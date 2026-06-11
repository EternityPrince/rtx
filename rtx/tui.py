import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional, Iterable, Union
from rich.text import Text
from rich.table import Table

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Input, Label, DirectoryTree, Button, Markdown
from textual.widgets.tree import TreeNode
from textual.widgets._directory_tree import DirEntry
from textual.screen import ModalScreen
from textual.worker import get_current_worker

from rtx.digger import DiggerEngine, format_bytes, get_file_metrics
from rtx.pipeline import run_parser_pipeline, ParseResult
from rtx.parsers import get_parser_for_path

class PreviewArea(Static):
    can_focus = True

    BINDINGS = [
        ("up", "scroll_up", "Scroll Up"),
        ("down", "scroll_down", "Scroll Down"),
        ("pageup", "page_up", "Page Up"),
        ("pagedown", "page_down", "Page Down"),
        ("home", "scroll_home", "Home"),
        ("end", "scroll_end", "End"),
    ]

class RtxDirectoryTree(DirectoryTree):
    def __init__(self, root: Path, project_path: Path, **kwargs):
        self.project_path = project_path
        super().__init__(root, **kwargs)

    def render_label(self, node: TreeNode[DirEntry], base_style, style) -> Text:
        # Get the standard label
        text = super().render_label(node, base_style, style)
        path = node.data.path if node.data else None
        
        if path:
            # 1. Append lazy-loaded stats if available
            if path in self.app.node_stats:
                files, lines, chars, bytes_size = self.app.node_stats[path]
                text.append(f" (F:{files} L:{lines} C:{chars} B:{format_bytes(bytes_size)})", style="dim")
            elif path.is_file():
                # Display individual file size instantly
                try:
                    sz = path.stat().st_size
                    text.append(f" ({format_bytes(sz)})", style="dim")
                except Exception:
                    pass
            
            # 2. Prepend checkboxes based on selection state
            prefix = "⬜ "
            if path.is_dir():
                if path in self.app.selected_paths:
                    prefix = "✅ "  # Fully selected
                else:
                    # Check if any selected files are under this directory
                    any_under = any(p.is_relative_to(path) for p in self.app.selected_paths if p.is_file())
                    if any_under:
                        prefix = "🟨 "  # Partially selected
            elif path.is_file():
                if path in self.app.selected_paths:
                    prefix = "✅ "  # Selected
                    
            text = Text(prefix) + text
            
            # 3. Apply visual highlight (reverse text styling) if selected
            if path in self.app.selected_paths:
                text.stylize("bold reverse")
            
        return text

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        query = getattr(self.app, "search_query", "").strip()
        if not query:
            return paths
            
        import fnmatch
        filtered = []
        query_lower = query.lower()
        for p in paths:
            if p.is_dir():
                filtered.append(p)
            else:
                name_lower = p.name.lower()
                if query_lower in name_lower or fnmatch.fnmatch(name_lower, query_lower):
                    filtered.append(p)
        return filtered

