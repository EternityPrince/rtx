from pathlib import Path
from rtx.parsers.base import BaseParser

class XlsxParser(BaseParser):
    def parse(self, path: Path) -> str:
        # Lazy import to avoid loading openpyxl on startup
        import openpyxl
        
        markdown_sections = []
        try:
            wb = openpyxl.load_workbook(path, data_only=True)
            for sheet in wb.worksheets:
                markdown_sections.append(f"### Sheet: {sheet.title}\n")
                
                rows = list(sheet.iter_rows(values_only=True))
                # Filter out completely empty trailing rows
                while rows and all(val is None for val in rows[-1]):
                    rows.pop()
                    
                if not rows:
                    markdown_sections.append("*Empty Sheet*\n")
                    continue
                
                # Determine max columns in sheet to form a correct table
                max_cols = max(len(row) for row in rows)
                
                for i, row in enumerate(rows):
                    row_cells = []
                    for val in row:
                        if val is None:
                            row_cells.append("")
                        else:
                            # Clean newlines and escape pipes to prevent table breaking
                            cell_str = str(val).replace("\n", " ").replace("|", "\\|").strip()
                            row_cells.append(cell_str)
                            
                    # Pad cells if row is shorter than max_cols
                    while len(row_cells) < max_cols:
                        row_cells.append("")
                        
                    row_str = "| " + " | ".join(row_cells) + " |"
                    markdown_sections.append(row_str)
                    
                    if i == 0:
                        sep_cells = ["---" for _ in range(max_cols)]
                        sep_str = "| " + " | ".join(sep_cells) + " |"
                        markdown_sections.append(sep_str)
                markdown_sections.append("")
                
            return "\n".join(markdown_sections).strip()
        except Exception as e:
            raise RuntimeError(f"Excel parsing failed for {path.name}: {str(e)}")
