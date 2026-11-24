import type { DragEvent } from "react";
import type { Task } from "../types";
import { formatMinutes } from "../util";

export const DRAG_MIME = "application/x-ppos-task";

export function onTaskDragStart(e: DragEvent, task: Task) {
  e.dataTransfer.setData(DRAG_MIME, task.id);
  e.dataTransfer.setData("text/plain", task.title);
  e.dataTransfer.effectAllowed = "move";
}

export function draggedTaskId(e: DragEvent): string | null {
  return e.dataTransfer.getData(DRAG_MIME) || null;
}

interface Props {
  task: Task;
  onOpen: (id: string) => void;
  onToggleDone?: (task: Task) => void;
  highlight?: boolean;
  today?: string;
}

export function TaskCard({ task, onOpen, onToggleDone, highlight, today }: Props) {
  const done = task.status === "done";
  const overdue = !!(today && task.due_date && task.due_date < today && !done);
  return (
    <div
      className={`task-card p${task.priority} ${done ? "done" : ""} ${highlight ? "highlight" : ""}`}
      draggable
      onDragStart={(e) => onTaskDragStart(e, task)}
      onClick={() => onOpen(task.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter") onOpen(task.id);
        if (e.key === " " && onToggleDone) {
          e.preventDefault();
          onToggleDone(task);
        }
      }}
      tabIndex={0}
      role="button"
      aria-label={task.title}
    >
      {onToggleDone && (
        <input
          type="checkbox"
          checked={done}
          aria-label={done ? "Mark not done" : "Mark done"}
          onClick={(e) => e.stopPropagation()}
          onChange={() => onToggleDone(task)}
        />
      )}
      <div className="task-body">
        <div className="task-title">
          {highlight && <span className="star" aria-label="Top priority">★</span>}
          {task.title}
        </div>
        <div className="task-meta">
          {task.priority < 4 && <span className={`pill prio p${task.priority}`}>P{task.priority}</span>}
          {task.estimate_minutes !== null && <span>{formatMinutes(task.estimate_minutes)}</span>}
          {task.actual_minutes > 0 && <span title="Actual time">⏱ {formatMinutes(task.actual_minutes)}</span>}
          {task.due_date && <span className={overdue ? "overdue" : ""}>due {task.due_date}</span>}
          {task.tags.map((t) => (
            <span key={t} className="tag">
              #{t}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
