"""Read-only iCalendar (.ics) parsing with recurrence expansion.

Works with Outlook exports ("Save calendar") and published calendars. Only
reads; nothing is ever written back. Attendee lists are deliberately ignored
(colleagues' personal data); only the organizer's display name is kept.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Any

import icalendar
import recurring_ical_events

from ppos.domain.meetings import ImportedEvent, ImportedSeries
from ppos.shared.errors import ValidationError

MAX_ICS_BYTES = 10 * 1024 * 1024
_DAYS = {"MO": "Mon", "TU": "Tue", "WE": "Wed", "TH": "Thu", "FR": "Fri", "SA": "Sat", "SU": "Sun"}
_FREE_STATUSES = {"FREE", "OOF", "WORKINGELSEWHERE"}


def cadence_from_rrule(rrule: Any) -> str | None:
    if not rrule:
        return None
    freq = (rrule.get("FREQ") or [""])[0]
    interval = int((rrule.get("INTERVAL") or [1])[0])
    days = [_DAYS.get(str(d)[-2:], str(d)) for d in rrule.get("BYDAY", [])]
    unit = {"DAILY": "day", "WEEKLY": "week", "MONTHLY": "month", "YEARLY": "year"}.get(
        freq, freq.lower()
    )
    base = f"Every {unit}" if interval == 1 else f"Every {interval} {unit}s"
    if freq == "DAILY" and interval == 1:
        base = "Daily"
    elif freq == "WEEKLY" and interval == 1:
        base = "Weekly"
    elif freq == "MONTHLY" and interval == 1:
        base = "Monthly"
    return f"{base} on {', '.join(days)}" if days else base


def _as_utc(value: date | datetime, default_tz: tzinfo) -> tuple[datetime, bool]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=default_tz)
        return value.astimezone(timezone.utc), False
    return datetime.combine(value, time(0), tzinfo=default_tz).astimezone(timezone.utc), True


def _text(component: Any, key: str) -> str | None:
    v = component.get(key)
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def parse_ics(
    content: str | bytes, window_start: datetime, window_end: datetime, default_tz: tzinfo
) -> tuple[list[ImportedEvent], list[ImportedSeries]]:
    raw = content.encode() if isinstance(content, str) else content
    if len(raw) > MAX_ICS_BYTES:
        raise ValidationError("calendar file is too large (max 10 MB)")
    try:
        cal = icalendar.Calendar.from_ical(raw)
    except ValueError as exc:
        raise ValidationError(f"not a valid iCalendar file: {exc}") from exc

    recurring_uids: dict[str, tuple[str, str | None]] = {}
    for comp in cal.walk("VEVENT"):
        uid = _text(comp, "UID")
        if uid and (comp.get("RRULE") or comp.get("RECURRENCE-ID")):
            title = _text(comp, "SUMMARY") or "(no title)"
            cadence = cadence_from_rrule(comp.get("RRULE"))
            prev = recurring_uids.get(uid)
            if prev is None or (cadence and not prev[1]):
                recurring_uids[uid] = (title, cadence)

    try:
        occurrences = recurring_ical_events.of(cal).between(window_start, window_end)
    except Exception as exc:  # library raises several types for malformed rules
        raise ValidationError(f"could not expand recurring events: {exc}") from exc

    events: list[ImportedEvent] = []
    seen: set[str] = set()
    for occ in occurrences:
        if str(occ.get("STATUS", "")).upper() == "CANCELLED":
            continue
        if str(occ.get("TRANSP", "")).upper() == "TRANSPARENT":
            continue
        if str(occ.get("X-MICROSOFT-CDO-BUSYSTATUS", "")).upper() in _FREE_STATUSES:
            continue
        dtstart = occ.decoded("DTSTART")
        start, all_day = _as_utc(dtstart, default_tz)
        if occ.get("DTEND") is not None:
            end, _ = _as_utc(occ.decoded("DTEND"), default_tz)
        elif occ.get("DURATION") is not None:
            end = start + occ.decoded("DURATION")
        else:
            end = start + (timedelta(days=1) if all_day else timedelta(0))
        if end - start > timedelta(hours=24):
            all_day = True
            end = start + timedelta(hours=24)
        uid = _text(occ, "UID") or f"no-uid-{_text(occ, 'SUMMARY')}-{start.isoformat()}"
        key = f"{uid}|{start.isoformat()}"
        if key in seen:
            continue
        seen.add(key)
        organizer = occ.get("ORGANIZER")
        org_name = (
            organizer.params.get("CN")
            if organizer is not None and hasattr(organizer, "params")
            else None
        )
        events.append(
            ImportedEvent(
                external_key=key,
                series_key=uid if uid in recurring_uids else None,
                title=_text(occ, "SUMMARY") or "(no title)",
                start_at=start,
                end_at=end,
                all_day=all_day,
                location=_text(occ, "LOCATION"),
                organizer=str(org_name) if org_name else None,
            )
        )
    series = [ImportedSeries(uid, t, c) for uid, (t, c) in recurring_uids.items()]
    return events, series
