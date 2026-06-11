import gc
from pathlib import Path
from rtx.parsers.base import BaseParser

# Module-level variable to cache marker models
_marker_models = None

def get_marker_models():
    """Lazily load and cache marker models."""
    global _marker_models
    if _marker_models is None:
        # Lazy imports for heavy ML libraries
        from marker.models import load_all_models
        _marker_models = load_all_models()
    return _marker_models

def clear_marker_models():
    """Unload marker models and free RAM/VRAM cache."""
    global _marker_models
    if _marker_models is not None:
        del _marker_models
        _marker_models = None
        
    # Run garbage collection
    gc.collect()
    
    # Empty PyTorch caches if torch is loaded
    try:
        import sys
        if "torch" in sys.modules:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if hasattr(torch, "mps") and torch.mps.is_available():
                torch.mps.empty_cache()
    except Exception:
        pass

class PdfParser(BaseParser):
    def parse(self, path: Path) -> str:
        # 1. Attempt marker-pdf parsing
        try:
            from marker.convert import convert_single_pdf
            models = get_marker_models()
            full_text, _, _ = convert_single_pdf(str(path.resolve()), models)
            if full_text and full_text.strip():
                return full_text.strip()
        except Exception as e:
            # Fallback to PyMuPDF or PyPDF if marker fails or is not available
            pass
            
        # 2. Fallback to PyMuPDF (extremely fast, good layout)
        try:
            import fitz
            doc = fitz.open(path)
            pages = []
            for page in doc:
                t = page.get_text()
                if t:
                    pages.append(t)
            if pages:
                return "\n".join(pages).strip()
        except Exception:
            pass

        # 3. Fallback to PyPDF
        try:
            from pypdf import PdfReader
            reader = PdfReader(path)
            pages = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    pages.append(t)
            if pages:
                return "\n".join(pages).strip()
        except Exception as e:
            raise RuntimeError(f"PDF parsing failed for {path.name}: {str(e)}")
        
        return ""
