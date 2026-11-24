"""Domain → response model conversion that needs lookups (people, topics, series)."""

from __future__ import annotations

from ppos.bootstrap import Container
from ppos.domain.meetings import DayTime, Meeting, MeetingSeries
from ppos_api.schemas import DayTimeOut, MeetingOut


class MeetingSerializer:
    def __init__(self, c: Container) -> None:
        self.people = {p.id: p.name for p in c.meetings.people()}
        self.topics = {t.id: t.name for t in c.meetings.topics()}

    def __call__(self, m: Meeting, series: dict[str, MeetingSeries]) -> MeetingOut:
        s = series.get(m.series_key) if m.series_key else None
        topic_id = m.topic_id or (s.topic_id if s else None)
        return MeetingOut(
            id=m.id,
            source=m.source,
            kind=m.kind.value,
            title=m.title,
            start_at=m.start_at,
            end_at=m.end_at,
            all_day=m.all_day,
            location=m.location,
            organizer=m.organizer,
            series_key=m.series_key,
            status=m.status.value if m.status else None,
            effective_status=m.effective_status(s).value,
            counted_minutes=m.counted_minutes(s),
            duration_minutes=m.duration_minutes,
            attended_minutes=m.attended_minutes,
            rating=m.rating,
            note=m.note,
            topic=self.topics.get(topic_id) if topic_id else None,
            people=[self.people[p] for p in m.people_ids if p in self.people],
            series_default_status=s.default_status if s else None,
            cadence=s.cadence if s else None,
        )


def day_time_out(d: DayTime) -> DayTimeOut:
    return DayTimeOut(
        day=d.day,
        work_minutes=d.work_minutes,
        meeting_minutes=d.meeting_minutes,
        meeting_minutes_total=d.meeting_minutes_total,
        available_minutes=d.available_minutes,
        capacity_minutes=d.capacity_minutes,
    )
