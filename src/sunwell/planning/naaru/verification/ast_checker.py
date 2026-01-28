"""AST-based Protocol method extraction and implementation checking.

Uses Python's ast module to:
1. Extract method signatures from Protocol classes
2. Verify implementation classes have matching methods
"""

import ast
from pathlib import Path

from sunwell.planning.naaru.verification.types import (
    MethodMismatch,
    MethodSignature,
    ProtocolInfo,
)


def _get_annotation_str(node: ast.expr | None) -> str:
    """Convert an AST annotation node to a string representation."""
    if node is None:
        return ""

    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Constant):
        return str(node.value) if node.value is not None else "None"
    elif isinstance(node, ast.Subscript):
        # Handle generic types like list[str], dict[str, int]
        value = _get_annotation_str(node.value)
        slice_val = _get_annotation_str(node.slice)
        return f"{value}[{slice_val}]"
    elif isinstance(node, ast.Tuple):
        # Handle tuple subscripts like dict[str, int]
        elts = ", ".join(_get_annotation_str(e) for e in node.elts)
        return elts
    elif isinstance(node, ast.Attribute):
        # Handle qualified names like typing.Optional
        value = _get_annotation_str(node.value)
        return f"{value}.{node.attr}"
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        # Handle union types like str | None
        left = _get_annotation_str(node.left)
        right = _get_annotation_str(node.right)
        return f"{left} | {right}"
    elif isinstance(node, ast.List):
        # Handle list literals in annotations
        elts = ", ".join(_get_annotation_str(e) for e in node.elts)
        return f"[{elts}]"
    else:
        # Fallback: try to get source segment or use repr
        return ast.dump(node)


def _extract_method_signature(
    func_def: ast.FunctionDef | ast.AsyncFunctionDef,
    is_property: bool = False,
) -> MethodSignature:
    """Extract a MethodSignature from an AST function definition."""
    # Get parameter names and types (skip 'self')
    params = []
    param_types = []

    for arg in func_def.args.args:
        if arg.arg == "self":
            continue
        params.append(arg.arg)
        param_types.append(_get_annotation_str(arg.annotation))

    # Get return type
    return_type = _get_annotation_str(func_def.returns) if func_def.returns else None

    return MethodSignature(
        name=func_def.name,
        parameters=tuple(params),
        parameter_types=tuple(param_types),
        return_type=return_type,
        is_async=isinstance(func_def, ast.AsyncFunctionDef),
        is_property=is_property,
    )


def _is_protocol_class(class_def: ast.ClassDef) -> bool:
    """Check if a class definition is a Protocol."""
    for base in class_def.bases:
        base_name = _get_annotation_str(base)
        if base_name in ("Protocol", "typing.Protocol", "typing_extensions.Protocol"):
            return True
    return False


def _has_property_decorator(decorators: list[ast.expr]) -> bool:
    """Check if decorators include @property."""
    for dec in decorators:
        if isinstance(dec, ast.Name) and dec.id == "property":
            return True
        if isinstance(dec, ast.Attribute) and dec.attr == "property":
            return True
    return False


def extract_protocol_methods(source: str, protocol_name: str) -> list[MethodSignature]:
    """Parse source code and extract method signatures from a Protocol class.

    Args:
        source: Python source code containing the Protocol
        protocol_name: Name of the Protocol class to extract

    Returns:
        List of MethodSignature objects for all methods in the Protocol

    Raises:
        ValueError: If the Protocol class is not found
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise ValueError(f"Failed to parse source: {e}") from e

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == protocol_name:
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Skip dunder methods except __init__
                    if item.name.startswith("__") and item.name != "__init__":
                        continue
                    is_property = _has_property_decorator(item.decorator_list)
                    methods.append(_extract_method_signature(item, is_property))
            return methods

    raise ValueError(f"Protocol '{protocol_name}' not found in source")


def extract_protocol_info(source: str, protocol_name: str) -> ProtocolInfo:
    """Extract full Protocol information from source code.

    Args:
        source: Python source code containing the Protocol
        protocol_name: Name of the Protocol class to extract

    Returns:
        ProtocolInfo with methods, bases, and docstring

    Raises:
        ValueError: If the Protocol class is not found
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise ValueError(f"Failed to parse source: {e}") from e

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == protocol_name:
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name.startswith("__") and item.name != "__init__":
                        continue
                    is_property = _has_property_decorator(item.decorator_list)
                    methods.append(_extract_method_signature(item, is_property))

            bases = [_get_annotation_str(base) for base in node.bases]
            docstring = ast.get_docstring(node)

            return ProtocolInfo(
                name=protocol_name,
                methods=methods,
                bases=bases,
                docstring=docstring,
            )

    raise ValueError(f"Protocol '{protocol_name}' not found in source")


def extract_class_methods(source: str, class_name: str | None = None) -> list[MethodSignature]:
    """Extract method signatures from a class in source code.

    Args:
        source: Python source code containing the class
        class_name: Name of the class to extract (if None, extracts first class found)

    Returns:
        List of MethodSignature objects for all methods in the class

    Raises:
        ValueError: If no class is found or specified class not found
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise ValueError(f"Failed to parse source: {e}") from e

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if class_name is not None and node.name != class_name:
                continue

            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name.startswith("__") and item.name != "__init__":
                        continue
                    is_property = _has_property_decorator(item.decorator_list)
                    methods.append(_extract_method_signature(item, is_property))
            return methods

    if class_name:
        raise ValueError(f"Class '{class_name}' not found in source")
    raise ValueError("No class found in source")


def find_implementing_class(source: str, protocol_name: str) -> str | None:
    """Find a class that appears to implement the given Protocol.

    Looks for classes that:
    1. Have the Protocol in their bases
    2. Have a name ending with the Protocol name (minus 'Protocol')
    3. Have matching method signatures

    Args:
        source: Python source code
        protocol_name: Name of the Protocol to find implementation of

    Returns:
        Name of the implementing class, or None if not found
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    # Derive expected implementation name from protocol name
    impl_name_hint = protocol_name.replace("Protocol", "")

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Skip if it's a Protocol itself
            if _is_protocol_class(node):
                continue

            # Check if Protocol is in bases
            for base in node.bases:
                base_name = _get_annotation_str(base)
                if protocol_name in base_name:
                    return node.name

            # Check if class name matches hint
            if impl_name_hint and impl_name_hint in node.name:
                return node.name

    return None


