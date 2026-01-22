# Copyright (c) 2026, Sunwell.  All rights reserved.
"""SIEM export formats for security audit logs (RFC-089).

Supports multiple SIEM and log aggregation formats:
- CEF (Common Event Format) - ArcSight, QRadar
- LEEF (Log Event Extended Format) - QRadar native
- Syslog RFC 5424 - Generic syslog
- JSON Lines - Splunk, Elasticsearch
- ECS (Elastic Common Schema) - Elasticsearch/Kibana
- Datadog - Datadog Log Management
"""


import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from sunwell.security.audit import AuditEntry


# =============================================================================
# SIEM FORMATTER PROTOCOL
# =============================================================================


class SIEMFormatter(ABC):
    """Abstract base for SIEM formatters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Format name."""
        ...

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """Recommended file extension."""
        ...

    @abstractmethod
    def format_entry(self, entry: AuditEntry) -> str:
        """Format a single entry."""
        ...

    def format_batch(self, entries: Iterator[AuditEntry]) -> str:
        """Format multiple entries."""
        return "\n".join(self.format_entry(e) for e in entries)


# =============================================================================
# CEF FORMAT (ArcSight, QRadar)
# =============================================================================


@dataclass
class CEFFormatter(SIEMFormatter):
    """Common Event Format (CEF) for ArcSight, QRadar.

    Format: CEF:Version|Device Vendor|Device Product|Device Version|
            Signature ID|Name|Severity|Extension
    """

    vendor: str = "Sunwell"
    product: str = "SecurityAudit"
    version: str = "1.0"

    @property
    def name(self) -> str:
        return "CEF"

    @property
    def file_extension(self) -> str:
        return ".cef"

    def format_entry(self, entry: AuditEntry) -> str:
        """Format entry as CEF."""
        # Map action to severity (0-10 scale)
        severity_map = {
            "execute": 3,
            "denied": 5,
            "violation": 8,
            "error": 7,
        }
        severity = severity_map.get(entry.action, 5)

        # Escape CEF special characters
        def escape(s: str) -> str:
            return s.replace("\\", "\\\\").replace("|", "\\|").replace("=", "\\=")

        # Build extension fields
        extensions = [
            f"dvc={escape(entry.skill_name)}",
            f"duser={escape(entry.user_id)}",
            f"cs1={escape(entry.dag_id)}",
            f"cs1Label=DAG_ID",
            f"msg={escape(entry.details[:200])}",
            f"rt={int(entry.timestamp.timestamp() * 1000)}",
            f"src_hash={escape(entry.inputs_hash[:16])}",
        ]

        if entry.outputs_hash:
            extensions.append(f"dst_hash={escape(entry.outputs_hash[:16])}")

        extension_str = " ".join(extensions)

        return (
            f"CEF:0|{self.vendor}|{self.product}|{self.version}|"
            f"{entry.action}|{entry.action}|{severity}|{extension_str}"
        )


# =============================================================================
# LEEF FORMAT (QRadar native)
# =============================================================================


@dataclass
class LEEFFormatter(SIEMFormatter):
    """Log Event Extended Format (LEEF) for QRadar native integration.

    Format: LEEF:Version|Vendor|Product|Version|EventID|[Key=Value pairs]
    """

    vendor: str = "Sunwell"
    product: str = "SecurityAudit"
    version: str = "1.0"

    @property
    def name(self) -> str:
        return "LEEF"

    @property
    def file_extension(self) -> str:
        return ".leef"

    def format_entry(self, entry: AuditEntry) -> str:
        """Format entry as LEEF."""
        # Event ID based on action
        event_ids = {
            "execute": "SKILL_EXECUTE",
            "denied": "PERMISSION_DENIED",
            "violation": "SECURITY_VIOLATION",
            "error": "EXECUTION_ERROR",
        }
        event_id = event_ids.get(entry.action, "UNKNOWN")

        # Key-value pairs
        kv_pairs = [
            f"devTime={entry.timestamp.strftime('%b %d %Y %H:%M:%S')}",
            f"devTimeFormat=MMM dd yyyy HH:mm:ss",
            f"usrName={entry.user_id}",
            f"src={entry.skill_name}",
            f"cat={entry.action}",
            f"dagId={entry.dag_id}",
            f"msg={entry.details[:200]}",
            f"severity={self._get_severity(entry.action)}",
        ]

        kv_str = "\t".join(kv_pairs)

        return (
            f"LEEF:2.0|{self.vendor}|{self.product}|{self.version}|"
            f"{event_id}|{kv_str}"
        )

    def _get_severity(self, action: str) -> int:
        """Map action to LEEF severity (1-10)."""
        return {"execute": 2, "denied": 5, "violation": 9, "error": 7}.get(action, 5)


# =============================================================================
# SYSLOG RFC 5424
# =============================================================================


