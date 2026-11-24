import type {
  CaptureResult,
  DailyPlan,
  DailyReview,
  Note,
  NoteKind,
  NoteSummary,
  NoteVersion,
  Project,
  SearchHit,
  Task,
  TaskStatus,
  Today,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = data.detail.map((d) => d.msg).join("; ");
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null) p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  today: (day?: string) => request<Today>("GET", `/api/today${qs({ day })}`),
  updateDay: (day: string, changes: Partial<Pick<DailyPlan, "objective" | "capacity_minutes" | "top_priority_ids">>) =>
    request<DailyPlan>("PATCH", `/api/days/${day}`, changes),
  saveReview: (day: string, changes: Partial<DailyReview> & { complete?: boolean }) =>
    request<DailyPlan>("PUT", `/api/days/${day}/review`, changes),
  reviewDraft: (day: string) =>
    request<{ completed: string[]; unfinished: string; blockers: string; tomorrow_first_task: string }>(
      "GET",
      `/api/days/${day}/review-draft`,
    ),
  rollOver: (day: string) => request<Task[]>("POST", `/api/days/${day}/roll-over`, {}),
  journal: (day: string) => request<Note>("POST", `/api/days/${day}/journal`),

  tasks: (params: { status?: TaskStatus; unscheduled?: boolean; project_id?: string; parent_id?: string; top_level?: boolean; tag?: string } = {}) =>
    request<Task[]>("GET", `/api/tasks${qs(params)}`),
  task: (id: string) => request<Task>("GET", `/api/tasks/${id}`),
  createTask: (data: Partial<Task> & { title: string }) => request<Task>("POST", "/api/tasks", data),
  updateTask: (id: string, changes: Partial<Task>) => request<Task>("PATCH", `/api/tasks/${id}`, changes),
  moveTask: (id: string, move: { status?: TaskStatus; scheduled_date?: string; unschedule?: boolean; position?: number }) =>
    request<Task>("POST", `/api/tasks/${id}/move`, move),
  deleteTask: (id: string) => request<void>("DELETE", `/api/tasks/${id}`),

  notes: (params: { kind?: NoteKind } = {}) => request<NoteSummary[]>("GET", `/api/notes${qs(params)}`),
  note: (id: string) => request<Note>("GET", `/api/notes/${id}`),
  createNote: (data: Partial<Note>) => request<Note>("POST", "/api/notes", data),
  updateNote: (id: string, changes: Partial<Note> & { snapshot?: boolean }) =>
    request<Note>("PATCH", `/api/notes/${id}`, changes),
  deleteNote: (id: string) => request<void>("DELETE", `/api/notes/${id}`),
  versions: (id: string) => request<NoteVersion[]>("GET", `/api/notes/${id}/versions`),
  restoreVersion: (id: string, v: number) => request<Note>("POST", `/api/notes/${id}/versions/${v}/restore`),

  projects: () => request<Project[]>("GET", "/api/projects"),
  createProject: (data: { name: string; area?: string; description?: string }) =>
    request<Project>("POST", "/api/projects", data),

  capture: (text: string) => request<CaptureResult>("POST", "/api/capture", { text }),
  search: (q: string) => request<SearchHit[]>("GET", `/api/search${qs({ q })}`),
};
