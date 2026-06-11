import csv
from pathlib import Path
from rtx.parsers.base import BaseParser

class CsvParser(BaseParser):
    def parse(self, path: Path) -> str:
        markdown_lines = []
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if not rows:
                return ""
            
            # Format rows as a markdown table
            for i, row in enumerate(rows):
                # Clean cell text to prevent breaking Markdown table structure
                row_cells = [cell.replace("\n", " ").replace("|", "\\|").strip() for cell in row]
                row_str = "| " + " | ".join(row_cells) + " |"
                markdown_lines.append(row_str)
                
                # Add separator after header row
                if i == 0:
                    sep_cells = ["---" for _ in row]
                    sep_str = "| " + " | ".join(sep_cells) + " |"
                    markdown_lines.append(sep_str)
                    
            return "\n".join(markdown_lines).strip()
        except Exception as e:
            raise RuntimeError(f"CSV parsing failed for {path.name}: {str(e)}")
