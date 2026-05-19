"""Streamlit UI for automatic weekend shift rotation."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from history import (
    append_history,
    clear_history,
    delete_history_entry,
    dict_to_assignment,
    load_history,
)
from rotation import generate_weekend_rotation, parse_shift_teams, rotation_summary, saturday_on_or_after

st.set_page_config(page_title="Weekend Shift Rotation", layout="wide")

st.title("Weekend shift rotation")
st.caption(
    "Morning · Morning DPT · Evening · Evening DPT — PH time slots (Saturday & Sunday)."
)

DEFAULT_MORNING = "name 1\nname 2\nname 3"
DEFAULT_MORNING_DPT = "name 1\nname 2\nname 3"
DEFAULT_EVENING = "name 1\nname 2\nname 3"
DEFAULT_EVENING_DPT = "name 1\nname 2\nname 3"


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _assignments_to_df(assignments) -> pd.DataFrame:
    rows = [
        {
            "Weekend #": a.weekend_index,
            "Date": a.work_date.strftime("%b %d, %Y"),
            "Day": a.day_label,
            "Time Slot": a.time_slot,
            "Setup Type": a.setup_type,
            "Shift Name": a.shift_name,
            "Assigned Person": a.employee,
        }
        for a in assignments
    ]
    return pd.DataFrame(rows)


def _render_schedule_tabs(assignments, anchor_str: str, *, key_prefix: str = "") -> None:
    df = _assignments_to_df(assignments)
    tab_calendar, tab_summary, tab_export = st.tabs(["Schedule", "Balance summary", "Export"])

    with tab_calendar:
        weekend_filter = st.selectbox(
            "Filter by weekend",
            options=["All"] + sorted(df["Weekend #"].unique().tolist()),
            key=f"{key_prefix}weekend_filter",
        )
        view = df if weekend_filter == "All" else df[df["Weekend #"] == weekend_filter]
        st.dataframe(view, use_container_width=True, hide_index=True)

    with tab_summary:
        summary = rotation_summary(assignments)
        summary_df = pd.DataFrame.from_dict(summary, orient="index").reset_index(names="Employee")
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

    with tab_export:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            data=csv,
            file_name=f"weekend_rotation_{anchor_str}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"{key_prefix}download_csv",
        )


if "history_entries" not in st.session_state:
    st.session_state["history_entries"] = load_history()

st.subheader("Team members by shift")
st.caption("Enter one name per line in each box.")

col_morning, col_morning_dpt, col_evening, col_evening_dpt = st.columns(4)

with col_morning:
    st.markdown("**Morning**")
    st.caption("6:00 AM–12:00 PM · 12:00 PM–6:00 PM")
    morning_text = st.text_area(
        "Morning members",
        value=DEFAULT_MORNING,
        height=160,
        label_visibility="collapsed",
        key="team_morning",
    )

with col_morning_dpt:
    st.markdown("**Morning DPT**")
    st.caption("7:00 AM–4:00 PM")
    morning_dpt_text = st.text_area(
        "Morning DPT members",
        value=DEFAULT_MORNING_DPT,
        height=160,
        label_visibility="collapsed",
        key="team_morning_dpt",
    )

with col_evening:
    st.markdown("**Evening**")
    st.caption("6:00 PM–12:00 AM · 12:00 AM–6:00 AM")
    evening_text = st.text_area(
        "Evening members",
        value=DEFAULT_EVENING,
        height=160,
        label_visibility="collapsed",
        key="team_evening",
    )

with col_evening_dpt:
    st.markdown("**Evening DPT**")
    st.caption("10:00 PM–7:00 AM (Sat & Sun)")
    evening_dpt_text = st.text_area(
        "Evening DPT members",
        value=DEFAULT_EVENING_DPT,
        height=160,
        label_visibility="collapsed",
        key="team_evening_dpt",
    )

with st.sidebar:
    st.header("Schedule settings")
    start = st.date_input("First weekend anchor (Saturday on or after this date)", value=date.today())
    num_weekends = st.number_input("Weekends to generate", min_value=1, max_value=52, value=12)
    anchor = saturday_on_or_after(start)
    st.info(f"First Saturday: **{anchor.strftime('%A, %d %b %Y')}**")

    st.markdown("**Roster size**")
    st.write(f"Morning: {len(_lines(morning_text))} members")
    st.write(f"Morning DPT: {len(_lines(morning_dpt_text))} members")
    st.write(f"Evening: {len(_lines(evening_text))} members")
    st.write(f"Evening DPT: {len(_lines(evening_dpt_text))} members")

    st.divider()
    history_count = len(st.session_state["history_entries"])
    st.caption(f"**{history_count}** saved rotation(s) in history")

col_gen, col_clear = st.columns([1, 1])
with col_gen:
    generate = st.button("Generate rotation", type="primary", use_container_width=True)
with col_clear:
    if st.button("Clear current schedule", use_container_width=True):
        st.session_state.pop("assignments", None)
        st.session_state.pop("anchor", None)
        st.rerun()

if generate:
    try:
        rosters = {
            "morning": _lines(morning_text),
            "morning_dpt": _lines(morning_dpt_text),
            "evening": _lines(evening_text),
            "evening_dpt": _lines(evening_dpt_text),
        }
        teams = parse_shift_teams(
            rosters["morning"],
            rosters["morning_dpt"],
            rosters["evening"],
            rosters["evening_dpt"],
        )
        assignments = generate_weekend_rotation(
            teams,
            anchor_saturday=anchor,
            num_weekends=int(num_weekends),
        )
        st.session_state["assignments"] = assignments
        st.session_state["anchor"] = anchor.isoformat()

        append_history(
            anchor_saturday=anchor,
            num_weekends=int(num_weekends),
            rosters=rosters,
            assignments=assignments,
        )
        st.session_state["history_entries"] = load_history()
        st.success("Rotation generated and saved to history.")
    except ValueError as exc:
        st.error(str(exc))

assignments = st.session_state.get("assignments")
anchor_str = st.session_state.get("anchor", anchor.isoformat())

page_generate, page_history = st.tabs(["Generate", "History"])

with page_generate:
    if not assignments:
        st.markdown(
            """
            ### How it works
            1. Add names under **Morning**, **Morning DPT**, **Evening**, and **Evening DPT** (one per line).
            2. Set the start date and number of weekends, then click **Generate rotation**.

            Each generation is saved to **History** automatically.
            """
        )
    else:
        _render_schedule_tabs(assignments, anchor_str, key_prefix="current_")

with page_history:
    entries = st.session_state["history_entries"]

    if not entries:
        st.info("No saved rotations yet. Generate a schedule to add one.")
    else:
        col_refresh, col_clear_all = st.columns([1, 1])
        with col_refresh:
            if st.button("Refresh history", use_container_width=True):
                st.session_state["history_entries"] = load_history()
                st.rerun()
        with col_clear_all:
            if st.button("Clear all history", use_container_width=True):
                clear_history()
                st.session_state["history_entries"] = []
                st.rerun()

        labels = {e.id: e.label for e in entries}
        selected_id = st.selectbox(
            "Past rotation",
            options=list(labels.keys()),
            format_func=lambda eid: labels[eid],
            key="history_select",
        )

        selected = next(e for e in entries if e.id == selected_id)

        col_load, col_delete = st.columns(2)
        with col_load:
            if st.button("Load into current view", type="primary", use_container_width=True):
                st.session_state["assignments"] = [
                    dict_to_assignment(row) for row in selected.assignments
                ]
                st.session_state["anchor"] = selected.anchor_saturday
                st.success("Loaded. Switch to the **Generate** tab to view.")
        with col_delete:
            if st.button("Delete this entry", use_container_width=True):
                delete_history_entry(selected_id)
                st.session_state["history_entries"] = load_history()
                st.rerun()

        with st.expander("Rosters used", expanded=False):
            for team_name, members in selected.rosters.items():
                st.markdown(f"**{team_name.replace('_', ' ').title()}**")
                st.write(", ".join(members) if members else "—")

        hist_assignments = [dict_to_assignment(row) for row in selected.assignments]
        _render_schedule_tabs(
            hist_assignments,
            selected.anchor_saturday,
            key_prefix=f"hist_{selected_id}_",
        )
