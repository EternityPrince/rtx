from pathlib import Path
from rtx.parsers.base import BaseParser

EXTENSION_TO_LANG = {
    ".py": "python",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".sh": "bash",
    ".bash": "bash",
    ".md": "markdown",
}

class CodeParser(BaseParser):
    def parse(self, path: Path) -> str:
        suffix = path.suffix.lower()
        lang = EXTENSION_TO_LANG.get(suffix, "")
        
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        from rtx.parsers.pdf import get_safe_markdown_fence
        fence = get_safe_markdown_fence(content)
            
        return f"{fence}{lang}\n{content}\n{fence}"
