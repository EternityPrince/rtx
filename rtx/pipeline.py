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
    Runs the parsing pipeline:
    1. PDF (sequentially using marker-pdf, then unloading the models to prevent OOM)
    2. Other files (parallelized via ThreadPoolExecutor)
    """
    results: List[ParseResult] = []
    total_files = len(file_paths)
    processed_count = 0
    
    # 1. Process PDF batch first and sequentially
    pdf_paths = [p for p in file_paths if p.suffix.lower() == ".pdf"]
    for path in pdf_paths:
        if progress_callback:
            progress_callback(path, processed_count, total_files)
        import time
        start_time = time.perf_counter()
        try:
            parser = get_parser_for_path(path)
            markdown_text = parser.parse(path)
            duration = time.perf_counter() - start_time
            results.append(ParseResult(
                path=path,
                extension=".pdf",
                text=markdown_text,
                status="Success",
                duration=duration
            ))
        except Exception as e:
            duration = time.perf_counter() - start_time
            results.append(ParseResult(
                path=path,
                extension=".pdf",
                status="Failed",
                error=str(e),
                duration=duration
            ))
        processed_count += 1
        
    clear_marker_models()
    
    # 2. Process all other files in parallel using ThreadPoolExecutor
    other_paths = [p for p in file_paths if p.suffix.lower() != ".pdf"]
    if other_paths:
        import threading
        import os
        from concurrent.futures import ThreadPoolExecutor
        
        lock = threading.Lock()
        
        def parse_file(path: Path) -> ParseResult:
            nonlocal processed_count
            suffix = path.suffix.lower()
            
            with lock:
                current_idx = processed_count
                processed_count += 1
                
            if progress_callback:
                progress_callback(path, current_idx, total_files)
                
            import time
            start_time = time.perf_counter()
            try:
                parser = get_parser_for_path(path)
                markdown_text = parser.parse(path)
                duration = time.perf_counter() - start_time
                return ParseResult(
                    path=path,
                    extension=suffix,
                    text=markdown_text,
                    status="Success",
                    duration=duration
                )
            except Exception as e:
                duration = time.perf_counter() - start_time
                return ParseResult(
                    path=path,
                    extension=suffix,
                    status="Failed",
                    error=str(e),
                    duration=duration
                )
                
        # Run in thread pool
        max_workers = min(32, (os.cpu_count() or 1) + 4)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_results = list(executor.map(parse_file, other_paths))
            results.extend(future_results)
            
    return results
