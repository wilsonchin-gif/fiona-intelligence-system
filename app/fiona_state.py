"""Single-instance durable state boundary; never an additional delivery authority."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_VERSION = "1.0"
MANIFEST_NAME = "state_manifest.json"


class StateContinuityError(RuntimeError):
    pass


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        # Directory fsync closes the rename durability window on Linux.
        if hasattr(os, "O_DIRECTORY"):
            directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class RuntimeStatePaths:
    root: Path | None
    output_dir: Path

    @classmethod
    def from_environment(cls, output_dir: Path) -> RuntimeStatePaths:
        explicit = os.getenv("FIONA_STATE_DIR", "").strip()
        mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
        railway = bool(os.getenv("RAILWAY_ENVIRONMENT_ID") or os.getenv("RAILWAY_PROJECT_ID"))
        root = Path(explicit).expanduser().resolve() if explicit else Path(mount).resolve() / "fiona" if mount else None
        if railway:
            if not mount or not os.path.ismount(mount):
                raise StateContinuityError("persistent_volume_unavailable; delivery paused")
            if root is None or not root.is_relative_to(Path(mount).resolve()) or root == Path(mount).resolve():
                raise StateContinuityError("state_root_outside_dedicated_volume")
        if root is not None and (root == Path("/app") or root.is_relative_to(Path("/app"))):
            raise StateContinuityError("state_root_masks_application_path")
        return cls(root, output_dir)

    @property
    def ledger(self) -> Path:
        return self.root / "scheduler/ledger.json" if self.root else self.output_dir / "fiona_scheduler_ledger.json"

    @property
    def memory(self) -> Path:
        return self.root / "alerts/runtime_memory.json" if self.root else self.output_dir / "fiona_memory.json"

    @property
    def standalone_alert_memory(self) -> Path:
        return self.root / "alerts/standalone_memory.json" if self.root else self.output_dir / "fiona_alert_memory.json"

    @property
    def uncertain_journal(self) -> Path:
        return self.root / "scheduler/delivery_uncertain.log" if self.root else self.output_dir / "fiona_scheduler_delivery_uncertain.log"

    @property
    def coverage_history(self) -> Path:
        return self.root / "coverage/shadow_history.json" if self.root else self.output_dir / "fiona_coverage_shadow_history.json"

    def require_initialized(self) -> None:
        if self.root is None:
            return
        manifest = self.root / MANIFEST_NAME
        if not manifest.exists():
            raise StateContinuityError("state_not_initialized_or_manifest_missing; explicit migration required")
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if data.get("schema_version") != STATE_VERSION or data.get("status") != "active":
                raise ValueError("unsupported manifest")
            datetime.fromisoformat(data["initialized_at"])
            from app.fiona_memory import FionaMemory
            from app.fiona_scheduler import SchedulerLedger

            for path in (self.ledger, self.memory, self.standalone_alert_memory):
                if not path.is_file():
                    raise ValueError("unexpected_missing: " + str(path.relative_to(self.root)))
            ledger = SchedulerLedger.load(self.ledger)
            if ledger.load_error:
                raise ValueError("corrupt_scheduler_ledger")
            for key, entry in ledger.entries.items():
                if entry.get("occurrence_id") != key or not all(name in entry for name in ("status", "scheduled_at", "attempt_count")):
                    raise ValueError("incomplete_scheduler_entry")
            FionaMemory.load(self.memory)
            FionaMemory.load(self.standalone_alert_memory)
        except Exception as exc:
            raise StateContinuityError("state_continuity_failure: " + str(exc)) from exc


def initialize_state(root: Path, *, ledger_payload: dict[str, Any], memory_payload: dict[str, Any],
                     boundary: datetime, standalone_payload: dict[str, Any] | None = None,
                     coverage_payload: dict[str, Any] | None = None, uncertain_records: list[dict[str, Any]] | None = None,
                     provenance: str = "migration") -> dict[str, Any]:
    """Explicit cutover only: preserve known records, suppress elapsed unknown backlog."""
    from app.fiona_memory import FionaMemory
    from app.fiona_scheduler import SchedulerLedger

    if boundary.tzinfo is None:
        raise ValueError("activation boundary must be timezone-aware")
    paths = RuntimeStatePaths(root.resolve(), root)
    if (paths.root / MANIFEST_NAME).exists() or any(p.exists() for p in (paths.ledger, paths.memory, paths.standalone_alert_memory)):
        raise StateContinuityError("refusing_to_overwrite_existing_state; use audited recovery copy")
    # Validate all inputs in isolation before writing anything to the target.
    with tempfile.TemporaryDirectory() as temporary:
        probe = Path(temporary)
        atomic_write_json(probe / "ledger.json", ledger_payload)
        checked = SchedulerLedger.load(probe / "ledger.json")
        if checked.load_error:
            raise StateContinuityError("invalid_migration_ledger")
        for key, entry in checked.entries.items():
            if entry.get("occurrence_id") != key or not all(name in entry for name in ("status", "scheduled_at", "attempt_count")):
                raise StateContinuityError("incomplete_migration_ledger_entry")
        for name, payload in (("runtime.json", memory_payload), ("standalone.json", standalone_payload or FionaMemory().to_dict())):
            atomic_write_json(probe / name, payload)
            FionaMemory.load(probe / name)
        for record in uncertain_records or []:
            if not isinstance(record.get("occurrence_id"), str) or not record["occurrence_id"]:
                raise StateContinuityError("invalid_migration_uncertain_record")
    migrated = dict(ledger_payload)
    last_check = checked.last_check_at
    migrated["last_check_at"] = max(boundary, last_check).isoformat() if last_check else boundary.isoformat()
    atomic_write_json(paths.ledger, migrated)
    atomic_write_json(paths.memory, memory_payload)
    atomic_write_json(paths.standalone_alert_memory, standalone_payload or FionaMemory().to_dict())
    if coverage_payload is not None:
        atomic_write_json(paths.coverage_history, coverage_payload)
    if uncertain_records:
        from app.fiona_scheduler import write_uncertain_delivery_journal
        for record in uncertain_records:
            write_uncertain_delivery_journal(paths.uncertain_journal, record)
    manifest = {"schema_version": STATE_VERSION, "status": "active", "initialized_at": datetime.now(timezone.utc).isoformat(),
                "activation_boundary": boundary.isoformat(), "provenance": provenance,
                "scheduler_entries_preserved": len(checked.entries), "contract": "single_instance_not_distributed_exactly_once"}
    atomic_write_json(paths.root / MANIFEST_NAME, manifest)
    paths.require_initialized()
    return manifest
