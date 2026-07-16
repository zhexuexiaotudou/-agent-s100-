"""ACL-aware, virtual document classification for the Digua file UI."""

from .classifier import DOCUMENT_CATEGORIES, classify_directory, classify_file

__all__ = ["DOCUMENT_CATEGORIES", "classify_directory", "classify_file"]