@dataclass
class SyslogFormatter(SIEMFormatter):
    """RFC 5424 Syslog format for generic syslog integration.

    Format: <PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID SD MSG
    """

    hostname: str = "sunwell-agent"
    app_name: str = "security-audit"
    facility: int = 16  # local0

    @property
    def name(self) -> str:
        return "Syslog"

    @property
    def file_extension(self) -> str:
        return ".log"

    def format_entry(self, entry: AuditEntry) -> str:
        """Format entry as RFC 5424 syslog."""
        # Severity mapping (0=emerg to 7=debug)
        severity_map = {
            "execute": 6,  # informational
            "denied": 4,  # warning
            "violation": 3,  # error
            "error": 3,  # error
        }
        severity = severity_map.get(entry.action, 6)

        # Priority = facility * 8 + severity
        priority = self.facility * 8 + severity

        # Timestamp in RFC 5424 format
        timestamp = entry.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Structured data
        sd = (
            f'[sunwell skill="{entry.skill_name}" dag="{entry.dag_id}" '
            f'user="{entry.user_id}" action="{entry.action}"]'
        )

        return (
            f"<{priority}>1 {timestamp} {self.hostname} {self.app_name} "
            f"- - {sd} {entry.details[:200]}"
        )


# =============================================================================
# JSON LINES (Splunk, Elasticsearch)
# =============================================================================


@dataclass
class JSONLinesFormatter(SIEMFormatter):
    """JSON Lines format for Splunk, Elasticsearch ingestion."""

    include_raw_permissions: bool = False
    """Include full permission scope in output."""

    @property
    def name(self) -> str:
        return "JSON Lines"

    @property
    def file_extension(self) -> str:
        return ".jsonl"

    def format_entry(self, entry: AuditEntry) -> str:
        """Format entry as JSON line."""
        data = {
            "@timestamp": entry.timestamp.isoformat(),
            "event.category": "security",
            "event.type": entry.action,
            "event.action": f"skill_{entry.action}",
            "event.outcome": "success" if entry.action == "execute" else "failure",
            "source.address": entry.skill_name,
            "user.id": entry.user_id,
            "labels.dag_id": entry.dag_id,
            "message": entry.details,
            "hash.input": entry.inputs_hash,
            "hash.output": entry.outputs_hash,
            "hash.entry": entry.entry_hash,
        }

        if self.include_raw_permissions:
            data["sunwell.permissions"] = entry.requested_permissions.to_dict()

        return json.dumps(data, default=str)


# =============================================================================
# ECS FORMAT (Elastic Common Schema)
# =============================================================================


@dataclass
class ECSFormatter(SIEMFormatter):
    """Elastic Common Schema (ECS) format for Elasticsearch/Kibana.

    Follows ECS 8.x specification for full compatibility.
    """

    agent_name: str = "sunwell-security"
    agent_version: str = "1.0.0"

    @property
    def name(self) -> str:
        return "ECS"

    @property
    def file_extension(self) -> str:
        return ".ndjson"

    def format_entry(self, entry: AuditEntry) -> str:
        """Format entry as ECS-compliant JSON."""
        # Map to ECS event categories and types
        category_map = {
            "execute": ("process", "start"),
            "denied": ("iam", "denied"),
            "violation": ("intrusion_detection", "alert"),
            "error": ("process", "error"),
        }
        category, event_type = category_map.get(entry.action, ("process", "info"))

        ecs_doc = {
            "@timestamp": entry.timestamp.isoformat(),
            "ecs": {"version": "8.11.0"},
            "event": {
                "kind": "event",
                "category": [category],
                "type": [event_type],
                "action": f"skill-{entry.action}",
                "outcome": "success" if entry.action == "execute" else "failure",
                "reason": entry.details[:500],
                "hash": entry.entry_hash,
            },
            "agent": {
                "name": self.agent_name,
                "version": self.agent_version,
                "type": "security-audit",
            },
            "user": {
                "id": entry.user_id,
                "name": entry.user_id,
            },
            "process": {
                "name": entry.skill_name,
                "entity_id": entry.dag_id,
            },
            "file": {
                "hash": {
                    "sha256": entry.entry_hash,
                }
            },
            "message": entry.details,
            "tags": ["sunwell", "skill-execution", entry.action],
            "labels": {
                "dag_id": entry.dag_id,
                "skill_name": entry.skill_name,
            },
        }

        return json.dumps(ecs_doc, default=str)


# =============================================================================
# DATADOG FORMAT
# =============================================================================


