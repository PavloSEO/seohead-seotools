"""Report writers. JSON is the contract; Markdown is its human projection."""

from .jsonfile import write_json
from .md import write_markdown

__all__ = ["write_json", "write_markdown"]