def check_implementation_satisfies(
    impl_source: str,
    impl_class_name: str | None,
    required_methods: list[MethodSignature],
) -> list[MethodMismatch]:
    """Check if an implementation has all required methods from a Protocol.

    Args:
        impl_source: Source code of the implementation
        impl_class_name: Name of the implementing class (auto-detected if None)
        required_methods: Method signatures required by the Protocol

    Returns:
        List of MethodMismatch objects describing issues (empty if all satisfied)
    """
    mismatches = []

    # Find the implementing class
    if impl_class_name is None:
        impl_class_name = find_implementing_class(impl_source, "")
        if impl_class_name is None:
            return [
                MethodMismatch(
                    method_name="<class>",
                    issue="No implementing class found in source",
                )
            ]

    # Extract implementation methods
    try:
        impl_methods = extract_class_methods(impl_source, impl_class_name)
    except ValueError as e:
        return [
            MethodMismatch(
                method_name="<class>",
                issue=str(e),
            )
        ]

    # Build a lookup by method name
    impl_by_name = {m.name: m for m in impl_methods}

    # Check each required method
    for required in required_methods:
        if required.name not in impl_by_name:
            mismatches.append(
                MethodMismatch(
                    method_name=required.name,
                    issue="Method not implemented",
                    expected=required.signature_str,
                )
            )
            continue

        impl_method = impl_by_name[required.name]

        # Check async mismatch
        if required.is_async != impl_method.is_async:
            mismatches.append(
                MethodMismatch(
                    method_name=required.name,
                    issue="Async mismatch",
                    expected="async" if required.is_async else "sync",
                    actual="async" if impl_method.is_async else "sync",
                )
            )

        # Check parameter count
        if len(required.parameters) != len(impl_method.parameters):
            mismatches.append(
                MethodMismatch(
                    method_name=required.name,
                    issue="Parameter count mismatch",
                    expected=str(len(required.parameters)),
                    actual=str(len(impl_method.parameters)),
                )
            )

        # Check return type if specified in protocol
        if required.return_type and impl_method.return_type:
            # Normalize types for comparison (basic normalization)
            req_ret = required.return_type.replace(" ", "")
            impl_ret = impl_method.return_type.replace(" ", "")
            if req_ret != impl_ret:
                # Allow covariant returns (implementation can be more specific)
                # This is a simplified check - full variance checking is complex
                if not _is_compatible_return(req_ret, impl_ret):
                    mismatches.append(
                        MethodMismatch(
                            method_name=required.name,
                            issue="Return type mismatch",
                            expected=required.return_type,
                            actual=impl_method.return_type,
                        )
                    )

    return mismatches


def _is_compatible_return(expected: str, actual: str) -> bool:
    """Check if actual return type is compatible with expected.

    This is a simplified check. Full variance checking would require
    understanding the type hierarchy.

    Args:
        expected: Expected return type string
        actual: Actual return type string

    Returns:
        True if types appear compatible
    """
    # Exact match
    if expected == actual:
        return True

    # None is compatible with anything for now (simplified)
    if actual == "None" or expected == "None":
        return True

    # Any is compatible with anything
    if "Any" in expected or "Any" in actual:
        return True

    # Allow more specific types (very simplified covariance)
    # In practice, this should use a proper type checker
    return False


def verify_protocol_from_files(
    impl_path: Path,
    protocol_path: Path,
    protocol_name: str,
    impl_class_name: str | None = None,
) -> list[MethodMismatch]:
    """Verify an implementation file satisfies a Protocol from another file.

    Convenience function that handles file reading.

    Args:
        impl_path: Path to implementation file
        protocol_path: Path to Protocol definition file
        protocol_name: Name of the Protocol class
        impl_class_name: Name of implementing class (auto-detected if None)

    Returns:
        List of MethodMismatch objects (empty if satisfied)
    """
    # Read files
    try:
        impl_source = impl_path.read_text(encoding="utf-8")
    except OSError as e:
        return [
            MethodMismatch(
                method_name="<file>",
                issue=f"Cannot read implementation file: {e}",
            )
        ]

    try:
        protocol_source = protocol_path.read_text(encoding="utf-8")
    except OSError as e:
        return [
            MethodMismatch(
                method_name="<file>",
                issue=f"Cannot read protocol file: {e}",
            )
        ]

    # Extract protocol methods
    try:
        required_methods = extract_protocol_methods(protocol_source, protocol_name)
    except ValueError as e:
        return [
            MethodMismatch(
                method_name="<protocol>",
                issue=str(e),
            )
        ]

    # Auto-detect implementing class if not specified
    if impl_class_name is None:
        impl_class_name = find_implementing_class(impl_source, protocol_name)

    # Check implementation
    return check_implementation_satisfies(impl_source, impl_class_name, required_methods)
