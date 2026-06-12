from pathlib import Path
from rtx.parsers import (
    get_parser_for_path,
    CodeParser,
    TextParser,
    DocxParser,
    XlsxParser,
    CsvParser,
    PptxParser,
    EbookParser,
    PdfParser,
)

def test_parser_factory():
    assert isinstance(get_parser_for_path(Path("file.py")), CodeParser)
    assert isinstance(get_parser_for_path(Path("file.md")), CodeParser)
    assert isinstance(get_parser_for_path(Path("file.txt")), TextParser)
    assert isinstance(get_parser_for_path(Path("file.docx")), DocxParser)
    assert isinstance(get_parser_for_path(Path("file.xlsx")), XlsxParser)
    assert isinstance(get_parser_for_path(Path("file.csv")), CsvParser)
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

def test_get_safe_markdown_fence():
    from rtx.parsers.pdf import get_safe_markdown_fence
    assert get_safe_markdown_fence("hello") == "```"
    assert get_safe_markdown_fence("```python\nprint(1)\n```") == "````"
    assert get_safe_markdown_fence("````markdown\n```\n````") == "`````"

def test_code_parser_dynamic_fence(sandbox_dir):
    parser = CodeParser()
    temp_md = sandbox_dir / "nested.md"
    temp_md.write_text("```python\nprint(1)\n```", encoding="utf-8")
    try:
        out = parser.parse(temp_md)
        assert out.startswith("````markdown")
        assert out.endswith("````")
    finally:
        temp_md.unlink()

def test_pdf_parser_fallbacks(sandbox_dir, monkeypatch):
    import sys
    from rtx.parsers.pdf import PdfParser
    import rtx.parsers.pdf
    
    # Force marker to be treated as missing/import failure
    monkeypatch.setitem(sys.modules, "marker", None)
    monkeypatch.setitem(sys.modules, "marker.converters.pdf", None)
    monkeypatch.setitem(sys.modules, "marker.models", None)
    
    # Capture calls to logger.debug
    debug_calls = []
    def mock_debug(msg, *args, **kwargs):
        debug_calls.append(msg)
    monkeypatch.setattr(rtx.parsers.pdf.logger, "debug", mock_debug)
    
    parser = PdfParser()
    out = parser.parse(sandbox_dir / "sample.pdf")
    assert "Hello PDF World" in out
    
    # Verify that the debug log was called because of marker failure
    assert len(debug_calls) >= 1
    assert any("marker-pdf failed" in str(msg) for msg in debug_calls)

def test_xlsx_parser(sandbox_dir):
    parser = XlsxParser()
    out = parser.parse(sandbox_dir / "sample.xlsx")
    assert "Sheet: TestSheet" in out
    assert "ColA" in out
    assert "ValA1" in out

def test_csv_parser(sandbox_dir):
    parser = CsvParser()
    out = parser.parse(sandbox_dir / "sample.csv")
    assert "Header1" in out
    assert "Row1Col1" in out

def test_pdf_image_extraction_pymupdf(sandbox_dir, monkeypatch):
    import sys
    # Force marker to fail so it falls back to PyMuPDF
    monkeypatch.setitem(sys.modules, "marker", None)
    monkeypatch.setitem(sys.modules, "marker.converters.pdf", None)
    monkeypatch.setitem(sys.modules, "marker.models", None)
    
    from rtx.parsers.pdf import PdfParser
    parser = PdfParser()
    out = parser.parse(sandbox_dir / "sample.pdf")
    
    assert "Hello PDF World" in out
    assert "![][image_" in out
    assert "data:image/jpeg;base64," in out

def test_pdf_image_extraction_pypdf(sandbox_dir, monkeypatch):
    import sys
    # Force marker and PyMuPDF to fail so it falls back to pypdf
    monkeypatch.setitem(sys.modules, "marker", None)
    monkeypatch.setitem(sys.modules, "marker.converters.pdf", None)
    monkeypatch.setitem(sys.modules, "marker.models", None)
    monkeypatch.setitem(sys.modules, "fitz", None)
    
    from rtx.parsers.pdf import PdfParser
    parser = PdfParser()
    out = parser.parse(sandbox_dir / "sample.pdf")
    
    assert "Hello PDF World" in out
    assert "![][image_" in out
    assert "data:image/jpeg;base64," in out

def test_process_and_compress_image():
    from rtx.parsers.pdf import process_and_compress_image
    from PIL import Image
    
    # 1. Test process_and_compress_image with a small RGB image
    img = Image.new("RGB", (200, 200), color="blue")
    uri = process_and_compress_image(img, max_dim=100)
    assert uri.startswith("data:image/jpeg;base64,")
    
    # Check that image was resized
    import base64
    import io
    header, encoded = uri.split(",", 1)
    data = base64.b64decode(encoded)
    decoded_img = Image.open(io.BytesIO(data))
    assert max(decoded_img.size) == 100
    
    # 2. Test with RGBA image (transparency conversion to RGB on white background)
    img_rgba = Image.new("RGBA", (150, 150), color=(0, 255, 0, 128))
    uri_rgba = process_and_compress_image(img_rgba)
    assert uri_rgba.startswith("data:image/jpeg;base64,")
