from pathlib import Path
from rtx.pipeline import ParseResult
from rtx.writer import update_gitignore, write_stream, write_mirror

def test_gitignore_creation(sandbox_dir):
    gi = sandbox_dir / ".gitignore"
    if gi.exists():
        gi.unlink()
        
    update_gitignore(sandbox_dir)
    assert gi.exists()
    content = gi.read_text(encoding="utf-8")
    assert ".rtx/" in content
    
    # Run again, verify no duplicate entries
    update_gitignore(sandbox_dir)
    content2 = gi.read_text(encoding="utf-8")
    assert content2.count(".rtx/") == 1

def test_write_stream(sandbox_dir):
    results = [
        ParseResult(sandbox_dir / "calculator.py", ".py", "print('hello')", "Success"),
        ParseResult(sandbox_dir / "readme.md", ".md", "# readme", "Success"),
        ParseResult(sandbox_dir / "failed.py", ".py", "", "Failed", "Some error"),
    ]
    
    out_file = sandbox_dir / "stream_output.md"
    write_stream(results, sandbox_dir, output_file=out_file)
    
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    
    assert "# FILE: calculator.py" in content
    assert "print('hello')" in content
    assert "# FILE: readme.md" in content
    assert "# readme" in content
    # Failed files should NOT be in the output stream
    assert "failed.py" not in content
    
    out_file.unlink()

def test_write_mirror(sandbox_dir):
    results = [
        ParseResult(sandbox_dir / "calculator.py", ".py", "print('hello')", "Success"),
        ParseResult(sandbox_dir / "readme.md", ".md", "# readme", "Success"),
    ]
    
    rtx_dir = sandbox_dir / ".rtx"
    if rtx_dir.exists():
        import shutil
        shutil.rmtree(rtx_dir)
        
    write_mirror(results, sandbox_dir)
    
    assert rtx_dir.exists()
    assert (rtx_dir / "calculator.py.md").exists()
    assert (rtx_dir / "readme.md.md").exists()
    
    assert (rtx_dir / "calculator.py.md").read_text(encoding="utf-8") == "print('hello')"
    assert (rtx_dir / "readme.md.md").read_text(encoding="utf-8") == "# readme"
    
    import shutil
    shutil.rmtree(rtx_dir)
