from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query, Response, status

from ppos.application.ports import TaskQuery
from ppos.domain.tasks import Priority, TaskStatus
from ppos_api.deps import ContainerDep
from ppos_api.schemas import TaskCreate, TaskMove, TaskOut, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut])
def list_tasks(
    c: ContainerDep,
    status_: list[TaskStatus] = Query(default=[], alias="status"),  # noqa: B008
    scheduled_date: date | None = None,
    unscheduled: bool = False,
    project_id: str | None = None,
    parent_id: str | None = None,
    top_level: bool = False,
    tag: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[TaskOut]:
    tasks = c.tasks.find(
        TaskQuery(
            statuses=tuple(status_),
            scheduled_date=scheduled_date,
            unscheduled_only=unscheduled,
            project_id=project_id,
            parent_id=parent_id,
            top_level_only=top_level,
            tag=tag,
            limit=limit,
            offset=offset,
        )
    )
    return [TaskOut.model_validate(t) for t in tasks]


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(body: TaskCreate, c: ContainerDep) -> TaskOut:
    data = body.model_dump()
    title = data.pop("title")
    task_status = data.pop("status")
    scheduled = data.pop("scheduled_date")
    data["priority"] = Priority(data["priority"])
    return TaskOut.model_validate(
        c.tasks.create(title, status=task_status, scheduled_date=scheduled, **data)
    )


@router.get("/trash", response_model=list[TaskOut])
def trash(c: ContainerDep) -> list[TaskOut]:
    """Deleted tasks, newest first; kept for 30 days."""
    return [TaskOut.model_validate(t) for t in c.tasks.trash()]


@router.post("/{task_id}/restore", response_model=TaskOut)
def restore_task(task_id: str, c: ContainerDep) -> TaskOut:
    return TaskOut.model_validate(c.tasks.restore(task_id))


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: str, c: ContainerDep) -> TaskOut:
    return TaskOut.model_validate(c.tasks.get(task_id))


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(task_id: str, body: TaskUpdate, c: ContainerDep) -> TaskOut:
    return TaskOut.model_validate(c.tasks.update(task_id, body.model_dump(exclude_unset=True)))


@router.post("/{task_id}/move", response_model=TaskOut)
def move_task(task_id: str, body: TaskMove, c: ContainerDep) -> TaskOut:
    return TaskOut.model_validate(
        c.tasks.move(
            task_id,
            status=body.status,
            scheduled_date=body.scheduled_date,
            unschedule=body.unschedule,
            position=body.position,
        )
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str, c: ContainerDep) -> Response:
    c.tasks.delete(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{task_id}/dependencies", response_model=list[str])
def list_dependencies(task_id: str, c: ContainerDep) -> list[str]:
    return c.tasks.dependencies_of(task_id)


@router.put("/{task_id}/dependencies/{depends_on}", status_code=status.HTTP_204_NO_CONTENT)
def add_dependency(task_id: str, depends_on: str, c: ContainerDep) -> Response:
    c.tasks.add_dependency(task_id, depends_on)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{task_id}/dependencies/{depends_on}", status_code=status.HTTP_204_NO_CONTENT)
def remove_dependency(task_id: str, depends_on: str, c: ContainerDep) -> Response:
    c.tasks.remove_dependency(task_id, depends_on)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
