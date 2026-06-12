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
        import os
        import sys
        from contextlib import redirect_stdout, redirect_stderr
        with open(os.devnull, "w") as fnull:
            with redirect_stdout(fnull), redirect_stderr(fnull):
                from marker.models import create_model_dict
                _marker_models = create_model_dict()
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

def process_and_compress_image(img, max_dim: int = 1024, quality: int = 50) -> str:
    """
    Resizes the PIL Image if its maximum dimension exceeds max_dim,
    converts it to RGB (handling transparency by putting it on white background),
    compresses it as JPEG with the given quality,
    and returns the base64 data URI string.
    """
    import io
    import base64
    from PIL import Image

    # 1. Resize if too large
    width, height = img.size
    if max(width, height) > max_dim:
        ratio = max_dim / max(width, height)
        new_size = (int(width * ratio), int(height * ratio))
        resample_filter = getattr(Image, "Resampling", None)
        if resample_filter is not None:
            img = img.resize(new_size, resample_filter.LANCZOS)
        else:
            img = img.resize(new_size, Image.ANTIALIAS)

    # 2. Convert to RGB to save as JPEG
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "RGBA":
            background.paste(img, mask=img.split()[-1])
        else:
            background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # 3. Compress to JPEG
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    img_bytes = buf.getvalue()

    # 4. Base64 encode
    encoded = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"

class PdfParser(BaseParser):
    def parse(self, path: Path) -> str:
        # 1. Attempt marker-pdf parsing
        try:
            import os
            import sys
            import re
            from contextlib import redirect_stdout, redirect_stderr
            from marker.converters.pdf import PdfConverter
            
            models = get_marker_models()
            with open(os.devnull, "w") as fnull:
                with redirect_stdout(fnull), redirect_stderr(fnull):
                    converter = PdfConverter(artifact_dict=models)
                    rendered = converter(str(path.resolve()))
                    full_text = rendered.markdown
                    images = getattr(rendered, "images", {})
            
            if full_text is not None:
                footer_entries = []
                if images:
                    for img_name, img_obj in images.items():
                        try:
                            data_uri = process_and_compress_image(img_obj)
                            footer_entries.append(f"[{img_name}]: {data_uri}")
                            # Replace standard markdown image reference: ![alt](img_name) -> ![alt][img_name]
                            pattern = r'!\[(.*?)\]\(' + re.escape(img_name) + r'\)'
                            full_text = re.sub(pattern, r'![\1][' + img_name + r']', full_text)
                        except Exception as img_err:
                            logger.debug(f"Failed to process marker image {img_name}: {img_err}")
                
                full_text = full_text.strip()
                if footer_entries:
                    full_text += "\n\n" + "\n".join(footer_entries)
                if full_text:
                    return full_text
        except Exception as e:
            logger.debug(
                f"marker-pdf failed for {path.name}, falling back to PyMuPDF. Error: {e}"
            )
            
        # 2. Fallback to PyMuPDF (extremely fast, good layout)
        try:
            import fitz
            from PIL import Image
            import io
            doc = fitz.open(path)
            pages = []
            footer_entries = []
            xref_to_ref = {}
            
            for page_index in range(len(doc)):
                page = doc[page_index]
                t = page.get_text()
                
                # Extract images from this page
                page_images = page.get_images(full=True)
                img_refs = []
                for img_info in page_images:
                    try:
                        xref = img_info[0]
                        if xref in xref_to_ref:
                            ref_name = xref_to_ref[xref]
                        else:
                            base_image = doc.extract_image(xref)
                            img_bytes = base_image["image"]
                            
                            img_obj = Image.open(io.BytesIO(img_bytes))
                            data_uri = process_and_compress_image(img_obj)
                            ref_name = f"image_{xref}"
                            footer_entries.append(f"[{ref_name}]: {data_uri}")
                            xref_to_ref[xref] = ref_name
                        
                        img_refs.append(f"![][{ref_name}]")
                    except Exception as img_err:
                        logger.debug(
                            f"Failed to extract image xref {xref} on page {page_index}: {img_err}"
                        )
                
                page_content = t if t else ""
                if img_refs:
                    page_content += "\n\n" + "\n".join(img_refs)
                if page_content:
                    pages.append(page_content)
                    
            if pages:
                full_text = "\n".join(pages).strip()
                if footer_entries:
                    full_text += "\n\n" + "\n".join(footer_entries)
                return full_text
        except Exception as e:
            logger.debug(
                f"PyMuPDF failed for {path.name}, falling back to pypdf. Error: {e}"
            )

        # 3. Fallback to PyPDF
        try:
            from pypdf import PdfReader
            from PIL import Image
            import io
            import hashlib
            reader = PdfReader(path)
            pages = []
            footer_entries = []
            data_hash_to_ref = {}
            
            for page_index, page in enumerate(reader.pages):
                t = page.extract_text()
                img_refs = []
                
                try:
                    for img_file_object in page.images:
                        try:
                            img_bytes = img_file_object.data
                            h = hashlib.md5(img_bytes).hexdigest()[:16]
                            if h in data_hash_to_ref:
                                ref_name = data_hash_to_ref[h]
                            else:
                                img_obj = Image.open(io.BytesIO(img_bytes))
                                data_uri = process_and_compress_image(img_obj)
                                ref_name = f"image_{h}"
                                footer_entries.append(f"[{ref_name}]: {data_uri}")
                                data_hash_to_ref[h] = ref_name
                            
                            img_refs.append(f"![][{ref_name}]")
                        except Exception as img_err:
                            logger.debug(
                                f"Failed to extract page.images item in pypdf: {img_err}"
                            )
                except Exception as page_imgs_err:
                    logger.debug(
                        f"Failed to get page.images in pypdf: {page_imgs_err}"
                    )
                    
                page_content = t if t else ""
                if img_refs:
                    page_content += "\n\n" + "\n".join(img_refs)
                if page_content:
                    pages.append(page_content)
                    
            if pages:
                full_text = "\n".join(pages).strip()
                if footer_entries:
                    full_text += "\n\n" + "\n".join(footer_entries)
                return full_text
        except Exception as e:
            logger.debug(f"pypdf failed for {path.name}: {e}")
            raise RuntimeError(f"PDF parsing failed for {path.name}: {str(e)}")
        
        return ""

