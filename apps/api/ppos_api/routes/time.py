"""Settings, meetings, calls, calendar import and time insights."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Query, Response, status

from ppos.domain.meetings import MeetingKind
from ppos_api.deps import ContainerDep
from ppos_api.schemas import (
    CallCreate,
    IcsImportIn,
    IcsImportOut,
    InsightsOut,
    MeetingOut,
    MeetingUpdate,
    NamedOut,
    RankedOut,
    SeriesOut,
    SeriesRankOut,
    SeriesUpdate,
    WorkspaceSettingsOut,
    WorkspaceSettingsUpdate,
)
from ppos_api.serializers import MeetingSerializer, day_time_out

router = APIRouter(tags=["time"])


def _settings_out(c: ContainerDep) -> WorkspaceSettingsOut:
    s = c.settings_service.get()
    return WorkspaceSettingsOut(**s.to_dict(), work_minutes=s.work_minutes)


@router.get("/api/settings", response_model=WorkspaceSettingsOut)
def get_settings(c: ContainerDep) -> WorkspaceSettingsOut:
    return _settings_out(c)


@router.patch("/api/settings", response_model=WorkspaceSettingsOut)
def update_settings(body: WorkspaceSettingsUpdate, c: ContainerDep) -> WorkspaceSettingsOut:
    c.settings_service.update(body.model_dump(exclude_none=True))
    return _settings_out(c)


@router.get("/api/meetings", response_model=list[MeetingOut])
def list_meetings(c: ContainerDep, start: date, end: date) -> list[MeetingOut]:
    meetings, series = c.meetings.between(start, end)
    ser = MeetingSerializer(c)
    return [ser(m, series) for m in meetings]


@router.post("/api/meetings", response_model=MeetingOut, status_code=status.HTTP_201_CREATED)
def log_call(body: CallCreate, c: ContainerDep) -> MeetingOut:
    m = c.meetings.log_call(
        title=body.title,
        start_at=body.start_at,
        minutes=body.minutes,
        people=body.people,
        topic=body.topic,
        note=body.note,
        rating=body.rating,
        kind=MeetingKind(body.kind),
    )
    return MeetingSerializer(c)(m, {})


@router.patch("/api/meetings/{meeting_id}", response_model=MeetingOut)
def update_meeting(meeting_id: str, body: MeetingUpdate, c: ContainerDep) -> MeetingOut:
    changes = body.model_dump(exclude_unset=True)
    if changes.pop("clear_status", False):
        changes["status"] = None
    m = c.meetings.update(meeting_id, changes)
    series = {}
    if m.series_key:
        s = c.meetings.between(m.start_at.date(), m.start_at.date())[1].get(m.series_key)
        series = {m.series_key: s} if s else {}
    return MeetingSerializer(c)(m, series)


@router.delete("/api/meetings/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(meeting_id: str, c: ContainerDep) -> Response:
    c.meetings.delete(meeting_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/meeting-series", response_model=list[SeriesOut])
def list_series(c: ContainerDep) -> list[SeriesOut]:
    return [
        SeriesOut(
            series_key=o.series.series_key,
            title=o.series.title,
            cadence=o.series.cadence,
            default_status=o.series.default_status,
            rating=o.series.rating,
            notes=o.series.notes,
            topic=o.topic_name,
            occurrences_4w=o.occurrences_4w,
            avg_minutes=o.avg_minutes,
            minutes_per_month=o.minutes_per_month,
            next_start=o.next_start,
            last_start=o.last_start,
        )
        for o in c.meetings.series_overview()
    ]


@router.patch("/api/meeting-series/{series_key:path}", response_model=dict)
def update_series(series_key: str, body: SeriesUpdate, c: ContainerDep) -> dict[str, str]:
    s = c.meetings.update_series(series_key, body.model_dump(exclude_unset=True))
    return {"series_key": s.series_key, "default_status": s.default_status}


@router.post("/api/calendar/import", response_model=IcsImportOut)
def import_calendar(body: IcsImportIn, c: ContainerDep) -> IcsImportOut:
    r = c.meetings.import_ics(body.filename, body.content)
    return IcsImportOut(**r.__dict__)


@router.get("/api/calendar/last-import")
def last_import(c: ContainerDep) -> dict[str, object] | None:
    return c.meetings.last_import()


@router.get("/api/people", response_model=list[NamedOut])
def people(c: ContainerDep) -> list[NamedOut]:
    return [NamedOut.model_validate(p) for p in c.meetings.people()]


@router.delete("/api/people/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def forget_person(person_id: str, c: ContainerDep) -> Response:
    c.meetings.forget_person(person_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/topics", response_model=list[NamedOut])
def topics(c: ContainerDep) -> list[NamedOut]:
    return [NamedOut.model_validate(t) for t in c.meetings.topics()]


@router.get("/api/insights/time", response_model=InsightsOut)
def time_insights(
    c: ContainerDep,
    start: date | None = None,
    end: date | None = None,
    days: int = Query(default=7, ge=1, le=366),
) -> InsightsOut:
    end = end or c.clock.today()
    start = start or end - timedelta(days=days - 1)
    r = c.meetings.insights(start, end)
    return InsightsOut(
        start=r.start,
        end=r.end,
        days=[day_time_out(d) for d in r.days],
        meeting_minutes=r.meeting_minutes,
        work_minutes=r.work_minutes,
        available_minutes=r.available_minutes,
        meetings_count=r.meetings_count,
        calls_count=r.calls_count,
        by_person=[RankedOut(name=n, minutes=m, count=k) for n, m, k in r.by_person],
        by_topic=[RankedOut(name=n, minutes=m, count=k) for n, m, k in r.by_topic],
        by_series=[
            SeriesRankOut(series_key=s, title=t, minutes=m, count=k, rating=rt)
            for s, t, m, k, rt in r.by_series
        ],
        rated_minutes=r.rated_minutes,
        avg_rating=r.avg_rating,
        reconsider=r.reconsider,
    )