class ParsingScreen(ModalScreen):
    def __init__(self, selected_files: List[Path], mirror_mode: bool, output_file: Optional[Path], project_path: Path):
        self.selected_files = selected_files
        self.mirror_mode = mirror_mode
        self.output_file = output_file
        self.project_path = project_path
        self.log_content = []
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Container(
            Label("Initializing parsing...", id="parsing_title"),
            Static("Preparing...", id="parsing_progress"),
            Static("", id="parsing_log"),
            Static("", id="parsing_summary", classes="hidden"),
            Button("Close", id="close_btn", variant="primary", classes="hidden"),
            id="parsing_modal_container"
        )

    def on_mount(self) -> None:
        self.run_parsing()

    @work(thread=True)
    def run_parsing(self) -> None:
        def progress(path: Path, current: int, total: int):
            self.app.call_from_thread(self.update_progress, path, current, total)
            
        results = run_parser_pipeline(self.selected_files, progress_callback=progress)
        
        # Write results
        if self.mirror_mode:
            from rtx.writer import write_mirror
            write_mirror(results, self.project_path)
        else:
            from rtx.writer import write_stream
            write_stream(results, self.project_path, output_file=self.output_file)
            
        self.app.call_from_thread(self.finished_parsing, results)

    def update_progress(self, path: Path, current: int, total: int):
        rel_path = path.relative_to(self.project_path) if path.is_relative_to(self.project_path) else path
        
        progress_widget = self.query_one("#parsing_progress", Static)
        pct = int((current / total) * 100) if total > 0 else 0
        progress_widget.update(f"Processed {current} of {total} files ({pct}%)")
        
        log_widget = self.query_one("#parsing_log", Static)
        self.log_content.append(f"Parsing: {rel_path}...")
        log_widget.update("\n".join(self.log_content))
        log_widget.scroll_end(animate=False)

    def finished_parsing(self, results: List[ParseResult]):
        self.query_one("#parsing_log").add_class("hidden")
        if not self.mirror_mode and not self.output_file:
            self.query_one("#parsing_progress").update("[bold green]Parsing completed! Results copied to clipboard.[/bold green]")
        else:
            self.query_one("#parsing_progress").update("[bold green]Parsing completed![/bold green]")
        
        summary_panel = self.query_one("#parsing_summary", Static)
        summary_panel.remove_class("hidden")
        
        # Build Table
        table = Table(
            title="File Processing Summary Statistics",
            show_header=True,
            header_style="bold magenta",
            expand=True
        )
        table.add_column("Extension", style="cyan")
        table.add_column("File Count", justify="right")
        table.add_column("Lines Extracted", justify="right")
        table.add_column("Characters Extracted", justify="right")
        table.add_column("Time Elapsed", justify="right")
        table.add_column("Status", justify="center")
        
        stats = {}
        for res in results:
            ext = res.extension.lower() or "no_ext"
            if ext not in stats:
                stats[ext] = {"count": 0, "lines": 0, "chars": 0, "success": 0, "failed": 0, "duration": 0.0}
            stats[ext]["count"] += 1
            stats[ext]["lines"] += res.lines
            stats[ext]["chars"] += res.chars
            stats[ext]["duration"] += getattr(res, "duration", 0.0)
            if res.status == "Success":
                stats[ext]["success"] += 1
            else:
                stats[ext]["failed"] += 1
                
        for ext, s in sorted(stats.items()):
            total = s["count"]
            succ = s["success"]
            fail = s["failed"]
            
            if fail == 0:
                status_str = "[green]Success[/green]"
            elif succ == 0:
                status_str = "[red]Error[/red]"
            else:
                status_str = f"[yellow]Partial ({succ}/{total})[/yellow]"
                
            table.add_row(
                ext,
                str(total),
                f"{s['lines']:,}",
                f"{s['chars']:,}",
                f"{s['duration']:.2f}s",
                status_str
            )
            
        summary_panel.update(table)
        
        # Show close button
        close_btn = self.query_one("#close_btn", Button)
        close_btn.remove_class("hidden")
        close_btn.focus()

    @on(Button.Pressed, "#close_btn")
    def on_close_pressed(self) -> None:
        self.dismiss()

