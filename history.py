"""Persist and load generated rotation history."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from rotation import Assignment

HISTORY_FILE = Path(__file__).resolve().parent / "data" / "history.json"
MAX_ENTRIES = 100


@dataclass
class HistoryEntry:
    id: str
    generated_at: str
    anchor_saturday: str
    num_weekends: int
    rosters: dict[str, list[str]]
    assignments: list[dict[str, Any]]

    @property
    def label(self) -> str:
        anchor = date.fromisoformat(self.anchor_saturday)
        ts = datetime.fromisoformat(self.generated_at)
        return (
            f"{ts.strftime('%d %b %Y %H:%M')} · "
            f"from {anchor.strftime('%d %b %Y')} · {self.num_weekends} weekend(s)"
        )


def _ensure_data_dir() -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_history() -> list[HistoryEntry]:
    _ensure_data_dir()
    if not HISTORY_FILE.exists():
        return []
    try:
        raw = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(raw, list):
        return []
    return [HistoryEntry(**item) for item in raw]


def save_history(entries: list[HistoryEntry]) -> None:
    _ensure_data_dir()
    trimmed = entries[:MAX_ENTRIES]
    payload = [asdict(entry) for entry in trimmed]
    HISTORY_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def assignment_to_dict(a: Assignment) -> dict[str, Any]:
    return {
        "weekend_index": a.weekend_index,
        "work_date": a.work_date.isoformat(),
        "day_label": a.day_label,
        "time_slot": a.time_slot,
        "setup_type": a.setup_type,
        "shift_name": a.shift_name,
        "start_time": a.start_time,
        "end_time": a.end_time,
        "employee": a.employee,
    }


def dict_to_assignment(data: dict[str, Any]) -> Assignment:
    return Assignment(
        weekend_index=int(data["weekend_index"]),
        work_date=date.fromisoformat(data["work_date"]),
        day_label=data["day_label"],
        time_slot=data["time_slot"],
        setup_type=data["setup_type"],
        shift_name=data["shift_name"],
        start_time=data["start_time"],
        end_time=data["end_time"],
        employee=data["employee"],
    )


def append_history(
    *,
    anchor_saturday: date,
    num_weekends: int,
    rosters: dict[str, list[str]],
    assignments: list[Assignment],
) -> HistoryEntry:
    entry = HistoryEntry(
        id=str(uuid.uuid4()),
        generated_at=datetime.now().isoformat(timespec="seconds"),
        anchor_saturday=anchor_saturday.isoformat(),
        num_weekends=num_weekends,
        rosters=rosters,
        assignments=[assignment_to_dict(a) for a in assignments],
    )
    entries = load_history()
    entries.insert(0, entry)
    save_history(entries)
    return entry


def delete_history_entry(entry_id: str) -> bool:
    entries = load_history()
    updated = [e for e in entries if e.id != entry_id]
    if len(updated) == len(entries):
        return False
    save_history(updated)
    return True


def clear_history() -> None:
    save_history([])
