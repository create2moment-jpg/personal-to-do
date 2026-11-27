import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { AlarmClock, CalendarClock, Clock, Flag, ListChecks, Repeat, Star } from "lucide-react";
import type { CSSProperties, KeyboardEvent } from "react";
import type { Project, Task } from "../lib/types";
import { startTaskDrag } from "../lib/drop";
import { describeRepeat } from "../lib/repeat";
import { DurationChip } from "./DurationPicker";
import { cx, formatMinutes, isoDay, relativeDay } from "../lib/util";

export interface TaskCardProps {
  task: Task;
  project?: Project;
  subtasks?: { done: number; total: number };
  starred?: boolean;
  onOpen: (id: string) => void;
  onToggleDone?: (task: Task) => void;
  onToggleStar?: (task: Task) => void;
  showSchedule?: boolean;
  overlay?: boolean;
  dragging?: boolean;
  style?: CSSProperties;
  dragProps?: Record<string, unknown>;
  innerRef?: (el: HTMLElement | null) => void;
}

export function TaskCard({
  task,
  project,
  subtasks,
  starred,
  onOpen,
  onToggleDone,
  onToggleStar,
  showSchedule,
  overlay,
  dragging,
  style,
  dragProps,
  innerRef,
}: TaskCardProps) {
  const done = task.status === "done";
  const today = isoDay();
  const { onKeyDown: dragKeyDown, ...restDrag } = (dragProps ?? {}) as { onKeyDown?: (e: KeyboardEvent<HTMLDivElement>) => void };
  const late = !done && task.due_date !== null && task.due_date < today;
  const dueSoon = !done && task.due_date !== null && task.due_date >= today;

  return (
    <div
      ref={innerRef}
      style={style}
      className={cx("task-card", done && "done", starred && "top", overlay && "overlay", dragging && "dragging")}
      onClick={() => onOpen(task.id)}
      onKeyDown={(e) => {
        dragKeyDown?.(e); // Space picks the card up for keyboard drag/drop
        if (e.key === "Enter") onOpen(task.id);
        if ((e.key === "x" || e.key === "X") && onToggleDone) {
          e.preventDefault();
          onToggleDone(task);
        }
      }}
      tabIndex={0}
      role="button"
      aria-label={`${task.title}${done ? " (done)" : ""}`}
      data-task-id={task.id}
      {...(dragProps ? {} : { draggable: true, onDragStart: (e: React.DragEvent) => startTaskDrag(e, task.id, task.title) })}
      {...restDrag}
    >
      {onToggleDone && (
        <input
          type="checkbox"
          className={cx("check", `p${task.priority}`)}
          checked={done}
          aria-label={done ? "Mark as not done" : "Mark as done"}
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
          onChange={() => onToggleDone(task)}
        />
      )}
      <div className="t-main">
        <div className="t-title">{task.title}</div>
        <div className="t-meta">
          {task.priority < 4 && (
            <span className={`prio-flag p${task.priority}`} title={`Priority ${task.priority}`}>
              <Flag fill="currentColor" /> P{task.priority}
            </span>
          )}
          {!done && !overlay ? (
            <DurationChip task={task} />
          ) : task.estimate_minutes !== null && (
            <span title="Estimate">
              <Clock /> {task.actual_minutes > 0 ? `${formatMinutes(task.actual_minutes)} / ` : ""}
              {formatMinutes(task.estimate_minutes)}
            </span>
          )}
          {task.recurrence && (
            <span title={describeRepeat(task.recurrence)} aria-label={describeRepeat(task.recurrence)}>
              <Repeat />
            </span>
          )}
          {subtasks && subtasks.total > 0 && (
            <span title="Subtasks">
              <ListChecks /> {subtasks.done}/{subtasks.total}
            </span>
          )}
          {showSchedule && task.scheduled_date && (
            <span>
              <CalendarClock /> {relativeDay(task.scheduled_date, today)}
            </span>
          )}
          {(late || dueSoon) && (
            <span className={cx(late && "late")} title="Due date">
              <AlarmClock /> {late ? "Overdue · " : "Due "}
              {relativeDay(task.due_date!, today)}
            </span>
          )}
          {project && (
            <span className="project-pill">
              <span className="dot" style={{ background: project.color ?? "var(--text-3)" }} />
              {project.name}
            </span>
          )}
          {task.tags.slice(0, 3).map((t) => (
            <span key={t} style={{ color: "var(--accent-text)" }}>
              #{t}
            </span>
          ))}
        </div>
      </div>
      {onToggleStar && !done && (
        <div className="t-actions">
          <button
            className={cx("btn icon sm ghost", starred && "starred")}
            aria-label={starred ? "Remove from top priorities" : "Make top priority"}
            title={starred ? "Remove from top priorities" : "Make top priority"}
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation();
              onToggleStar(task);
            }}
          >
            <Star fill={starred ? "currentColor" : "none"} />
          </button>
        </div>
      )}
    </div>
  );
}

/** Drag-and-drop wrapper (dnd-kit sortable: pointer, touch and keyboard). */
export function SortableTaskCard(props: TaskCardProps & { containerId: string }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: props.task.id,
    data: { container: props.containerId, task: props.task },
  });
  return (
    <TaskCard
      {...props}
      innerRef={setNodeRef}
      dragging={isDragging}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      dragProps={{ ...attributes, ...listeners, tabIndex: 0, role: "button" }}
    />
  );
}