class RtxApp(App):
    TITLE = "RTX - Universal Workspace Parser"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("x", "toggle_select", "Select (Toggle)"),
        ("m", "toggle_mode", "Mode (Mirror/Stream)"),
        ("ctrl+p", "start_parsing", "Parse Selected"),
        ("p", "start_parsing", "Parse"),
        ("o", "open_file", "Open File"),
        ("r", "reload", "Reload"),
    ]
    
    CSS = """
    #tree_container {
        width: 30%;
        border-right: solid $accent;
    }
    #right_panel {
        width: 70%;
        layout: horizontal;
    }
    #details_container {
        width: 40%;
        border-right: solid $accent;
        padding: 1;
    }
    #preview_container {
        width: 60%;
        padding: 1;
    }
    #details_panel {
        height: 1fr;
    }
    #input_container {
        height: auto;
        border-top: dashed $accent;
        padding-top: 1;
    }
    #preview_header {
        height: 3;
        margin-bottom: 1;
    }
    #preview_title {
        text-style: bold;
        background: $accent;
        color: $text;
        padding: 0 2;
        height: 100%;
        content-align: left middle;
        width: 1fr;
    }
    #open_file_btn {
        height: 100%;
        min-width: 12;
    }
    #preview_content {
        height: 1fr;
        overflow-y: scroll;
        border: solid $surface;
        padding: 1 2;
    }
    #preview_content:focus {
        border: solid $accent;
    }
    #preview_markdown {
        height: 1fr;
        overflow-y: scroll;
        border: solid $surface;
        padding: 1 2;
    }
    #preview_markdown:focus {
        border: solid $accent;
    }
    #search_input {
        margin-bottom: 1;
        border: solid $accent;
    }
    
    ParsingScreen {
        align: center middle;
    }
    #parsing_modal_container {
        width: 80%;
        height: 80%;
        border: thick $accent;
        background: $panel;
        padding: 1 2;
    }
    #parsing_title {
        text-style: bold;
        text-align: center;
        margin-bottom: 1;
    }
    #parsing_progress {
        text-align: center;
        margin-bottom: 1;
        color: $accent;
    }
    #parsing_log {
        height: 65%;
        border: solid $surface;
        overflow-y: scroll;
        margin-bottom: 1;
    }
    #parsing_summary {
        height: 65%;
        overflow-y: scroll;
        margin-bottom: 1;
    }
    .hidden {
        display: none;
    }
    """

    def __init__(self, project_path: Path, mirror_mode: bool = False, output_file: Optional[Path] = None):
        super().__init__()
        self.project_path = project_path.resolve()
        self.mirror_mode = mirror_mode
        self.output_file = output_file
        
        self.digger = DiggerEngine(self.project_path)
        self.selected_paths: Set[Path] = set()
        self.node_stats: Dict[Path, Tuple[int, int, int, int]] = {}
        self.current_preview_path: Optional[Path] = None
        self.search_query: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(
            Vertical(
                Input(placeholder="Filter files (e.g. *.py)...", id="search_input"),
                RtxDirectoryTree(self.project_path, self.project_path, id="dir_tree"),
                id="tree_container"
            ),
            Horizontal(
                Vertical(
                    Static("", id="details_panel"),
                    Vertical(
                        Label("Output File (Mode A):"),
                        Input(
                            value=str(self.output_file) if self.output_file else "",
                            placeholder="Empty to copy to clipboard",
                            id="output_path_input"
                        ),
                        id="input_container"
                    ),
                    id="details_container"
                ),
                Vertical(
                    Horizontal(
                        Label("File Preview: -", id="preview_title"),
                        Button("Open", id="open_file_btn", variant="default", disabled=True),
                        id="preview_header"
                    ),
                    PreviewArea("(select a file to preview)", id="preview_content"),
                    Markdown(id="preview_markdown", classes="hidden"),
                    id="preview_container"
                ),
                id="right_panel"
            )
        )
        yield Footer()

    def on_mount(self) -> None:
        self.update_details()
        self.query_one("#dir_tree").focus()

    def get_selected_metrics(self) -> Tuple[int, int, int, int, int]:
        """
        Calculate metrics for all selected files: (Files, Lines, Chars, Bytes, EstTokens).
        """
        total_files = 0
        total_lines = 0
        total_chars = 0
        total_bytes = 0
        total_tokens = 0
        
        for path in list(self.selected_paths):
            if path.is_file():
                if path in self.digger.metrics_cache:
                    _, lines, chars, bytes_sz = self.digger.metrics_cache[path]
                else:
                    lines, chars, bytes_sz = get_file_metrics(path)
                    self.digger.metrics_cache[path] = (1, lines, chars, bytes_sz)
                
                total_files += 1
                total_lines += lines
                total_chars += chars
                total_bytes += bytes_sz
                total_tokens += chars // 4
                
        return total_files, total_lines, total_chars, total_bytes, total_tokens

    def update_details(self) -> None:
        details = self.query_one("#details_panel", Static)
        
        mode_str = "[bold underline magenta]Mode B: Mirroring (.rtx/)[/bold underline magenta]" if self.mirror_mode else "[bold underline cyan]Mode A: Single File (Stream)[/bold underline cyan]"
        if self.mirror_mode:
            output_str = "[dim]Not Applicable (Mirroring)[/dim]"
        else:
            output_str = f"[green]{self.output_file}[/green]" if self.output_file else "[bold yellow]Clipboard[/bold yellow]"
        
        files_count, total_lines, total_chars, total_bytes, total_tokens = self.get_selected_metrics()
        dirs_count = len([p for p in self.selected_paths if p.is_dir()])
        
        lines = [
            "[bold underline]RTX Settings[/bold underline]\n",
            f"Current Mode: {mode_str}",
            f"Output File: {output_str}",
            f"Selected Files: [bold]{files_count}[/bold] (and folders: {dirs_count})",
            f"Total Size: [bold]{format_bytes(total_bytes)}[/bold]",
            f"Lines of Code: [bold]{total_lines:,}[/bold]",
            f"Characters: [bold]{total_chars:,}[/bold]",
            f"Est. Tokens: [bold]{total_tokens:,}[/bold]\n",
            "[bold underline]Keyboard Shortcuts[/bold underline]",
            "  [bold]X[/bold]      - Select / Deselect",
            "  [bold]Enter[/bold]  - Expand / Collapse folder",
            "  [bold]M[/bold]      - Toggle Mode (Mirror / Stream)",
            "  [bold]Ctrl+P[/bold] - Start Parsing",
            "  [bold]Q[/bold]      - Quit\n",
            "[bold underline]Selected Files:[/bold underline]"
        ]
        
        files_only = sorted([p.relative_to(self.project_path) for p in self.selected_paths if p.is_file()])
        if not files_only:
            lines.append("  [dim](no selected files)[/dim]")
        else:
            for p in files_only[:15]:
                lines.append(f"  • {p}")
            if len(files_only) > 15:
                lines.append(f"  ... and {len(files_only) - 15} more files.")
                
        details.update("\n".join(lines))

    @on(Input.Changed, "#search_input")
    def handle_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value
        tree = self.query_one(RtxDirectoryTree)
        tree.reload()

    @on(Input.Submitted, "#output_path_input")
    def handle_output_path_submit(self, event: Input.Submitted) -> None:
        val = event.value.strip()
        if val:
            self.output_file = Path(val)
        else:
            self.output_file = None
        self.update_details()
        self.notify(f"Output file saved: {self.output_file or 'stdout'}")

    def _get_all_descendants(self, dir_path: Path) -> Tuple[List[Path], List[Path]]:
        """
        Recursively get all valid files and directories under dir_path.
        Returns a tuple of (files, dirs).
        """
        import os
        from rtx.digger import is_excluded_path
        files = []
        dirs = []
        
        for dirpath, dirnames, filenames in os.walk(dir_path):
            path_dir = Path(dirpath)
            
            # Filter dirnames in-place to prevent entering excluded directories
            for dirname in list(dirnames):
                sub_dir = path_dir / dirname
                if is_excluded_path(sub_dir, self.project_path, self.digger.ignore_patterns):
                    dirnames.remove(dirname)
                else:
                    dirs.append(sub_dir.resolve())
                    
            for filename in filenames:
                file_path = path_dir / filename
                if not is_excluded_path(file_path, self.project_path, self.digger.ignore_patterns):
                    files.append(file_path.resolve())
                    
        return files, dirs

    def action_toggle_select(self) -> None:
        tree = self.query_one(RtxDirectoryTree)
        node = tree.cursor_node
        if not node or not node.data:
            return
            
        path = node.data.path.resolve()
        
        if path.is_file():
            if path in self.selected_paths:
                self.selected_paths.remove(path)
            else:
                self.selected_paths.add(path)
        elif path.is_dir():
            files, dirs = self._get_all_descendants(path)
            # Toggle logic: if the directory itself or any of its descendants is currently selected,
            # we deselect all of them. Otherwise, we select all of them.
            any_selected = (path in self.selected_paths) or any(f in self.selected_paths for f in files) or any(d in self.selected_paths for d in dirs)
            if any_selected:
                self.selected_paths.discard(path)
                for f in files:
                    self.selected_paths.discard(f)
                for d in dirs:
                    self.selected_paths.discard(d)
            else:
                self.selected_paths.add(path)
                for f in files:
                    self.selected_paths.add(f)
                for d in dirs:
                    self.selected_paths.add(d)
                
        tree.refresh()
        self.update_details()

    def action_toggle_mode(self) -> None:
        self.mirror_mode = not self.mirror_mode
        self.update_details()
        self.notify(f"Mode changed: {'Mirroring' if self.mirror_mode else 'Single File (Stream)'}")

    def action_reload(self) -> None:
        self.node_stats.clear()
        self.digger.metrics_cache.clear()
        tree = self.query_one(RtxDirectoryTree)
        tree.reload()
        self.notify("Workspace reloaded and caches cleared.")

    @on(Button.Pressed, "#open_file_btn")
    def handle_open_file_pressed(self) -> None:
        self.action_open_file()

    def action_open_file(self) -> None:
        if self.current_preview_path and self.current_preview_path.is_file():
            self.open_current_file()
        else:
            self.notify("Select a file to open!", severity="warning")

    def open_current_file(self) -> None:
        if not self.current_preview_path:
            return
        import sys
        import os
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(self.current_preview_path)], check=True)
            elif sys.platform == "win32":
                os.startfile(self.current_preview_path)
            else:
                subprocess.run(["xdg-open", str(self.current_preview_path)], check=True)
            self.notify(f"File opened in system: {self.current_preview_path.name}")
        except Exception as e:
            self.notify(f"Failed to open file: {e}", severity="error")

    def action_start_parsing(self) -> None:
        files_only = [p for p in self.selected_paths if p.is_file()]
        if not files_only:
            self.notify("Select files to parse using the X key!", severity="warning")
            return
            
        self.push_screen(
            ParsingScreen(
                selected_files=files_only,
                mirror_mode=self.mirror_mode,
                output_file=self.output_file,
                project_path=self.project_path
            )
        )

    @on(DirectoryTree.NodeExpanded)
    def handle_node_expanded(self, event: DirectoryTree.NodeExpanded[DirEntry]) -> None:
        node = event.node
        path = node.data.path if node.data else None
        if path and path.is_dir():
            if path not in self.node_stats:
                self.calculate_metrics_async(node, path)

    @work(thread=True)
    def calculate_metrics_async(self, node: TreeNode[DirEntry], path: Path) -> None:
        # Run heavy calculation in background thread
        stats = self.digger.calculate_metrics(path)
        self.node_stats[path] = stats
        self.call_from_thread(self._on_metrics_calculated)

    def _on_metrics_calculated(self) -> None:
        self.query_one(RtxDirectoryTree).refresh()

    @on(DirectoryTree.NodeHighlighted)
    def handle_node_highlighted(self, event: DirectoryTree.NodeHighlighted[DirEntry]) -> None:
        node = event.node
        path = node.data.path if node.data else None
        if path:
            self.show_preview(path)

    @work(thread=True, exclusive=True)
    def show_preview(self, path: Path) -> None:
        self.current_preview_path = path
        if path.is_dir():
            lines = [
                f"[bold cyan]Folder: {path.name}[/bold cyan]",
                f"[dim]Path: {path}[/dim]\n"
            ]
            if path in self.app.node_stats:
                files, lines_cnt, chars, bytes_size = self.app.node_stats[path]
                lines.extend([
                    "[bold]Folder statistics:[/bold]",
                    f"  Files: {files}",
                    f"  Lines of code: {lines_cnt}",
                    f"  Characters: {chars}",
                    f"  Size: {format_bytes(bytes_size)}"
                ])
            else:
                lines.append("[dim]Statistics not calculated. Expand folder to calculate.[/dim]")
            
            self.call_from_thread(self._update_preview_content, Text.from_markup("\n".join(lines)), str(path.name), is_markdown=False)
            return

        if path.is_file():
            self.call_from_thread(self._update_preview_content, Text("Loading preview..."), str(path.name), is_markdown=False)
            
            try:
                sz = path.stat().st_size
                if sz > 10 * 1024 * 1024:  # > 10MB
                    self.call_from_thread(self._update_preview_content, Text("File is too large for preview (>10MB)"), str(path.name), is_markdown=False)
                    return
            except Exception as e:
                self.call_from_thread(self._update_preview_content, Text(f"Failed to get file info: {e}"), str(path.name), is_markdown=False)
                return

            suffix = path.suffix.lower()
            
            # Markdown preview
            if suffix == ".md":
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                    self.call_from_thread(self._update_preview_content, content, str(path.name), is_markdown=True)
                    return
                except Exception as e:
                    self.call_from_thread(self._update_preview_content, Text(f"Failed to read markdown file: {e}"), str(path.name), is_markdown=False)
                    return
            
            # Formatted documents preview (docx, xlsx, csv, pptx, epub, fb2)
            if suffix in (".docx", ".xlsx", ".csv", ".pptx", ".epub", ".fb2"):
                try:
                    self.call_from_thread(self._update_preview_content, "Generating document preview...", str(path.name), is_markdown=False)
                    parser = get_parser_for_path(path)
                    markdown_text = parser.parse(path)
                    if len(markdown_text) > 5000:
                        markdown_text = markdown_text[:5000] + "\n\n...(preview truncated)..."
                    self.call_from_thread(self._update_preview_content, markdown_text, str(path.name), is_markdown=True)
                    return
                except Exception as e:
                    self.call_from_thread(self._update_preview_content, Text(f"Failed to parse document: {e}"), str(path.name), is_markdown=False)
                    return

            # Default text/code preview
            try:
                res = subprocess.run(
                    ['bat', '--color=always', '--style=numbers', '--line-range', ':300', str(path)],
                    capture_output=True,
                    text=True,
                    timeout=2.0
                )
                if res.returncode == 0:
                    preview_text = Text.from_ansi(res.stdout)
                    self.call_from_thread(self._update_preview_content, preview_text, str(path.name), is_markdown=False)
                    return
            except Exception:
                pass

            # Fallback to reading file and highlighting using plain text
            try:
                lines = []
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    for _ in range(300):
                        line = f.readline()
                        if not line:
                            break
                        lines.append(line)
                
                content = "".join(lines)
                if '\x00' in content:
                    msg = (
                        "This file is binary or has a format (e.g. PDF, image)\n"
                        "that cannot be displayed as plain text.\n\n"
                        "You can open it in the associated system application\n"
                        "by clicking the 'Open' button in the top-right corner or pressing 'O'."
                    )
                    self.call_from_thread(self._update_preview_content, Text(msg), str(path.name), is_markdown=False)
                    return

                numbered_lines = []
                for i, line in enumerate(lines, 1):
                    numbered_lines.append(f"{i:4d} │ {line.rstrip()}")
                fallback_text = Text("\n".join(numbered_lines))
                self.call_from_thread(self._update_preview_content, fallback_text, str(path.name), is_markdown=False)
            except Exception as e:
                self.call_from_thread(self._update_preview_content, Text(f"Failed to read file: {e}"), str(path.name), is_markdown=False)

    def _update_preview_content(self, text: Union[Text, str], title: str, is_markdown: bool = False) -> None:
        try:
            self.query_one("#preview_title", Label).update(f"Preview: {title}")
            content_widget = self.query_one("#preview_content", PreviewArea)
            markdown_widget = self.query_one("#preview_markdown", Markdown)
            
            if is_markdown:
                content_widget.add_class("hidden")
                markdown_widget.remove_class("hidden")
                markdown_widget.update(str(text))
            else:
                markdown_widget.add_class("hidden")
                content_widget.remove_class("hidden")
                content_widget.update(text)
                content_widget.scroll_home(animate=False)
            
            # Update "Open" button disabled state
            btn = self.query_one("#open_file_btn", Button)
            if self.current_preview_path and self.current_preview_path.is_file():
                btn.disabled = False
            else:
                btn.disabled = True
        except Exception:
            pass

def run_tui(project_path: Path, mirror_mode: bool = False, output_file: Optional[Path] = None):
    app = RtxApp(project_path, mirror_mode=mirror_mode, output_file=output_file)
    app.run()
