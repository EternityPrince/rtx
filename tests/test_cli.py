from typer.testing import CliRunner
from rtx.cli import app

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "--tui" in result.output
    assert "--mirror" in result.output

def test_cli_scan(sandbox_dir):
    runner = CliRunner()
    result = runner.invoke(app, [str(sandbox_dir)])
    assert result.exit_code == 0
    # Check that calculator.py boundary is in the output stream
    assert "# FILE: calculator.py" in result.output
    # Check that docx parsed headers are there
    assert "Heading 1 Test" in result.output

def test_cli_mirror_mode(sandbox_dir):
    runner = CliRunner()
    result = runner.invoke(app, [str(sandbox_dir), "--mirror"])
    assert result.exit_code == 0
    
    rtx_dir = sandbox_dir / ".rtx"
    assert rtx_dir.exists()
    assert (rtx_dir / "calculator.py.md").exists()
    
    import shutil
    shutil.rmtree(rtx_dir)

def test_cli_output_file(sandbox_dir):
    runner = CliRunner()
    out_file = sandbox_dir / "cli_out.md"
    result = runner.invoke(app, [str(sandbox_dir), "--output", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "# FILE: calculator.py" in content
    out_file.unlink()
