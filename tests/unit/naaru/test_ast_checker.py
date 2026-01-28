"""Tests for AST-based Protocol method extraction and verification."""

import pytest

from sunwell.planning.naaru.verification.ast_checker import (
    check_implementation_satisfies,
    extract_class_methods,
    extract_protocol_info,
    extract_protocol_methods,
    find_implementing_class,
)
from sunwell.planning.naaru.verification.types import MethodSignature


class TestExtractProtocolMethods:
    """Tests for extract_protocol_methods function."""

    def test_simple_protocol(self) -> None:
        """Extract methods from a simple Protocol."""
        source = '''
from typing import Protocol

class UserProtocol(Protocol):
    def get_id(self) -> str:
        ...
    
    def get_name(self) -> str:
        ...
'''
        methods = extract_protocol_methods(source, "UserProtocol")

        assert len(methods) == 2
        assert methods[0].name == "get_id"
        assert methods[0].return_type == "str"
        assert methods[1].name == "get_name"
        assert methods[1].return_type == "str"

    def test_async_methods(self) -> None:
        """Extract async methods from Protocol."""
        source = '''
from typing import Protocol

class AsyncProtocol(Protocol):
    async def fetch(self, url: str) -> bytes:
        ...
'''
        methods = extract_protocol_methods(source, "AsyncProtocol")

        assert len(methods) == 1
        assert methods[0].name == "fetch"
        assert methods[0].is_async is True
        assert methods[0].parameters == ("url",)
        assert methods[0].parameter_types == ("str",)
        assert methods[0].return_type == "bytes"

    def test_method_with_parameters(self) -> None:
        """Extract methods with multiple parameters."""
        source = '''
from typing import Protocol

class ServiceProtocol(Protocol):
    def process(self, data: str, count: int, flag: bool) -> list[str]:
        ...
'''
        methods = extract_protocol_methods(source, "ServiceProtocol")

        assert len(methods) == 1
        method = methods[0]
        assert method.name == "process"
        assert method.parameters == ("data", "count", "flag")
        assert method.parameter_types == ("str", "int", "bool")
        assert "list" in method.return_type

    def test_property_methods(self) -> None:
        """Extract property methods from Protocol."""
        source = '''
from typing import Protocol

class ConfigProtocol(Protocol):
    @property
    def name(self) -> str:
        ...
'''
        methods = extract_protocol_methods(source, "ConfigProtocol")

        assert len(methods) == 1
        assert methods[0].name == "name"
        assert methods[0].is_property is True

    def test_protocol_not_found(self) -> None:
        """Raise ValueError if Protocol not found."""
        source = '''
class NotAProtocol:
    pass
'''
        with pytest.raises(ValueError, match="not found"):
            extract_protocol_methods(source, "MissingProtocol")

    def test_invalid_source(self) -> None:
        """Raise ValueError for invalid Python syntax."""
        source = "def foo( invalid syntax"

        with pytest.raises(ValueError, match="Failed to parse"):
            extract_protocol_methods(source, "SomeProtocol")

    def test_skips_dunder_methods(self) -> None:
        """Dunder methods (except __init__) are skipped."""
        source = '''
from typing import Protocol

class DataProtocol(Protocol):
    def __init__(self) -> None:
        ...
    
    def __str__(self) -> str:
        ...
    
    def get_data(self) -> bytes:
        ...
'''
        methods = extract_protocol_methods(source, "DataProtocol")

        # Should only have __init__ and get_data
        names = [m.name for m in methods]
        assert "__init__" in names
        assert "__str__" not in names
        assert "get_data" in names

    def test_union_return_type(self) -> None:
        """Handle union return types."""
        source = '''
from typing import Protocol

class ResultProtocol(Protocol):
    def compute(self) -> str | None:
        ...
'''
        methods = extract_protocol_methods(source, "ResultProtocol")

        assert len(methods) == 1
        assert "str" in methods[0].return_type
        assert "None" in methods[0].return_type


class TestExtractProtocolInfo:
    """Tests for extract_protocol_info function."""

    def test_extracts_docstring(self) -> None:
        """Extract Protocol docstring."""
        source = '''
from typing import Protocol

class DocProtocol(Protocol):
    """A well-documented protocol."""
    
    def method(self) -> None:
        ...
'''
        info = extract_protocol_info(source, "DocProtocol")

        assert info.name == "DocProtocol"
        assert info.docstring == "A well-documented protocol."
        assert len(info.methods) == 1

    def test_extracts_bases(self) -> None:
        """Extract Protocol base classes."""
        source = '''
from typing import Protocol

class BaseProtocol(Protocol):
    pass

class ExtendedProtocol(BaseProtocol):
    def extra(self) -> None:
        ...
'''
        info = extract_protocol_info(source, "ExtendedProtocol")

        assert "BaseProtocol" in info.bases


class TestExtractClassMethods:
    """Tests for extract_class_methods function."""

    def test_extracts_from_regular_class(self) -> None:
        """Extract methods from a regular class."""
        source = '''
class UserService:
    def get_id(self) -> str:
        return "123"
    
    def get_name(self) -> str:
        return "Test"
'''
        methods = extract_class_methods(source, "UserService")

        assert len(methods) == 2
        assert methods[0].name == "get_id"
        assert methods[1].name == "get_name"

    def test_extracts_first_class_if_none_specified(self) -> None:
        """Extract from first class if name not specified."""
        source = '''
class FirstClass:
    def method_a(self) -> None:
        pass

class SecondClass:
    def method_b(self) -> None:
        pass
'''
        methods = extract_class_methods(source)

        assert len(methods) == 1
        assert methods[0].name == "method_a"

    def test_class_not_found(self) -> None:
        """Raise ValueError if class not found."""
        source = '''
class OtherClass:
    pass
'''
        with pytest.raises(ValueError, match="not found"):
            extract_class_methods(source, "MissingClass")


