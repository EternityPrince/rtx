import sys
from pathlib import Path
from typing import List, Optional
import typer
from rich.console import Console
from rich.table import Table

from rtx.digger import DiggerEngine, is_excluded_path
from rtx.pipeline import run_parser_pipeline, ParseResult
from rtx.writer import write_stream, write_mirror

app = typer.Typer(add_completion=False, help="RTX - Universal Workspace Parser & Context Gatherer")

def print_summary_table(results: List[ParseResult], console: Console):
    """Prints a beautiful Rich table summarizing the parsing statistics."""
    if not results:
        console.print("[yellow]No files to process.[/yellow]")
        return
        
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
    
    # Group results by extension
    stats = {}
    for res in results:
        ext = res.extension.lower()
        if not ext:
            ext = "no_ext"
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
        
    console.print(table)

def get_git_status_files(root_path: Path) -> List[Path]:
    import subprocess
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root_path,
            capture_output=True,
            text=True,
            check=True
        )
        files = []
        for line in res.stdout.splitlines():
            if len(line) > 3:
                rel_path_str = line[3:].strip()
                if " -> " in rel_path_str:
                    rel_path_str = rel_path_str.split(" -> ")[-1].strip()
                if rel_path_str.startswith('"') and rel_path_str.endswith('"'):
                    rel_path_str = rel_path_str[1:-1]
                file_path = (root_path / rel_path_str).resolve()
                if file_path.exists() and file_path.is_file():
                    files.append(file_path)
        return files
    except Exception:
        return []

def get_git_diff_context(root_path: Path) -> str:
    import subprocess
    try:
        diff_unstaged = subprocess.run(["git", "diff"], cwd=root_path, capture_output=True, text=True).stdout
        diff_staged = subprocess.run(["git", "diff", "--cached"], cwd=root_path, capture_output=True, text=True).stdout
        
        status_res = subprocess.run(["git", "status", "--porcelain"], cwd=root_path, capture_output=True, text=True).stdout
        untracked_files = []
        for line in status_res.splitlines():
            if line.startswith("??"):
                filename = line[3:].strip()
                if filename.startswith('"') and filename.endswith('"'):
                    filename = filename[1:-1]
                untracked_files.append(filename)
        
        markdown = []
        markdown.append("# GIT DIFF AND CONTEXT\n\n")
        
        if diff_staged.strip():
            markdown.append("## Staged Changes (git diff --cached)\n")
            markdown.append("```diff\n" + diff_staged + "\n```\n\n")
            
        if diff_unstaged.strip():
            markdown.append("## Unstaged Changes (git diff)\n")
            markdown.append("```diff\n" + diff_unstaged + "\n```\n\n")
            
        if untracked_files:
            markdown.append("## Untracked Files\n")
            from rtx.digger import load_rtxignore_patterns
            ignore_patterns = load_rtxignore_patterns(root_path)
            for f_rel in untracked_files:
                f_path = root_path / f_rel
                if f_path.exists() and f_path.is_file() and not is_excluded_path(f_path, root_path, ignore_patterns):
                    markdown.append(f"### File: {f_rel} (Untracked)\n")
                    try:
                        content = f_path.read_text(encoding="utf-8", errors="ignore")
                        from rtx.parsers.pdf import get_safe_markdown_fence
                        fence = get_safe_markdown_fence(content)
                        from rtx.parsers.code import EXTENSION_TO_LANG
                        lang = EXTENSION_TO_LANG.get(f_path.suffix.lower(), "")
                        markdown.append(f"{fence}{lang}\n{content}\n{fence}\n\n")
                    except Exception as e:
                        markdown.append(f"Failed to read file: {e}\n\n")
                        
        return "".join(markdown)
    except Exception as e:
        return f"Error gathering git diff context: {e}"

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    path: Path = typer.Option(
        Path("."),
        help="Path to the project directory to scan",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    mirror: bool = typer.Option(
        False,
        "--mirror", "-m",
        help="Mode B: Mirror directory structure into the hidden folder .rtx/",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Mode A: Path to the output file (if not specified and mirror=False, prints to stdout and clipboard)",
        dir_okay=False,
    ),
):
    """
    RTX - Universal Workspace Parser & Context Gatherer.
    Runs TUI by default when no subcommand is specified.
    """
    if ctx.invoked_subcommand is None:
        # Launch Textual TUI
        from rtx.tui import run_tui
        run_tui(path, mirror_mode=mirror, output_file=output)

