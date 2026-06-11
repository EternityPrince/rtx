from pathlib import Path
from rtx.parsers.base import BaseParser

class TextParser(BaseParser):
    def parse(self, path: Path) -> str:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        from rtx.parsers.pdf import get_safe_markdown_fence
        fence = get_safe_markdown_fence(content)
            
        return f"{fence}text\n{content}\n{fence}"
