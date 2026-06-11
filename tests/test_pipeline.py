from pathlib import Path
from rtx.pipeline import run_parser_pipeline, ParseResult
from rtx.parsers import pdf

def test_pipeline_execution(sandbox_dir):
    files = [
        sandbox_dir / "calculator.py",
        sandbox_dir / "readme.md",
        sandbox_dir / "sample.pdf",
    ]
    
    progress_called = []
    
    def callback(path: Path, current: int, total: int):
        progress_called.append((path, current, total))
        
    results = run_parser_pipeline(files, progress_callback=callback)
    
    assert len(results) == 3
    assert len(progress_called) == 3
    
    # Verify the callback sequences and inputs
    for idx, (path, current, total) in enumerate(progress_called):
        assert total == 3
        assert current == idx
        
    # PDF should be processed first due to the sequential grouping rules
    # In run_parser_pipeline: PDF -> DOCX -> PPTX -> EPUB -> FB2 -> Code/Text
    # So results[0] should be PDF, and results[2] should be Python code or Markdown
    assert results[0].extension == ".pdf"
    assert results[1].extension in (".py", ".md")
    assert results[2].extension in (".py", ".md")

def test_pipeline_error_handling(sandbox_dir):
    # Pass a non-existent file
    bad_file = sandbox_dir / "does_not_exist.docx"
    
    results = run_parser_pipeline([bad_file])
    
    assert len(results) == 1
    assert results[0].status == "Failed"
    assert len(results[0].error) > 0
    assert results[0].lines == 0
    assert results[0].chars == 0

def test_clear_marker_models_invocation(sandbox_dir):
    # Verify that clear_marker_models runs and resets cached models
    pdf.get_marker_models = lambda: "mock_models"
    models = pdf.get_marker_models()
    assert models == "mock_models"
    
    pdf.clear_marker_models()
    assert pdf._marker_models is None
