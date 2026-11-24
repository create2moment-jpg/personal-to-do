import type { DragEndEvent } from "@dnd-kit/core";
import type { DragEvent } from "react";
import { toast } from "sonner";
import { api } from "./api";
import { invalidateTasks, invalidateTime, queryClient } from "./queries";
import { addDays, isoDay, relativeDay } from "./util";

/*
 * Cross-view drag and drop. Anything tagged with data-drop-target accepts
 * tasks (and, for "book", notes). Lists use native HTML5 drag; the dnd-kit
 * boards (Today, Week) fall back to these targets when dropped outside.
 */

export const TASK_MIME = "application/x-ppos-task";
export const NOTE_MIME = "application/x-ppos-note";

export type DropTarget = "today" | "tomorrow" | "backlog" | "sprint" | "book" | `day:${string}` | `project:${string}`;

export function startTaskDrag(e: DragEvent, taskId: string, title: string) {
  e.dataTransfer.setData(TASK_MIME, taskId);
  e.dataTransfer.setData("text/plain", title);
  e.dataTransfer.effectAllowed = "move";
}

export function startNoteDrag(e: DragEvent, noteId: string, title: string) {
  e.dataTransfer.setData(NOTE_MIME, noteId);
  e.dataTransfer.setData("text/plain", title);
  e.dataTransfer.effectAllowed = "copy";
}

export async function dropTask(target: DropTarget, taskId: string): Promise<void> {
  try {
    if (target === "today" || target === "tomorrow" || target.startsWith("day:")) {
      const day = target === "today" ? isoDay() : target === "tomorrow" ? addDays(isoDay(), 1) : target.slice(4);
      await api.moveTask(taskId, { scheduled_date: day });
      toast.success(`Planned for ${relativeDay(day)}`);
    } else if (target === "backlog") {
      await api.moveTask(taskId, { status: "backlog" });
      toast.success("Moved to the backlog");
    } else if (target === "sprint") {
      const sprint = await api.currentSprint();
      if (!sprint) {
        toast("No active or planned sprint", { description: "Create one on the Sprint page first." });
        return;
      }
      await api.addToSprint(sprint.id, [taskId], "committed");
      toast.success(`Committed to ${sprint.name}`);
    } else if (target.startsWith("project:")) {
      const projectId = target.slice(8);
      await api.updateTask(taskId, { project_id: projectId });
      toast.success("Moved to project");
    } else {
      toast("Drop a note here to turn it into a prompt page");
      return;
    }
    invalidateTasks();
    invalidateTime();
  } catch (err) {
    toast.error((err as Error).message);
  }
}

/** A note dropped on the Prompt Book becomes a new page in the first book. */
export async function dropNoteOnBook(noteId: string): Promise<string | null> {
  try {
    const note = await api.note(noteId);
    let books = await api.books();
    if (books.length === 0) books = [await api.createBook({ title: "My prompts", emoji: "📘" })];
    const page = await api.createNode({ book_id: books[0]!.id, kind: "page", title: note.title, body: note.body });
    void queryClient.invalidateQueries({ queryKey: ["book-tree"] });
    toast.success("Added to your Prompt Book", { description: note.title });
    return page.id;
  } catch (err) {
    toast.error((err as Error).message);
    return null;
  }
}

/** Props for an element that accepts native drops; `onOver` toggles a highlight. */
export function dropProps(target: DropTarget, onOver: (over: boolean) => void, after?: (pageId?: string) => void) {
  return {
    "data-drop-target": target,
    onDragOver: (e: DragEvent) => {
      const types = e.dataTransfer.types;
      if (types.includes(TASK_MIME) || (target === "book" && types.includes(NOTE_MIME))) {
        e.preventDefault();
        onOver(true);
      }
    },
    onDragLeave: () => onOver(false),
    onDrop: async (e: DragEvent) => {
      e.preventDefault();
      onOver(false);
      const taskId = e.dataTransfer.getData(TASK_MIME);
      const noteId = e.dataTransfer.getData(NOTE_MIME);
      if (taskId) {
        await dropTask(target, taskId);
        after?.();
      } else if (noteId && target === "book") after?.((await dropNoteOnBook(noteId)) ?? undefined);
    },
  };
}

/** For dnd-kit boards: if the card was released over a data-drop-target, handle it. */
export function dropOutsideBoard(e: DragEndEvent): boolean {
  const start = e.activatorEvent as PointerEvent;
  if (!("clientX" in start)) return false; // keyboard drags stay inside the board
  const x = start.clientX + e.delta.x;
  const y = start.clientY + e.delta.y;
  // The drag overlay sits under the pointer, so look through every layer.
  const el = document
    .elementsFromPoint(x, y)
    .map((n) => n.closest<HTMLElement>("[data-drop-target]"))
    .find((n): n is HTMLElement => !!n && !n.closest(".board, .week-grid, .tray"));
  const target = el?.dataset.dropTarget as DropTarget | undefined;
  if (!target) return false;
  void dropTask(target, String(e.active.id));
  return true;
}
