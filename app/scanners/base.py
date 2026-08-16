"""Scanner adapter interface — AI never executes these; workers do."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ScanContext:
    scan_id: str
    target: str
    profile: str
    scope: list[str]
    authorized: bool
    evidence_dir: Path
    engagement_id: str | None = None
    org_id: str | None = None
    user_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawScanResult:
    exit_code: int
    stdout: str
    stderr: str
    artifact_paths: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedService:
    port: int
    protocol: str = "tcp"
    state: str = "open"
    service: str = ""
    product: str = ""
    version: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedFinding:
    title: str
    severity: str = "info"
    asset_name: str = ""
    cve: str | None = None
    cvss: float | None = None
    source: str = ""
    evidence: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedScan:
    asset_name: str
    asset_type: str = "host"
    services: list[NormalizedService] = field(default_factory=list)
    findings: list[NormalizedFinding] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


class Scanner(ABC):
    id: str = "base"
    name: str = "Base Scanner"
    profiles: tuple[str, ...] = ("discovery",)

    @abstractmethod
    def available(self) -> tuple[bool, str]:
        """Return (ok, detail) — e.g. binary on PATH."""

    @abstractmethod
    def validate_target(self, target: str) -> tuple[bool, str]:
        ...

    @abstractmethod
    def validate_scope(self, target: str, scope: list[str]) -> tuple[bool, str]:
        ...

    @abstractmethod
    def build_command(self, ctx: ScanContext) -> list[str]:
        ...

    @abstractmethod
    async def execute(self, ctx: ScanContext) -> RawScanResult:
        ...

    @abstractmethod
    def parse(self, raw: RawScanResult, ctx: ScanContext) -> Any:
        """Parser-specific intermediate structure (e.g. dict from XML)."""

    @abstractmethod
    def normalize(self, parsed: Any, ctx: ScanContext) -> NormalizedScan:
        ...
