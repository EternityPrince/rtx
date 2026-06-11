import asyncio
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional, Iterable
from rich.text import Text
from rich.table import Table

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Input, Label, DirectoryTree, Button
from textual.widgets.tree import TreeNode
from textual.widgets._directory_tree import DirEntry
from textual.screen import ModalScreen
from textual.worker import get_current_worker

from rtx.digger import DiggerEngine, format_bytes
from rtx.pipeline import run_parser_pipeline, ParseResult

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
            
        return text

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return paths

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
            Label("Инициализация парсинга...", id="parsing_title"),
            Static("Подготовка...", id="parsing_progress"),
            Static("", id="parsing_log"),
            Static("", id="parsing_summary", classes="hidden"),
            Button("Закрыть", id="close_btn", variant="primary", classes="hidden"),
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
        progress_widget.update(f"Обработано {current} из {total} файлов ({pct}%)")
        
        log_widget = self.query_one("#parsing_log", Static)
        self.log_content.append(f"Парсинг: {rel_path}...")
        log_widget.update("\n".join(self.log_content))
        log_widget.scroll_end(animate=False)

    def finished_parsing(self, results: List[ParseResult]):
        self.query_one("#parsing_log").add_class("hidden")
        if not self.mirror_mode and not self.output_file:
            self.query_one("#parsing_progress").update("[bold green]Парсинг завершен! Результаты скопированы в буфер обмена.[/bold green]")
        else:
            self.query_one("#parsing_progress").update("[bold green]Парсинг завершен![/bold green]")
        
        summary_panel = self.query_one("#parsing_summary", Static)
        summary_panel.remove_class("hidden")
        
        # Build Table
        table = Table(
            title="Сводная статистика обработки файлов",
            show_header=True,
            header_style="bold magenta",
            expand=True
        )
        table.add_column("Расширение", style="cyan")
        table.add_column("Количество файлов", justify="right")
        table.add_column("Строк извлечено", justify="right")
        table.add_column("Символов извлечено", justify="right")
        table.add_column("Статус", justify="center")
        
        stats = {}
        for res in results:
            ext = res.extension.lower() or "no_ext"
            if ext not in stats:
                stats[ext] = {"count": 0, "lines": 0, "chars": 0, "success": 0, "failed": 0}
            stats[ext]["count"] += 1
            stats[ext]["lines"] += res.lines
            stats[ext]["chars"] += res.chars
            if res.status == "Success":
                stats[ext]["success"] += 1
            else:
                stats[ext]["failed"] += 1
                
        for ext, s in sorted(stats.items()):
            total = s["count"]
            succ = s["success"]
            fail = s["failed"]
            
            if fail == 0:
                status_str = "[green]Успешно[/green]"
            elif succ == 0:
                status_str = "[red]Ошибка[/red]"
            else:
                status_str = f"[yellow]Частично ({succ}/{total})[/yellow]"
                
            table.add_row(
                ext,
                str(total),
                f"{s['lines']:,}",
                f"{s['chars']:,}",
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
        ("q", "quit", "Выйти"),
        ("x", "toggle_select", "Выделить (Toggle)"),
        ("m", "toggle_mode", "Режим (Mirror/Stream)"),
        ("ctrl+p", "start_parsing", "Парсить выделенные"),
        ("p", "start_parsing", "Парсить"),
    ]
    
    CSS = """
    #tree_container {
        width: 45%;
        border-right: solid $accent;
    }
    #right_panel {
        width: 55%;
        padding: 1;
    }
    #details_panel {
        height: 1fr;
        padding-bottom: 1;
    }
    #input_container {
        height: auto;
        border-top: dashed $accent;
        padding-top: 1;
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

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(
            Vertical(
                RtxDirectoryTree(self.project_path, self.project_path, id="dir_tree"),
                id="tree_container"
            ),
            Vertical(
                Static("", id="details_panel"),
                Vertical(
                    Label("Выходной файл (Режим A):"),
                    Input(
                        value=str(self.output_file) if self.output_file else "",
                        placeholder="Пусто для копирования в буфер обмена",
                        id="output_path_input"
                    ),
                    id="input_container"
                ),
                id="right_panel"
            )
        )
        yield Footer()

    def on_mount(self) -> None:
        self.update_details()

    def update_details(self) -> None:
        details = self.query_one("#details_panel", Static)
        
        mode_str = "[bold magenta]Режим B: Зеркалирование (.rtx/)[/bold magenta]" if self.mirror_mode else "[bold cyan]Режим A: Единый файл (Stream)[/bold cyan]"
        if self.mirror_mode:
            output_str = "[dim]Не применимо (Зеркалирование)[/dim]"
        else:
            output_str = f"[green]{self.output_file}[/green]" if self.output_file else "[bold yellow]Буфер обмена (Clipboard)[/bold yellow]"
        
        files_count = len([p for p in self.selected_paths if p.is_file()])
        dirs_count = len([p for p in self.selected_paths if p.is_dir()])
        
        lines = [
            "[bold underline]Настройки RTX[/bold underline]\n",
            f"Текущий режим: {mode_str}",
            f"Выходной файл: {output_str}",
            f"Выбрано файлов: [bold]{files_count}[/bold] (и папок: {dirs_count})\n",
            "[bold underline]Горячие клавиши[/bold underline]",
            "  [bold]X[/bold]      - Выделить / Снять выделение",
            "  [bold]Enter[/bold]  - Раскрыть / Свернуть папку",
            "  [bold]M[/bold]      - Переключить режим (Mirror / Stream)",
            "  [bold]Ctrl+P[/bold] - Начать парсинг",
            "  [bold]Q[/bold]      - Выйти\n",
            "[bold underline]Выбранные файлы:[/bold underline]"
        ]
        
        files_only = sorted([p.relative_to(self.project_path) for p in self.selected_paths if p.is_file()])
        if not files_only:
            lines.append("  [dim](нет выбранных файлов)[/dim]")
        else:
            for p in files_only[:15]:
                lines.append(f"  • {p}")
            if len(files_only) > 15:
                lines.append(f"  ... и еще {len(files_only) - 15} файлов.")
                
        details.update("\n".join(lines))

    @on(Input.Submitted, "#output_path_input")
    def handle_output_path_submit(self, event: Input.Submitted) -> None:
        val = event.value.strip()
        if val:
            self.output_file = Path(val)
        else:
            self.output_file = None
        self.update_details()
        self.notify(f"Выходной файл сохранен: {self.output_file or 'stdout'}")

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
            # Find all valid descendant files inside the directory
            files = list(self.digger.scan_valid_files(start_dir=path))
            # If any of those files are in selected_paths, we toggle all of them off.
            # Otherwise we select all of them.
            any_selected = any(f in self.selected_paths for f in files)
            if any_selected:
                for f in files:
                    self.selected_paths.discard(f)
                self.selected_paths.discard(path)
            else:
                for f in files:
                    self.selected_paths.add(f)
                self.selected_paths.add(path)
                
        tree.refresh()
        self.update_details()

    def action_toggle_mode(self) -> None:
        self.mirror_mode = not self.mirror_mode
        self.update_details()
        self.notify(f"Режим изменен: {'Зеркальный' if self.mirror_mode else 'Единый файл'}")

    def action_start_parsing(self) -> None:
        files_only = [p for p in self.selected_paths if p.is_file()]
        if not files_only:
            self.notify("Выберите файлы для парсинга с помощью клавиши X!", severity="warning")
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

def run_tui(project_path: Path, mirror_mode: bool = False, output_file: Optional[Path] = None):
    app = RtxApp(project_path, mirror_mode=mirror_mode, output_file=output_file)
    app.run()
