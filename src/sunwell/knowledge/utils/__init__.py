"""Knowledge domain utilities.

RFC-138: Module Architecture Consolidation

Provides code parsing, AST manipulation, and file scanning utilities
specific to the knowledge domain.
"""

from sunwell.knowledge.utils.ast import extract_class_defs, extract_function_defs
from sunwell.knowledge.utils.parsing import is_python_file, parse_python_file
from sunwell.knowledge.utils.scanner import scan_code_files, scan_directory

__all__ = [
    # AST utilities
    "extract_function_defs",
    "extract_class_defs",
    # Parsing utilities
    "is_python_file",
    "parse_python_file",
    # Scanner utilities
    "scan_code_files",
    "scan_directory",
]
