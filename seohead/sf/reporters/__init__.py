"""Report writers. JSON is the contract; Markdown is its human projection."""

from .json_reporter import write_json
from .md_reporter import write_markdown

__all__ = ["write_json", "write_markdown"]
