import gc
import logging
from pathlib import Path
from rtx.parsers.base import BaseParser

logger = logging.getLogger(__name__)

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
    except Exception as e:
        logger.debug(f"Failed to clear PyTorch cache: {e}")

def get_safe_markdown_fence(content: str) -> str:
    """
    Finds the maximum sequence of backticks in the content
    and returns a fence string that is at least 3 backticks long,
    and at least one backtick longer than any backtick sequence in the content.
    """
    import re
    backticks = re.findall(r'`+', content)
    max_backticks = max(len(b) for b in backticks) if backticks else 0
    fence_length = max(3, max_backticks + 1)
    return "`" * fence_length

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
            logger.debug(
                f"marker-pdf failed for {path.name}, falling back to PyMuPDF. Error: {e}"
            )
            
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
        except Exception as e:
            logger.debug(
                f"PyMuPDF failed for {path.name}, falling back to pypdf. Error: {e}"
            )

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
            logger.debug(f"pypdf failed for {path.name}: {e}")
            raise RuntimeError(f"PDF parsing failed for {path.name}: {str(e)}")
        
        return ""

