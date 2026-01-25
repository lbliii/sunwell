"""AST manipulation utilities for code analysis.

RFC-138: Module Architecture Consolidation

Provides helpers for extracting information from Python ASTs.
"""

import ast
from collections.abc import Callable


def extract_function_defs(node: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Extract all function definitions from an AST node.

    Args:
        node: AST node (Module, ClassDef, or FunctionDef)

    Returns:
        List of function definition nodes

    Example:
        >>> tree = ast.parse("def foo(): pass\\nclass Bar:\\n  def baz(): pass")
        >>> funcs = extract_function_defs(tree)
        >>> len(funcs)
        1  # Only top-level functions
    """
    functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    class FunctionVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            functions.append(node)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            functions.append(node)
            self.generic_visit(node)

    visitor = FunctionVisitor()
    visitor.visit(node)
    return functions


def extract_class_defs(node: ast.AST) -> list[ast.ClassDef]:
    """Extract all class definitions from an AST node.

    Args:
        node: AST node (Module or ClassDef)

    Returns:
        List of class definition nodes

    Example:
        >>> tree = ast.parse("class Foo: pass\\nclass Bar: pass")
        >>> classes = extract_class_defs(tree)
        >>> len(classes)
        2
    """
    classes: list[ast.ClassDef] = []

    class ClassVisitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            classes.append(node)
            self.generic_visit(node)

    visitor = ClassVisitor()
    visitor.visit(node)
    return classes


def extract_nodes_by_type[T: ast.AST](
    node: ast.AST,
    node_type: type[T],
    predicate: Callable[[T], bool] | None = None,
) -> list[T]:
    """Extract nodes of a specific type, optionally filtered by predicate.

    Args:
        node: AST node to search
        node_type: Type of nodes to extract
        predicate: Optional filter function

    Returns:
        List of matching nodes

    Example:
        >>> tree = ast.parse("x = 1\\ny = 2")
        >>> assigns = extract_nodes_by_type(tree, ast.Assign)
        >>> len(assigns)
        2
    """
    nodes: list[T] = []

    class TypeVisitor(ast.NodeVisitor):
        def visit(self, n: ast.AST) -> None:
            if isinstance(n, node_type):
                if predicate is None or predicate(n):
                    nodes.append(n)
            self.generic_visit(n)

    visitor = TypeVisitor()
    visitor.visit(node)
    return nodes