@app.command()
def scan(
    targets: List[str] = typer.Argument(
        None,
        help="Paths or glob patterns to scan (e.g. '.', 'dir_name/', '*.py'). If empty, scans all valid files.",
    ),
    mirror: bool = typer.Option(
        False,
        "--mirror", "-m",
        help="Mode B: Mirror directory structure into the hidden folder .rtx/",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Mode A: Path to the output file (if not specified, prints to stdout and clipboard)",
        dir_okay=False,
    ),
    git_status: bool = typer.Option(
        False,
        "--git-status", "-g",
        help="Scan only modified/untracked files (git status)",
    ),
    git_diff: bool = typer.Option(
        False,
        "--git-diff",
        help="Generate context in the form of git diff changes with surrounding code",
    ),
    project_path: Path = typer.Option(
        Path("."),
        "--project",
        help="Path to the project directory root",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
):
    """
    Scan files from target paths or glob patterns, parse them, and aggregate their contents.
    """
    use_stderr = (not mirror and output is None)
    log_console = Console(stderr=use_stderr)
    
    if git_diff:
        log_console.print("[bold green]RTX:[/bold green] Generating Git diff context...")
        diff_content = get_git_diff_context(project_path)
        if not diff_content.strip() or diff_content.strip() == "# GIT DIFF AND CONTEXT":
            log_console.print("[yellow]No git changes found.[/yellow]")
            raise typer.Exit()
            
        if mirror:
            rtx_dir = project_path / ".rtx"
            rtx_dir.mkdir(exist_ok=True)
            from rtx.writer import update_gitignore
            update_gitignore(project_path)
            target = rtx_dir / "git_diff.md"
            target.write_text(diff_content, encoding="utf-8")
            log_console.print(f"[bold green]Diff mirrored to {target}[/bold green]")
        else:
            if output:
                output.write_text(diff_content, encoding="utf-8")
                log_console.print(f"[bold green]Diff written to {output}[/bold green]")
            else:
                sys.stdout.write(diff_content)
                try:
                    import pyperclip
                    pyperclip.copy(diff_content)
                except Exception:
                    pass
                log_console.print("[bold green]Diff copied to clipboard![/bold green]")
        return

    digger = DiggerEngine(project_path)
    if git_status:
        log_console.print("[bold green]RTX:[/bold green] Scanning modified/untracked files from Git...")
        git_files = get_git_status_files(project_path)
        if not git_files:
            log_console.print("[yellow]No modified or untracked files found in git status.[/yellow]")
            raise typer.Exit()
        files = [f for f in git_files if not is_excluded_path(f, project_path, digger.ignore_patterns)]
    else:
        log_console.print(f"[bold green]RTX:[/bold green] Scanning project: [cyan]{project_path}[/cyan]")
        if targets:
            log_console.print(f"[yellow]Collecting file list for targets: {targets}...[/yellow]")
        else:
            log_console.print("[yellow]Collecting file list...[/yellow]")
        files = list(digger.scan_targets(targets))
        
    if not files:
        log_console.print("[bold red]No valid files to process.[/bold red]")
        raise typer.Exit()
        
    # Check for already indexed PDFs in .rtx/
    pdf_already_indexed = []
    for f in files:
        if f.suffix.lower() == ".pdf":
            try:
                rel_path = f.relative_to(project_path)
            except ValueError:
                rel_path = Path(f.name)
            mirror_path = project_path / ".rtx" / rel_path.with_name(rel_path.name + ".md")
            if mirror_path.exists():
                pdf_already_indexed.append((f, rel_path))
                
    if pdf_already_indexed:
        files_to_keep = []
        skipped_any = False
        for f, rel_path in pdf_already_indexed:
            log_console.print(f"[bold yellow]Warning:[/bold yellow] PDF file '{rel_path}' is already indexed in .rtx/.")
            if typer.confirm("Do you want to re-scan it?", default=False):
                files_to_keep.append(f)
            else:
                log_console.print(f"[yellow]Skipping already indexed PDF:[/yellow] {rel_path}")
                skipped_any = True
                
        if skipped_any:
            skipped_set = {f for f, _ in pdf_already_indexed if f not in files_to_keep}
            files = [f for f in files if f not in skipped_set]
            if not files:
                log_console.print("[yellow]No files left to process.[/yellow]")
                raise typer.Exit()
        
    log_console.print(f"Files found for parsing: [bold]{len(files)}[/bold].")
    
    with log_console.status("[bold blue]Processing files in batches...[/bold blue]") as status:
        def progress(p: Path, idx: int, total: int):
            status.update(f"[bold blue]Processing [{idx+1}/{total}]:[/bold blue] {p.name}")
        results = run_parser_pipeline(files, progress_callback=progress)
        
    if mirror:
        log_console.print("[yellow]Writing results in mirror mode (.rtx/)...[/yellow]")
        write_mirror(results, project_path)
    else:
        if output:
            log_console.print(f"[yellow]Writing results to file {output}...[/yellow]")
            write_stream(results, project_path, output_file=output)
        else:
            write_stream(results, project_path, output_file=None)
            log_console.print("[bold green]Results copied to clipboard![/bold green]")
            
    print_summary_table(results, log_console)

if __name__ == "__main__":
    app()
