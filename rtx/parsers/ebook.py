import warnings
from pathlib import Path
from rtx.parsers.base import BaseParser

class EbookParser(BaseParser):
    def parse(self, path: Path) -> str:
        # Suppress ebooklib and beautifulsoup warnings
        warnings.filterwarnings("ignore", category=UserWarning)
        warnings.filterwarnings("ignore", category=FutureWarning)
        
        suffix = path.suffix.lower()
        if suffix == ".epub":
            return self._parse_epub(path)
        elif suffix == ".fb2":
            return self._parse_fb2(path)
        else:
            raise ValueError(f"Unsupported ebook extension: {suffix}")

    def _parse_epub(self, path: Path) -> str:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup
        
        book = epub.read_epub(path)
        markdown_sections = []
        
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                html_content = item.get_content()
                soup = BeautifulSoup(html_content, "html.parser")
                
                # Simple HTML to Markdown conversion
                for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
                    level = int(heading.name[1])
                    heading.replace_with(f"\n{'#' * level} {heading.get_text().strip()}\n")
                
                for p in soup.find_all("p"):
                    p.replace_with(f"\n{p.get_text().strip()}\n")
                    
                for li in soup.find_all("li"):
                    li.replace_with(f"* {li.get_text().strip()}\n")
                
                text = soup.get_text()
                # Clean up multiple empty lines
                cleaned_text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
                if cleaned_text:
                    markdown_sections.append(cleaned_text)
                    
        return "\n\n".join(markdown_sections).strip()

    def _parse_fb2(self, path: Path) -> str:
        from bs4 import BeautifulSoup
        
        with open(path, "rb") as f:
            xml_content = f.read()
            
        soup = BeautifulSoup(xml_content, "xml")
        
        # In FB2 XML:
        # <title-info> -> Book Title, Authors
        # <section> -> Chapters
        # <title> -> Chapter Headings
        # <p> -> Paragraphs
        
        for title in soup.find_all("title"):
            title.replace_with(f"\n## {title.get_text().strip()}\n")
            
        for p in soup.find_all("p"):
            p.replace_with(f"\n{p.get_text().strip()}\n")
            
        text = soup.get_text()
        cleaned_text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
        return cleaned_text.strip()
