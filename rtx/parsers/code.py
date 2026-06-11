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
            
        # Determine backtick fence length to avoid collision
        fence = "```"
        if "```" in content:
            # If the code itself contains triple backticks, use 4 backticks for fence
            fence = "````"
            
        return f"{fence}{lang}\n{content}\n{fence}"
