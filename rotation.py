"""Weekend shift rotation — timings match reference schedule."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

# (slot_label, setup_type, shift_name, start, end)
SLOT_TEMPLATES: dict[str, tuple[tuple[str, str, str, str, str], ...]] = {
    "Morning": (
        ("6:00 AM - 12:00 PM", "On-Shift", "Morning", "06:00", "12:00"),
        ("12:00 PM - 6:00 PM", "On-call", "Morning", "12:00", "18:00"),
    ),
    "Morning DPT": (
        ("7:00 AM - 4:00 PM", "On-Shift", "Morning DPT", "07:00", "16:00"),
    ),
    "Evening": (
        ("6:00 PM - 12:00 AM", "On-Call", "Evening", "18:00", "00:00"),
        ("12:00 AM - 6:00 AM", "On-Shift", "Evening", "00:00", "06:00"),
    ),
    "Evening DPT": (
        ("10:00 PM - 7:00 AM", "On-Shift", "Evening DPT", "22:00", "07:00"),
    ),
}


@dataclass(frozen=True)
class ShiftTeams:
    morning: list[str]
    morning_dpt: list[str]
    evening: list[str]
    evening_dpt: list[str]


@dataclass(frozen=True)
class Assignment:
    weekend_index: int
    work_date: date
    day_label: str
    time_slot: str
    setup_type: str
    shift_name: str
    start_time: str
    end_time: str
    employee: str


def saturday_on_or_after(d: date) -> date:
    days_until_sat = (5 - d.weekday()) % 7
    return d + timedelta(days=days_until_sat)


def weekend_dates(anchor_saturday: date, weekend_index: int) -> tuple[date, date]:
    sat = anchor_saturday + timedelta(weeks=weekend_index)
    return sat, sat + timedelta(days=1)


def _parse_names(employees: Iterable[str], shift_label: str) -> list[str]:
    cleaned = [e.strip() for e in employees if e and e.strip()]
    if not cleaned:
        raise ValueError(f"{shift_label} team must have at least one member.")
    seen: set[str] = set()
    unique: list[str] = []
    for name in cleaned:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(name)
    return unique


def parse_shift_teams(
    morning: Iterable[str],
    morning_dpt: Iterable[str],
    evening: Iterable[str],
    evening_dpt: Iterable[str],
) -> ShiftTeams:
    return ShiftTeams(
        morning=_parse_names(morning, "Morning"),
        morning_dpt=_parse_names(morning_dpt, "Morning DPT"),
        evening=_parse_names(evening, "Evening"),
        evening_dpt=_parse_names(evening_dpt, "Evening DPT"),
    )


def _pick(queue: list[str], index: int) -> str:
    return queue[index % len(queue)]


def _append_slots(
    assignments: list[Assignment],
    *,
    weekend_index: int,
    work_date: date,
    day_label: str,
    shift_key: str,
    employee: str,
) -> None:
    for slot_label, setup_type, shift_name, start, end in SLOT_TEMPLATES[shift_key]:
        assignments.append(
            Assignment(
                weekend_index=weekend_index,
                work_date=work_date,
                day_label=day_label,
                time_slot=slot_label,
                setup_type=setup_type,
                shift_name=shift_name,
                start_time=start,
                end_time=end,
                employee=employee,
            )
        )


def _assign_day(
    assignments: list[Assignment],
    *,
    weekend_index: int,
    week_offset: int,
    work_date: date,
    day_label: str,
    morning: list[str],
    morning_dpt: list[str],
    evening: list[str],
    evening_dpt: list[str],
) -> None:
    is_saturday = day_label == "Saturday"

    morning_member = _pick(morning, week_offset * 2 + (0 if is_saturday else 1))
    morning_dpt_member = _pick(morning_dpt, week_offset)
    evening_split = _pick(evening, week_offset * 2 + (0 if is_saturday else 1))
    evening_dpt_member = _pick(evening_dpt, week_offset)

    _append_slots(
        assignments,
        weekend_index=weekend_index,
        work_date=work_date,
        day_label=day_label,
        shift_key="Morning",
        employee=morning_member,
    )
    _append_slots(
        assignments,
        weekend_index=weekend_index,
        work_date=work_date,
        day_label=day_label,
        shift_key="Morning DPT",
        employee=morning_dpt_member,
    )
    _append_slots(
        assignments,
        weekend_index=weekend_index,
        work_date=work_date,
        day_label=day_label,
        shift_key="Evening",
        employee=evening_split,
    )
    _append_slots(
        assignments,
        weekend_index=weekend_index,
        work_date=work_date,
        day_label=day_label,
        shift_key="Evening DPT",
        employee=evening_dpt_member,
    )


def generate_weekend_rotation(
    teams: ShiftTeams,
    *,
    start_date: date | None = None,
    num_weekends: int = 12,
    anchor_saturday: date | None = None,
) -> list[Assignment]:
    if num_weekends < 1:
        raise ValueError("num_weekends must be at least 1.")

    anchor = anchor_saturday or saturday_on_or_after(start_date or date.today())
    assignments: list[Assignment] = []

    for week in range(num_weekends):
        weekend_index = week + 1
        sat, sun = weekend_dates(anchor, week)
        for work_date, day_label in ((sat, "Saturday"), (sun, "Sunday")):
            _assign_day(
                assignments,
                weekend_index=weekend_index,
                week_offset=week,
                work_date=work_date,
                day_label=day_label,
                morning=teams.morning,
                morning_dpt=teams.morning_dpt,
                evening=teams.evening,
                evening_dpt=teams.evening_dpt,
            )

    return assignments


def rotation_summary(assignments: list[Assignment]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    weekends_by_employee: dict[str, set[int]] = {}

    for a in assignments:
        if a.employee not in summary:
            summary[a.employee] = {
                "Morning": 0,
                "Morning DPT": 0,
                "Evening": 0,
                "Evening DPT": 0,
                "Total slots": 0,
            }
            weekends_by_employee[a.employee] = set()
        summary[a.employee][a.shift_name] += 1
        summary[a.employee]["Total slots"] += 1
        weekends_by_employee[a.employee].add(a.weekend_index)

    for name, weekends in weekends_by_employee.items():
        summary[name]["Weekends"] = len(weekends)

    return summary
