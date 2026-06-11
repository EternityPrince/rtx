import sys
from pathlib import Path
from typing import List, Optional
from rtx.pipeline import ParseResult

def update_gitignore(root_path: Path):
    """
    Ensures that the .rtx/ folder is ignored in the project's .gitignore.
    Creates .gitignore if it doesn't exist.
    """
    gitignore_path = root_path / ".gitignore"
    if not gitignore_path.exists():
        try:
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write("# RTX context directory\n.rtx/\n")
            return
        except Exception:
            return  # Fail silently or log if cannot write
            
    try:
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        lines = content.splitlines()
        has_rtx = False
        for line in lines:
            cleaned = line.strip().split("#")[0].strip()  # Strip comments
            if cleaned in (".rtx", ".rtx/", ".rtx/*"):
                has_rtx = True
                break
                
        if not has_rtx:
            # Append .rtx/ to the file
            if content and not content.endswith("\n"):
                with open(gitignore_path, "a", encoding="utf-8") as f:
                    f.write("\n.rtx/\n")
            else:
                with open(gitignore_path, "a", encoding="utf-8") as f:
                    f.write(".rtx/\n")
    except Exception:
        pass

def write_stream(results: List[ParseResult], root_path: Path, output_file: Optional[Path] = None):
    """
    Scenario A: Writes all successfully parsed files into a single stream.
    Outputs to sys.stdout (default) or a specified file path.
    """
    root_path = root_path.resolve()
    out = sys.stdout
    if output_file:
        try:
            out = open(output_file, "w", encoding="utf-8")
        except Exception as e:
            raise RuntimeError(f"Could not open output file {output_file}: {e}")
            
    try:
        markdown_content = []
        for res in results:
            if res.status != "Success":
                continue
                
            try:
                rel_path = res.path.relative_to(root_path)
            except ValueError:
                rel_path = res.path
                
            block = f"# FILE: {rel_path}\n---\n{res.text}\n\n"
            out.write(block)
            if not output_file:
                markdown_content.append(block)
                
        if not output_file and markdown_content:
            import pyperclip
            try:
                pyperclip.copy("".join(markdown_content))
            except Exception:
                pass  # Ignore clipboard errors on headless systems
    finally:
        if output_file and out is not sys.stdout:
            out.close()

def write_mirror(results: List[ParseResult], root_path: Path):
    """
    Scenario B: Replicates the workspace structure inside the hidden .rtx/ directory,
    writing all extracted texts as .md files.
    """
    root_path = root_path.resolve()
    rtx_root = root_path / ".rtx"
    rtx_root.mkdir(exist_ok=True)
    
    # Keep gitignore updated
    update_gitignore(root_path)
    
    for res in results:
        if res.status != "Success":
            continue
            
        try:
            rel_path = res.path.relative_to(root_path)
        except ValueError:
            rel_path = Path(res.path.name)
            
        # Append .md to the filename to preserve original extension and avoid collisions
        target_path = rtx_root / rel_path.with_name(rel_path.name + ".md")
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(res.text)
        except Exception as e:
            # Continue on individual write failures
            pass
