# Copyright (c) 2026, Sunwell.  All rights reserved.
"""Tests for security audit logging (RFC-089)."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from sunwell.security.analyzer import PermissionScope
from sunwell.security.audit import (
    AuditEntry,
    AuditLogManager,
    LocalAuditLog,
)


class TestAuditEntry:
    """Tests for AuditEntry."""

    def test_to_dict_roundtrip(self):
        """Serialization roundtrip preserves data."""
        scope = PermissionScope(
            filesystem_read=frozenset(["/app/src/*"]),
        )

        entry = AuditEntry(
            timestamp=datetime.now(),
            skill_name="test-skill",
            dag_id="dag-123",
            user_id="user-456",
            requested_permissions=scope,
            action="execute",
            details="Test execution",
            inputs_hash="abc123",
            outputs_hash="def456",
            previous_hash="",
            entry_hash="ghi789",
            signature="sig123",
        )

        data = entry.to_dict()
        restored = AuditEntry.from_dict(data)

        assert restored.skill_name == entry.skill_name
        assert restored.dag_id == entry.dag_id
        assert restored.action == entry.action
        assert restored.entry_hash == entry.entry_hash


class TestLocalAuditLog:
    """Tests for LocalAuditLog."""

    @pytest.fixture
    def temp_log(self):
        """Create a temporary audit log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            key = b"test-signing-key-0123456789abcdef"
            yield LocalAuditLog(log_path, key)

    def test_append_creates_entry(self, temp_log):
        """Appending creates an audit entry."""
        scope = PermissionScope()

        entry = temp_log.append({
            "timestamp": datetime.now(),
            "skill_name": "test-skill",
            "dag_id": "dag-123",
            "user_id": "user-456",
            "requested_permissions": scope,
            "action": "execute",
            "details": "Test execution",
            "inputs_hash": "abc123",
            "outputs_hash": "def456",
        })

        assert entry.skill_name == "test-skill"
        assert entry.entry_hash  # Has computed hash
        assert entry.signature  # Has signature
        assert entry.previous_hash == ""  # First entry

    def test_chain_integrity(self, temp_log):
        """Entries form a chain."""
        scope = PermissionScope()

        entry1 = temp_log.append({
            "timestamp": datetime.now(),
            "skill_name": "skill-1",
            "dag_id": "dag-1",
            "user_id": "user-1",
            "requested_permissions": scope,
            "action": "execute",
            "details": "First",
            "inputs_hash": "hash1",
            "outputs_hash": None,
        })

        entry2 = temp_log.append({
            "timestamp": datetime.now(),
            "skill_name": "skill-2",
            "dag_id": "dag-2",
            "user_id": "user-1",
            "requested_permissions": scope,
            "action": "execute",
            "details": "Second",
            "inputs_hash": "hash2",
            "outputs_hash": None,
        })

        # Second entry references first
        assert entry2.previous_hash == entry1.entry_hash

    def test_verify_integrity_valid(self, temp_log):
        """Valid log passes integrity check."""
        scope = PermissionScope()

        for i in range(5):
            temp_log.append({
                "timestamp": datetime.now(),
                "skill_name": f"skill-{i}",
                "dag_id": f"dag-{i}",
                "user_id": "user-1",
                "requested_permissions": scope,
                "action": "execute",
                "details": f"Entry {i}",
                "inputs_hash": f"hash{i}",
                "outputs_hash": None,
            })

        valid, message = temp_log.verify_integrity()
        assert valid
        assert "5 entries" in message

    def test_verify_integrity_empty(self, temp_log):
        """Empty log passes integrity check."""
        valid, message = temp_log.verify_integrity()
        assert valid
        assert "No audit log" in message

    def test_query_by_skill_name(self, temp_log):
        """Query filters by skill name."""
        scope = PermissionScope()

        temp_log.append({
            "timestamp": datetime.now(),
            "skill_name": "skill-a",
            "dag_id": "dag-1",
            "user_id": "user-1",
            "requested_permissions": scope,
            "action": "execute",
            "details": "A",
            "inputs_hash": "hash1",
            "outputs_hash": None,
        })

        temp_log.append({
            "timestamp": datetime.now(),
            "skill_name": "skill-b",
            "dag_id": "dag-2",
            "user_id": "user-1",
            "requested_permissions": scope,
            "action": "execute",
            "details": "B",
            "inputs_hash": "hash2",
            "outputs_hash": None,
        })

        entries = list(temp_log.query(skill_name="skill-a"))
        assert len(entries) == 1
        assert entries[0].skill_name == "skill-a"

    def test_query_by_action(self, temp_log):
        """Query filters by action."""
        scope = PermissionScope()

        temp_log.append({
            "timestamp": datetime.now(),
            "skill_name": "skill-1",
            "dag_id": "dag-1",
            "user_id": "user-1",
            "requested_permissions": scope,
            "action": "execute",
            "details": "Execute",
            "inputs_hash": "hash1",
            "outputs_hash": None,
        })

        temp_log.append({
            "timestamp": datetime.now(),
            "skill_name": "skill-2",
            "dag_id": "dag-2",
            "user_id": "user-1",
            "requested_permissions": scope,
            "action": "violation",
            "details": "Violation",
            "inputs_hash": "hash2",
            "outputs_hash": None,
        })

        entries = list(temp_log.query(action="violation"))
        assert len(entries) == 1
        assert entries[0].action == "violation"

    def test_get_recent(self, temp_log):
        """Get recent returns newest first."""
        scope = PermissionScope()

        for i in range(10):
            temp_log.append({
                "timestamp": datetime.now(),
                "skill_name": f"skill-{i}",
                "dag_id": f"dag-{i}",
                "user_id": "user-1",
                "requested_permissions": scope,
                "action": "execute",
                "details": f"Entry {i}",
                "inputs_hash": f"hash{i}",
                "outputs_hash": None,
            })

        recent = temp_log.get_recent(limit=5)

        assert len(recent) == 5
        # Should be newest first
        assert recent[0].skill_name == "skill-9"
        assert recent[-1].skill_name == "skill-5"