class TestFindImplementingClass:
    """Tests for find_implementing_class function."""

    def test_finds_by_protocol_base(self) -> None:
        """Find class that has Protocol in bases."""
        source = '''
from typing import Protocol

class UserProtocol(Protocol):
    def get_id(self) -> str:
        ...

class UserService(UserProtocol):
    def get_id(self) -> str:
        return "123"
'''
        impl_class = find_implementing_class(source, "UserProtocol")

        assert impl_class == "UserService"

    def test_finds_by_naming_convention(self) -> None:
        """Find class by naming convention (without Protocol suffix)."""
        source = '''
class User:
    def get_id(self) -> str:
        return "123"
'''
        impl_class = find_implementing_class(source, "UserProtocol")

        assert impl_class == "User"

    def test_returns_none_if_not_found(self) -> None:
        """Return None if no implementing class found."""
        source = '''
class Unrelated:
    pass
'''
        impl_class = find_implementing_class(source, "CompletelyDifferentProtocol")

        assert impl_class is None


class TestCheckImplementationSatisfies:
    """Tests for check_implementation_satisfies function."""

    def test_implementation_satisfies_protocol(self) -> None:
        """No mismatches when implementation satisfies protocol."""
        impl_source = '''
class UserService:
    def get_id(self) -> str:
        return "123"
    
    def get_name(self) -> str:
        return "Test"
'''
        required_methods = [
            MethodSignature(
                name="get_id",
                parameters=(),
                parameter_types=(),
                return_type="str",
            ),
            MethodSignature(
                name="get_name",
                parameters=(),
                parameter_types=(),
                return_type="str",
            ),
        ]

        mismatches = check_implementation_satisfies(
            impl_source, "UserService", required_methods
        )

        assert len(mismatches) == 0

    def test_missing_method(self) -> None:
        """Report mismatch for missing method."""
        impl_source = '''
class PartialService:
    def get_id(self) -> str:
        return "123"
'''
        required_methods = [
            MethodSignature(
                name="get_id",
                parameters=(),
                parameter_types=(),
                return_type="str",
            ),
            MethodSignature(
                name="get_name",
                parameters=(),
                parameter_types=(),
                return_type="str",
            ),
        ]

        mismatches = check_implementation_satisfies(
            impl_source, "PartialService", required_methods
        )

        assert len(mismatches) == 1
        assert mismatches[0].method_name == "get_name"
        assert "not implemented" in mismatches[0].issue.lower()

    def test_async_mismatch(self) -> None:
        """Report mismatch for async/sync difference."""
        impl_source = '''
class SyncService:
    def fetch(self, url: str) -> bytes:
        return b"data"
'''
        required_methods = [
            MethodSignature(
                name="fetch",
                parameters=("url",),
                parameter_types=("str",),
                return_type="bytes",
                is_async=True,
            ),
        ]

        mismatches = check_implementation_satisfies(
            impl_source, "SyncService", required_methods
        )

        assert len(mismatches) == 1
        assert mismatches[0].method_name == "fetch"
        assert "async" in mismatches[0].issue.lower()

    def test_parameter_count_mismatch(self) -> None:
        """Report mismatch for wrong parameter count."""
        impl_source = '''
class WrongParams:
    def process(self) -> str:
        return "done"
'''
        required_methods = [
            MethodSignature(
                name="process",
                parameters=("data",),
                parameter_types=("str",),
                return_type="str",
            ),
        ]

        mismatches = check_implementation_satisfies(
            impl_source, "WrongParams", required_methods
        )

        assert len(mismatches) == 1
        assert "parameter count" in mismatches[0].issue.lower()

    def test_class_not_found(self) -> None:
        """Report error if class not found."""
        impl_source = '''
class OtherClass:
    pass
'''
        required_methods = [
            MethodSignature(
                name="method",
                parameters=(),
                parameter_types=(),
                return_type="None",
            ),
        ]

        mismatches = check_implementation_satisfies(
            impl_source, "MissingClass", required_methods
        )

        assert len(mismatches) == 1
        assert mismatches[0].method_name == "<class>"


class TestMethodSignature:
    """Tests for MethodSignature dataclass."""

    def test_signature_str_simple(self) -> None:
        """Generate simple signature string."""
        sig = MethodSignature(
            name="get_id",
            parameters=(),
            parameter_types=(),
            return_type="str",
        )

        assert sig.signature_str == "def get_id() -> str"

    def test_signature_str_with_params(self) -> None:
        """Generate signature string with parameters."""
        sig = MethodSignature(
            name="process",
            parameters=("data", "count"),
            parameter_types=("str", "int"),
            return_type="bool",
        )

        assert sig.signature_str == "def process(data: str, count: int) -> bool"

    def test_signature_str_async(self) -> None:
        """Generate async signature string."""
        sig = MethodSignature(
            name="fetch",
            parameters=("url",),
            parameter_types=("str",),
            return_type="bytes",
            is_async=True,
        )

        assert sig.signature_str == "async def fetch(url: str) -> bytes"

    def test_signature_str_property(self) -> None:
        """Generate property signature string."""
        sig = MethodSignature(
            name="name",
            parameters=(),
            parameter_types=(),
            return_type="str",
            is_property=True,
        )

        assert "@property" in sig.signature_str
