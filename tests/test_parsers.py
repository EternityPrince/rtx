from pathlib import Path
from rtx.parsers import (
    get_parser_for_path,
    CodeParser,
    TextParser,
    DocxParser,
    PptxParser,
    EbookParser,
    PdfParser,
)

def test_parser_factory():
    assert isinstance(get_parser_for_path(Path("file.py")), CodeParser)
    assert isinstance(get_parser_for_path(Path("file.md")), CodeParser)
    assert isinstance(get_parser_for_path(Path("file.txt")), TextParser)
    assert isinstance(get_parser_for_path(Path("file.docx")), DocxParser)
    assert isinstance(get_parser_for_path(Path("file.pptx")), PptxParser)
    assert isinstance(get_parser_for_path(Path("file.epub")), EbookParser)
    assert isinstance(get_parser_for_path(Path("file.fb2")), EbookParser)
    assert isinstance(get_parser_for_path(Path("file.pdf")), PdfParser)

def test_code_parser(sandbox_dir):
    parser = CodeParser()
    out = parser.parse(sandbox_dir / "calculator.py")
    assert out.startswith("```python")
    assert "def add" in out
    assert out.endswith("```")

def test_text_parser(sandbox_dir):
    parser = TextParser()
    # Let's create a temporary config file
    config_path = sandbox_dir / "settings.conf"
    config_path.write_text("port = 8080\nhost = localhost", encoding="utf-8")
    
    out = parser.parse(config_path)
    assert out.startswith("```text")
    assert "port = 8080" in out
    assert out.endswith("```")
    config_path.unlink()

def test_docx_parser(sandbox_dir):
    parser = DocxParser()
    out = parser.parse(sandbox_dir / "sample.docx")
    assert "Heading 1 Test" in out
    assert "This is paragraph 1" in out

def test_pptx_parser(sandbox_dir):
    parser = PptxParser()
    out = parser.parse(sandbox_dir / "sample.pptx")
    assert "RTX TUI Presentation" in out
    assert "Bullet Point 1" in out

def test_pdf_parser(sandbox_dir):
    parser = PdfParser()
    out = parser.parse(sandbox_dir / "sample.pdf")
    assert "Hello PDF World" in out

def test_epub_parser(sandbox_dir):
    parser = EbookParser()
    out = parser.parse(sandbox_dir / "sample.epub")
    assert "Introduction to RTX" in out
    assert "Epub is a great digital book format" in out