class TestAuditLogManager:
    """Tests for AuditLogManager."""

    @pytest.fixture
    def manager(self):
        """Create an audit log manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            key = b"test-signing-key-0123456789abcdef"
            backend = LocalAuditLog(log_path, key)
            yield AuditLogManager(backend, default_user_id="test-user")

    def test_record_execution(self, manager):
        """Records successful execution."""
        scope = PermissionScope()

        entry = manager.record_execution(
            skill_name="test-skill",
            dag_id="dag-123",
            permissions=scope,
            inputs_hash="abc123",
            outputs_hash="def456",
            details="Executed successfully",
        )

        assert entry.skill_name == "test-skill"
        assert entry.action == "execute"
        assert entry.user_id == "test-user"

    def test_record_violation(self, manager):
        """Records security violation."""
        scope = PermissionScope()

        entry = manager.record_violation(
            skill_name="bad-skill",
            dag_id="dag-456",
            permissions=scope,
            violation_type="credential_leak",
            evidence="AWS key detected",
        )

        assert entry.action == "violation"
        assert "credential_leak" in entry.details

    def test_record_denied(self, manager):
        """Records permission denial."""
        scope = PermissionScope(
            network_allow=frozenset(["external.com:443"])
        )

        entry = manager.record_denied(
            skill_name="net-skill",
            dag_id="dag-789",
            permissions=scope,
            reason="External network not allowed",
        )

        assert entry.action == "denied"
        assert "External network" in entry.details

    def test_record_error(self, manager):
        """Records execution error."""
        scope = PermissionScope()

        entry = manager.record_error(
            skill_name="err-skill",
            dag_id="dag-err",
            permissions=scope,
            error="Timeout after 30s",
        )

        assert entry.action == "error"
        assert "Timeout" in entry.details

    def test_custom_user_id(self, manager):
        """Allows custom user ID."""
        scope = PermissionScope()

        entry = manager.record_execution(
            skill_name="test-skill",
            dag_id="dag-123",
            permissions=scope,
            inputs_hash="abc123",
            outputs_hash=None,
            user_id="custom-user",
        )

        assert entry.user_id == "custom-user"
