import sys
from pathlib import Path
from typing import List, Optional
import typer
from rich.console import Console
from rich.table import Table

from rtx.digger import DiggerEngine
from rtx.pipeline import run_parser_pipeline, ParseResult
from rtx.writer import write_stream, write_mirror

app = typer.Typer(add_completion=False, help="RTX - Universal Workspace Parser & Context Gatherer")

def print_summary_table(results: List[ParseResult], console: Console):
    """Prints a beautiful Rich table summarizing the parsing statistics."""
    if not results:
        console.print("[yellow]Нет файлов для обработки.[/yellow]")
        return
        
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
    
    # Group results by extension
    stats = {}
    for res in results:
        ext = res.extension.lower()
        if not ext:
            ext = "no_ext"
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
        
    console.print(table)

@app.command()
def main(
    path: Path = typer.Argument(
        default=Path("."),
        help="Путь к директории проекта для сканирования",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    tui: bool = typer.Option(
        False,
        "--tui",
        help="Запустить интерактивный TUI режим",
    ),
    mirror: bool = typer.Option(
        False,
        "--mirror", "-m",
        help="Режим B: Зеркалирование структуры в скрытую папку .rtx/",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Режим A: Путь к выходному файлу (если не указан и mirror=False, выводит в stdout)",
        dir_okay=False,
    ),
):
    if tui:
        # Launch Textual TUI
        from rtx.tui import run_tui
        run_tui(path, mirror_mode=mirror, output_file=output)
    else:
        # CLI Mode
        # If we are outputting to stdout (Scenario A with output=None),
        # all messages and tables must print to stderr to avoid polluting stdout.
        use_stderr = (not mirror and output is None)
        log_console = Console(stderr=use_stderr)
        
        log_console.print(f"[bold green]RTX:[/bold green] Сканирование директории: [cyan]{path}[/cyan]")
        digger = DiggerEngine(path)
        
        log_console.print("[yellow]Сбор списка файлов...[/yellow]")
        files = list(digger.scan_valid_files())
        
        if not files:
            log_console.print("[bold red]Нет валидных файлов для обработки в директории.[/bold red]")
            raise typer.Exit()
            
        log_console.print(f"Найдено файлов для парсинга: [bold]{len(files)}[/bold].")
        
        # Run parsing pipeline
        with log_console.status("[bold blue]Обработка файлов батчами...[/bold blue]") as status:
            def progress(p: Path, idx: int, total: int):
                status.update(f"[bold blue]Обработка [{idx+1}/{total}]:[/bold blue] {p.name}")
            results = run_parser_pipeline(files, progress_callback=progress)
            
        # Write output
        if mirror:
            log_console.print("[yellow]Запись результатов в режиме зеркалирования (.rtx/)...[/yellow]")
            write_mirror(results, path)
        else:
            if output:
                log_console.print(f"[yellow]Запись результатов в файл {output}...[/yellow]")
                write_stream(results, path, output_file=output)
            else:
                write_stream(results, path, output_file=None)
                log_console.print("[bold green]Результаты скопированы в буфер обмена![/bold green]")
                
        # Print stats summary
        print_summary_table(results, log_console)

if __name__ == "__main__":
    app()
