from typer.testing import CliRunner
from rtx.cli import app

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "scan" in result.output

def test_cli_scan(sandbox_dir):
    runner = CliRunner()
    result = runner.invoke(app, ["scan", "--project", str(sandbox_dir)])
    assert result.exit_code == 0
    # Check that calculator.py boundary is in the output stream
    assert "# FILE: calculator.py" in result.output
    # Check that docx parsed headers are there
    assert "Heading 1 Test" in result.output
    # Check that csv and xlsx are there
    assert "Header1" in result.output
    assert "Sheet: TestSheet" in result.output

def test_cli_scan_targets(sandbox_dir):
    runner = CliRunner()
    result = runner.invoke(app, ["scan", "calculator.py", "--project", str(sandbox_dir)])
    assert result.exit_code == 0
    assert "# FILE: calculator.py" in result.output
    assert "sample.docx" not in result.output

def test_cli_mirror_mode(sandbox_dir):
    runner = CliRunner()
    result = runner.invoke(app, ["scan", "--project", str(sandbox_dir), "--mirror"])
    assert result.exit_code == 0
    
    rtx_dir = sandbox_dir / ".rtx"
    assert rtx_dir.exists()
    assert (rtx_dir / "calculator.py.md").exists()
    assert (rtx_dir / "sample.csv.md").exists()
    
    import shutil
    shutil.rmtree(rtx_dir)

def test_cli_output_file(sandbox_dir):
    runner = CliRunner()
    out_file = sandbox_dir / "cli_out.md"
    result = runner.invoke(app, ["scan", "--project", str(sandbox_dir), "--output", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "# FILE: calculator.py" in content
    out_file.unlink()

def test_cli_git_status(sandbox_dir, monkeypatch):
    # Mock subprocess run to simulate git status
    import subprocess
    original_run = subprocess.run
    
    def mock_run(args, **kwargs):
        class MockCompletedProcess:
            def __init__(self, stdout):
                self.stdout = stdout
                self.returncode = 0
        if "status" in args:
            return MockCompletedProcess(" M calculator.py\n?? untracked.py\n")
        return original_run(args, **kwargs)
        
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Create untracked.py in sandbox_dir
    untracked_path = sandbox_dir / "untracked.py"
    untracked_path.write_text("print('untracked')", encoding="utf-8")
    
    try:
        runner = CliRunner()
        result = runner.invoke(app, ["scan", "--git-status", "--project", str(sandbox_dir)])
        assert result.exit_code == 0
        assert "# FILE: calculator.py" in result.output
        assert "# FILE: untracked.py" in result.output
        assert "sample.docx" not in result.output
    finally:
        if untracked_path.exists():
            untracked_path.unlink()

def test_cli_git_diff(sandbox_dir, monkeypatch):
    import subprocess
    def mock_run(args, **kwargs):
        class MockCompletedProcess:
            def __init__(self, stdout):
                self.stdout = stdout
                self.returncode = 0
        if "diff" in args:
            return MockCompletedProcess("--- a/calculator.py\n+++ b/calculator.py\n@@ -1,1 +1,1 @@\n-def add\n+def addition\n")
        if "status" in args:
            return MockCompletedProcess("?? untracked.py\n")
        return subprocess.CompletedProcess(args, 0, b"", b"")
        
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    untracked_path = sandbox_dir / "untracked.py"
    untracked_path.write_text("print('untracked')", encoding="utf-8")
    
    try:
        runner = CliRunner()
        result = runner.invoke(app, ["scan", "--git-diff", "--project", str(sandbox_dir)])
        assert result.exit_code == 0
        assert "GIT DIFF AND CONTEXT" in result.output
        assert "def addition" in result.output
        assert "untracked.py" in result.output
    finally:
        if untracked_path.exists():
            untracked_path.unlink()

def test_cli_scan_already_indexed_pdf(sandbox_dir):
    # 1. Create a PDF file in sandbox_dir
    pdf_path = sandbox_dir / "test_doc.pdf"
    import fitz
    doc_pdf = fitz.open()
    page = doc_pdf.new_page()
    page.insert_text((50, 50), "PDF content", fontsize=12)
    doc_pdf.save(pdf_path)
    
    # 2. Simulate mirror index of it in .rtx/
    rtx_dir = sandbox_dir / ".rtx"
    rtx_dir.mkdir(exist_ok=True)
    mirror_pdf = rtx_dir / "test_doc.pdf.md"
    mirror_pdf.write_text("Parsed PDF content", encoding="utf-8")
    
    try:
        runner = CliRunner()
        # Confirm "y" to re-scan
        result = runner.invoke(app, ["scan", "test_doc.pdf", "--project", str(sandbox_dir)], input="y\n")
        assert result.exit_code == 0
        assert "Warning: PDF file 'test_doc.pdf' is already indexed in .rtx/." in result.output
        assert "# FILE: test_doc.pdf" in result.output
        
        # Run cli scan and say "n" to re-scan
        result_skip = runner.invoke(app, ["scan", "test_doc.pdf", "--project", str(sandbox_dir)], input="n\n")
        assert "Warning: PDF file 'test_doc.pdf' is already indexed in .rtx/." in result_skip.output
        assert "Skipping already indexed PDF: test_doc.pdf" in result_skip.output
        assert "No files left to process" in result_skip.output
        assert result_skip.exit_code == 0
    finally:
        if pdf_path.exists():
            pdf_path.unlink()
        import shutil
        if rtx_dir.exists():
            shutil.rmtree(rtx_dir)

