from pathlib import Path
from rtx.parsers.base import BaseParser
from rtx.parsers.pdf import PdfParser, clear_marker_models
from rtx.parsers.docx import DocxParser
from rtx.parsers.xlsx import XlsxParser
from rtx.parsers.csv import CsvParser
from rtx.parsers.pptx import PptxParser
from rtx.parsers.ebook import EbookParser
from rtx.parsers.code import CodeParser, EXTENSION_TO_LANG
from rtx.parsers.text import TextParser

__all__ = [
    "BaseParser",
    "PdfParser",
    "DocxParser",
    "XlsxParser",
    "CsvParser",
    "PptxParser",
    "EbookParser",
    "CodeParser",
    "TextParser",
    "clear_marker_models",
    "get_parser_for_path",
]

def get_parser_for_path(path: Path) -> BaseParser:
    """Factory function to get the appropriate parser for a given file path."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return PdfParser()
    elif suffix == ".docx":
        return DocxParser()
    elif suffix == ".xlsx":
        return XlsxParser()
    elif suffix == ".csv":
        return CsvParser()
    elif suffix == ".pptx":
        return PptxParser()
    elif suffix in (".epub", ".fb2"):
        return EbookParser()
    elif suffix in EXTENSION_TO_LANG:
        return CodeParser()
    else:
        return TextParser()
