from abc import ABC, abstractmethod
from pathlib import Path

class BaseParser(ABC):
    @abstractmethod
    def parse(self, path: Path) -> str:
        """
        Parses a file and returns its content as a clean Markdown string.
        Should raise an exception on failure.
        """
        pass
