import gc
from pathlib import Path
from typing import List, Dict, Tuple, Any, Callable, Optional
from rtx.parsers import get_parser_for_path, clear_marker_models

class ParseResult:
    def __init__(self, path: Path, extension: str, text: str = "", status: str = "Success", error: str = "", duration: float = 0.0):
        self.path = path
        self.extension = extension
        self.text = text
        self.status = status  # "Success" or "Failed"
        self.error = error
        self.duration = duration
        
        # Calculate metrics of the extracted markdown content
        if status == "Success":
            self.lines = text.count("\n") + 1 if text else 0
            self.chars = len(text)
        else:
            self.lines = 0
            self.chars = 0

def run_parser_pipeline(
    file_paths: List[Path], 
    progress_callback: Optional[Callable[[Path, int, int], None]] = None
) -> List[ParseResult]:
    """
    Runs the parsing pipeline sequentially grouped by extensions:
    1. PDF (using marker-pdf, then unloading the models to prevent OOM)
    2. DOCX
    3. PPTX
    4. EPUB
    5. FB2
    6. Code and Text
    """
    pdf_files = []
    docx_files = []
    pptx_files = []
    epub_files = []
    fb2_files = []
    code_text_files = []
    
    for p in file_paths:
        suffix = p.suffix.lower()
        if suffix == ".pdf":
            pdf_files.append(p)
        elif suffix == ".docx":
            docx_files.append(p)
        elif suffix == ".pptx":
            pptx_files.append(p)
        elif suffix == ".epub":
            epub_files.append(p)
        elif suffix == ".fb2":
            fb2_files.append(p)
        else:
            code_text_files.append(p)
            
    # Execution batches in sequence
    batches = [
        ("PDF", pdf_files),
        ("DOCX", docx_files),
        ("PPTX", pptx_files),
        ("EPUB", epub_files),
        ("FB2", fb2_files),
        ("Code/Text", code_text_files),
    ]
    
    results: List[ParseResult] = []
    total_files = len(file_paths)
    processed_count = 0
    
    for batch_name, paths in batches:
        if not paths:
            continue
            
        for path in paths:
            if progress_callback:
                progress_callback(path, processed_count, total_files)
                
            suffix = path.suffix.lower()
            import time
            start_time = time.perf_counter()
            try:
                parser = get_parser_for_path(path)
                markdown_text = parser.parse(path)
                duration = time.perf_counter() - start_time
                results.append(ParseResult(
                    path=path,
                    extension=suffix,
                    text=markdown_text,
                    status="Success",
                    duration=duration
                ))
            except Exception as e:
                duration = time.perf_counter() - start_time
                results.append(ParseResult(
                    path=path,
                    extension=suffix,
                    status="Failed",
                    error=str(e),
                    duration=duration
                ))
            processed_count += 1
            
        # Clean up marker models immediately after the PDF batch completes to prevent OOM
        if batch_name == "PDF":
            clear_marker_models()
            
    return results
