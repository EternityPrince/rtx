from pathlib import Path
from rtx.digger import DiggerEngine, is_excluded_path, is_binary_content, format_bytes

def test_binary_detection(sandbox_dir):
    assert is_binary_content(sandbox_dir / "image.png") is True
    assert is_binary_content(sandbox_dir / "unknown.dat") is True
    assert is_binary_content(sandbox_dir / "calculator.py") is False

def test_exclusion_logic(sandbox_dir):
    # Valid files
    assert is_excluded_path(sandbox_dir / "calculator.py", sandbox_dir) is False
    assert is_excluded_path(sandbox_dir / "readme.md", sandbox_dir) is False
    assert is_excluded_path(sandbox_dir / "sample.pdf", sandbox_dir) is False
    
    # Excluded files/folders
    assert is_excluded_path(sandbox_dir / "node_modules", sandbox_dir) is True
    assert is_excluded_path(sandbox_dir / "node_modules" / "index.js", sandbox_dir) is True
    assert is_excluded_path(sandbox_dir / ".git", sandbox_dir) is True
    assert is_excluded_path(sandbox_dir / "image.png", sandbox_dir) is True
    assert is_excluded_path(sandbox_dir / "unknown.dat", sandbox_dir) is True

def test_digger_scanning(sandbox_dir):
    digger = DiggerEngine(sandbox_dir)
    files = list(digger.scan_valid_files())
    filenames = [f.name for f in files]
    
    # Check we have exactly our 8 valid files (including sample.csv and sample.xlsx)
    assert len(files) == 8
    assert "calculator.py" in filenames
    assert "readme.md" in filenames
    assert "sample.docx" in filenames
    assert "sample.pptx" in filenames
    assert "sample.pdf" in filenames
    assert "sample.epub" in filenames
    assert "sample.csv" in filenames
    assert "sample.xlsx" in filenames

def test_metrics_calculation(sandbox_dir):
    digger = DiggerEngine(sandbox_dir)
    
    # Test file metrics
    files, lines, chars, bytes_sz = digger.calculate_metrics(sandbox_dir / "calculator.py")
    assert files == 1
    assert lines == 3
    assert chars > 0
    assert bytes_sz == (sandbox_dir / "calculator.py").stat().st_size
    
    # Test directory metrics (which counts all children recursively)
    dir_files, dir_lines, dir_chars, dir_bytes = digger.calculate_metrics(sandbox_dir)
    assert dir_files == 8
    assert dir_lines > 0
    assert dir_chars > 0
    assert dir_bytes > 0
    
    # Verify caching
    assert sandbox_dir in digger.metrics_cache

def test_format_bytes():
    assert format_bytes(500) == "500 B"
    assert format_bytes(1024) == "1.0 KiB"
    assert format_bytes(1024 * 1024 * 2.5) == "2.5 MiB"

def test_rtxignore(sandbox_dir):
    ignore_file = sandbox_dir / ".rtxignore"
    ignore_file.write_text("*.docx\ncalculator.py\n", encoding="utf-8")
    try:
        digger = DiggerEngine(sandbox_dir)
        files = list(digger.scan_valid_files())
        filenames = [f.name for f in files]
        assert "calculator.py" not in filenames
        assert "sample.docx" not in filenames
        assert "readme.md" in filenames
    finally:
        if ignore_file.exists():
            ignore_file.unlink()

def test_scan_targets(sandbox_dir):
    digger = DiggerEngine(sandbox_dir)
    files = list(digger.scan_targets(["calculator.py"]))
    assert len(files) == 1
    assert files[0].name == "calculator.py"
    
    files_dir = list(digger.scan_targets(["."]))
    assert len(files_dir) == 8
    
    files_glob = list(digger.scan_targets(["*.py"]))
    assert len(files_glob) == 1
    assert files_glob[0].name == "calculator.py"