@dataclass
class DatadogFormatter(SIEMFormatter):
    """Datadog Log Management format.

    Follows Datadog's JSON log format with standard attributes.
    """

    service: str = "sunwell"
    source: str = "security-audit"
    env: str = "production"

    @property
    def name(self) -> str:
        return "Datadog"

    @property
    def file_extension(self) -> str:
        return ".jsonl"

    def format_entry(self, entry: AuditEntry) -> str:
        """Format entry for Datadog."""
        # Map to Datadog status levels
        status_map = {
            "execute": "info",
            "denied": "warn",
            "violation": "error",
            "error": "error",
        }

        doc = {
            "timestamp": entry.timestamp.isoformat(),
            "status": status_map.get(entry.action, "info"),
            "service": self.service,
            "source": self.source,
            "env": self.env,
            "message": entry.details,
            "ddtags": f"action:{entry.action},skill:{entry.skill_name},dag:{entry.dag_id}",
            "usr.id": entry.user_id,
            "skill.name": entry.skill_name,
            "dag.id": entry.dag_id,
            "security.action": entry.action,
            "security.input_hash": entry.inputs_hash,
            "security.output_hash": entry.outputs_hash,
            "security.entry_hash": entry.entry_hash,
        }

        return json.dumps(doc, default=str)


# =============================================================================
# SPLUNK HEC FORMAT
# =============================================================================


@dataclass
class SplunkHECFormatter(SIEMFormatter):
    """Splunk HTTP Event Collector (HEC) format.

    Pre-formatted for direct HEC API ingestion.
    """

    index: str = "security"
    sourcetype: str = "sunwell:security:audit"
    source: str = "sunwell-agent"

    @property
    def name(self) -> str:
        return "Splunk HEC"

    @property
    def file_extension(self) -> str:
        return ".jsonl"

    def format_entry(self, entry: AuditEntry) -> str:
        """Format entry for Splunk HEC."""
        event = {
            "action": entry.action,
            "skill_name": entry.skill_name,
            "dag_id": entry.dag_id,
            "user_id": entry.user_id,
            "details": entry.details,
            "inputs_hash": entry.inputs_hash,
            "outputs_hash": entry.outputs_hash,
            "entry_hash": entry.entry_hash,
            "permissions": entry.requested_permissions.to_dict(),
        }

        hec_event = {
            "time": entry.timestamp.timestamp(),
            "index": self.index,
            "sourcetype": self.sourcetype,
            "source": self.source,
            "event": event,
        }

        return json.dumps(hec_event, default=str)


# =============================================================================
# FORMAT REGISTRY
# =============================================================================


SIEM_FORMATTERS: dict[str, type[SIEMFormatter]] = {
    "cef": CEFFormatter,
    "leef": LEEFFormatter,
    "syslog": SyslogFormatter,
    "jsonl": JSONLinesFormatter,
    "ecs": ECSFormatter,
    "datadog": DatadogFormatter,
    "splunk": SplunkHECFormatter,
}


def get_formatter(
    format_name: str,
    **kwargs,
) -> SIEMFormatter:
    """Get a SIEM formatter by name.

    Args:
        format_name: Name of the format (cef, leef, syslog, etc.)
        **kwargs: Formatter-specific configuration

    Returns:
        Configured formatter instance

    Raises:
        ValueError: If format is not supported
    """
    format_lower = format_name.lower()
    if format_lower not in SIEM_FORMATTERS:
        available = ", ".join(SIEM_FORMATTERS.keys())
        raise ValueError(f"Unknown format '{format_name}'. Available: {available}")

    return SIEM_FORMATTERS[format_lower](**kwargs)


def export_to_siem(
    entries: Iterator[AuditEntry],
    format_name: str,
    **kwargs,
) -> str:
    """Export audit entries to SIEM format.

    Args:
        entries: Audit entries to export
        format_name: Target format (cef, leef, syslog, jsonl, ecs, datadog, splunk)
        **kwargs: Formatter-specific options

    Returns:
        Formatted export string
    """
    formatter = get_formatter(format_name, **kwargs)
    return formatter.format_batch(entries)


def list_formats() -> list[dict[str, str]]:
    """List available SIEM formats.

    Returns:
        List of format info dicts with name, extension, and description
    """
    return [
        {
            "name": "cef",
            "extension": ".cef",
            "description": "Common Event Format (ArcSight, QRadar)",
        },
        {
            "name": "leef",
            "extension": ".leef",
            "description": "Log Event Extended Format (QRadar native)",
        },
        {
            "name": "syslog",
            "extension": ".log",
            "description": "RFC 5424 Syslog",
        },
        {
            "name": "jsonl",
            "extension": ".jsonl",
            "description": "JSON Lines (Splunk, Elasticsearch)",
        },
        {
            "name": "ecs",
            "extension": ".ndjson",
            "description": "Elastic Common Schema (Elasticsearch/Kibana)",
        },
        {
            "name": "datadog",
            "extension": ".jsonl",
            "description": "Datadog Log Management",
        },
        {
            "name": "splunk",
            "extension": ".jsonl",
            "description": "Splunk HTTP Event Collector (HEC)",
        },
    ]
