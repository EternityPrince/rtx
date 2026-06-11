from pathlib import Path
from rtx.parsers.base import BaseParser

def iter_block_items(parent):
    """
    Yield each paragraph and table child within `parent`, in document order.
    Each returned value is an instance of either Paragraph or Table.
    """
    from docx.document import Document
    from docx.text.paragraph import Paragraph
    from docx.table import Table

    if isinstance(parent, Document):
        parent_elm = parent.element.body
    elif isinstance(parent, Table):
        # We could iterate inside cell but let's stick to root level items for simplicity
        parent_elm = parent._tbl
    else:
        raise TypeError("Unsupported parent element")

    for child in parent_elm.iterchildren():
        if child.tag.endswith('p'):
            yield Paragraph(child, parent)
        elif child.tag.endswith('tbl'):
            yield Table(child, parent)

class DocxParser(BaseParser):
    def parse(self, path: Path) -> str:
        # Lazy import to avoid loading heavy modules on startup
        import docx
        
        doc = docx.Document(path)
        markdown_lines = []
        
        from docx.text.paragraph import Paragraph
        from docx.table import Table

        for item in iter_block_items(doc):
            if isinstance(item, Paragraph):
                text = item.text.strip()
                if not text:
                    continue
                
                style_name = item.style.name if item.style else ""
                
                # Check for headings
                if style_name.startswith("Heading 1"):
                    markdown_lines.append(f"\n# {text}\n")
                elif style_name.startswith("Heading 2"):
                    markdown_lines.append(f"\n## {text}\n")
                elif style_name.startswith("Heading 3"):
                    markdown_lines.append(f"\n### {text}\n")
                elif style_name.startswith("Heading 4"):
                    markdown_lines.append(f"\n#### {text}\n")
                elif "List Bullet" in style_name:
                    markdown_lines.append(f"* {text}")
                elif "List Number" in style_name:
                    markdown_lines.append(f"1. {text}")
                else:
                    markdown_lines.append(text)
            elif isinstance(item, Table):
                markdown_lines.append("")
                # Render table
                for i, row in enumerate(item.rows):
                    row_cells = [cell.text.replace("\n", " ").strip() for cell in row.cells]
                    row_str = "| " + " | ".join(row_cells) + " |"
                    markdown_lines.append(row_str)
                    
                    # Add separator after header row
                    if i == 0:
                        sep_cells = ["---" for _ in row.cells]
                        sep_str = "| " + " | ".join(sep_cells) + " |"
                        markdown_lines.append(sep_str)
                markdown_lines.append("")

        return "\n".join(markdown_lines).strip()
