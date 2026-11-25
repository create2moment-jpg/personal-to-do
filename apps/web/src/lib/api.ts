import type {
  RecurrenceRule,
  SeriesPlan,
  AiConfigState,
  AiTestReport,
  LlmConfig,
  CareerMatrix,
  EvidenceSuggestion,
  Expectation,
  Fact,
  FactRun,
  FactStatus,
  DocHit,
  DocumentDetail,
  DocumentInfo,
  AiStatus,
  Book,
  BookNode,
  Improvement,
  NodeKind,
  Page,
  PromptVersion,
  IcsImportResult,
  Meeting,
  MeetingSeries,
  Named,
  Sprint,
  SprintSummary,
  TimeInsights,
  Week,
  WeeklyPlan,
  WeekReview,
  WorkspaceSettings,
  CapturePreview,
  CaptureResult,
  Health,
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
  updateDay: (day: string, changes: Partial<Pick<DailyPlan, "objective" | "capacity_minutes" | "top_priority_ids" | "capacity_mode">>) =>
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

  tasks: (params: { status?: TaskStatus; unscheduled?: boolean; project_id?: string; parent_id?: string; top_level?: boolean; tag?: string; limit?: number } = {}) =>
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
  createProject: (data: { name: string; area?: string; description?: string; color?: string }) =>
    request<Project>("POST", "/api/projects", data),

  settings: () => request<WorkspaceSettings>("GET", "/api/settings"),
  updateSettings: (changes: Partial<WorkspaceSettings>) => request<WorkspaceSettings>("PATCH", "/api/settings", changes),

  sprints: () => request<Sprint[]>("GET", "/api/sprints"),
  currentSprint: () => request<Sprint | null>("GET", "/api/sprints/current"),
  createSprint: (data: Partial<Sprint>) => request<Sprint>("POST", "/api/sprints", data),
  updateSprint: (id: string, changes: Partial<Sprint>) => request<Sprint>("PATCH", `/api/sprints/${id}`, changes),
  deleteSprint: (id: string) => request<void>("DELETE", `/api/sprints/${id}`),
  startSprint: (id: string) => request<Sprint>("POST", `/api/sprints/${id}/start`),
  sprintSummary: (id: string) => request<SprintSummary>("GET", `/api/sprints/${id}/summary`),
  addToSprint: (id: string, task_ids: string[], commitment: "committed" | "stretch" = "committed") =>
    request<Task[]>("POST", `/api/sprints/${id}/tasks`, { task_ids, commitment }),
  removeFromSprint: (taskId: string) => request<Task>("DELETE", `/api/sprints/tasks/${taskId}`),
  completeSprint: (id: string, body: { rollover: "next" | "backlog"; summary?: string; lessons?: string }) =>
    request<{ sprint: Sprint; next_sprint: Sprint | null; rolled_over: number }>("POST", `/api/sprints/${id}/complete`, body),

  week: (day: string) => request<Week>("GET", `/api/weeks/${day}`),
  updateWeek: (day: string, changes: Partial<WeeklyPlan> & { complete_review?: boolean }) =>
    request<WeeklyPlan>("PATCH", `/api/weeks/${day}`, changes),
  weekReview: (day: string) => request<WeekReview>("GET", `/api/weeks/${day}/review`),
  rollOverWeek: (day: string) => request<{ moved: number }>("POST", `/api/weeks/${day}/roll-over`),

  meetings: (start: string, end: string) => request<Meeting[]>("GET", `/api/meetings${qs({ start, end })}`),
  logCall: (data: { title?: string; people: string[]; topic?: string | null; start_at: string; minutes: number; note?: string; rating?: number | null; kind?: "call" | "meeting" }) =>
    request<Meeting>("POST", "/api/meetings", data),
  updateMeeting: (id: string, changes: Partial<Omit<Meeting, "people">> & { people?: string[]; minutes?: number; clear_status?: boolean }) =>
    request<Meeting>("PATCH", `/api/meetings/${id}`, changes),
  deleteMeeting: (id: string) => request<void>("DELETE", `/api/meetings/${id}`),
  meetingSeries: () => request<MeetingSeries[]>("GET", "/api/meeting-series"),
  scheduleMeeting: (body: { title: string; day: string; start_time: string; minutes: number; people: string[]; topic: string | null; location: string | null; kind: "meeting" | "call"; recurrence: RecurrenceRule | null }) =>
    request<{ meeting?: Meeting; series_key?: string; cadence?: string; title?: string }>("POST", "/api/meetings/schedule", body),
  editSeriesPlan: (key: string, changes: Partial<Omit<SeriesPlan, "first_day">> & { title?: string }) =>
    request<{ series_key: string; cadence: string; title: string }>("PATCH", `/api/meeting-series/${encodeURIComponent(key)}/plan`, changes),
  endSeries: (key: string) => request<{ removed: number }>("DELETE", `/api/meeting-series/${encodeURIComponent(key)}`),
  updateSeries: (key: string, changes: Partial<Pick<MeetingSeries, "default_status" | "rating" | "notes">> & { topic?: string | null }) =>
    request<unknown>("PATCH", `/api/meeting-series/${encodeURIComponent(key)}`, changes),
  importCalendar: (filename: string, content: string) => request<IcsImportResult>("POST", "/api/calendar/import", { filename, content }),
  lastImport: () => request<{ filename: string; imported_at: string; events: number; series: number } | null>("GET", "/api/calendar/last-import"),
  people: () => request<Named[]>("GET", "/api/people"),
  topics: () => request<Named[]>("GET", "/api/topics"),
  insights: (days: number) => request<TimeInsights>("GET", `/api/insights/time${qs({ days })}`),

  books: () => request<Book[]>("GET", "/api/books"),
  createBook: (data: { title: string; emoji?: string | null }) => request<Book>("POST", "/api/books", data),
  updateBook: (id: string, changes: Partial<Book>) => request<Book>("PATCH", `/api/books/${id}`, changes),
  deleteBook: (id: string) => request<void>("DELETE", `/api/books/${id}`),
  bookTree: (id: string) => request<{ book: Book; nodes: BookNode[] }>("GET", `/api/books/${id}/tree`),
  createNode: (data: { book_id: string; kind: NodeKind; title?: string; parent_id?: string | null; body?: string; emoji?: string | null }) =>
    request<Page>("POST", "/api/book-nodes", data),
  node: (id: string) => request<Page>("GET", `/api/book-nodes/${id}`),
  updateNode: (id: string, changes: Partial<Pick<Page, "title" | "emoji" | "body" | "tags" | "rating">>) =>
    request<Page>("PATCH", `/api/book-nodes/${id}`, changes),
  moveNode: (id: string, parent_id: string | null, position?: number) =>
    request<Page>("POST", `/api/book-nodes/${id}/move`, { parent_id, position }),
  deleteNode: (id: string) => request<void>("DELETE", `/api/book-nodes/${id}`),
  pageVersions: (id: string) => request<PromptVersion[]>("GET", `/api/book-nodes/${id}/versions`),
  snapshotPage: (id: string) => request<PromptVersion>("POST", `/api/book-nodes/${id}/snapshot`),
  restorePage: (id: string, v: number) => request<Page>("POST", `/api/book-nodes/${id}/versions/${v}/restore`),
  usePage: (id: string, values: Record<string, string>, body?: string) =>
    request<{ text: string }>("POST", `/api/book-nodes/${id}/use`, { values, body }),
  improvePage: (id: string, style: string, body?: string) => request<Improvement>("POST", `/api/book-nodes/${id}/improve`, { style, body }),
  acceptVersion: (id: string, v: number) => request<Page>("POST", `/api/book-nodes/${id}/versions/${v}/accept`),
  aiStatus: () => request<AiStatus>("GET", "/api/ai/status"),
  aiConfig: () => request<AiConfigState>("GET", "/api/ai/config"),
  applyAiConfig: (body: LlmConfig & { api_key?: string | null; clear_key?: boolean }) => request<AiConfigState>("PUT", "/api/ai/config", body),
  testAiConfig: (body: LlmConfig & { api_key?: string | null }) => request<AiTestReport>("POST", "/api/ai/test", body),

  documents: () => request<DocumentInfo[]>("GET", "/api/documents"),
  document: (id: string) => request<DocumentDetail>("GET", `/api/documents/${id}`),
  updateDocument: (id: string, changes: { title?: string; kind?: string }) => request<DocumentInfo>("PATCH", `/api/documents/${id}`, changes),
  deleteDocument: (id: string) => request<void>("DELETE", `/api/documents/${id}`),
  reindexDocument: (id: string) => request<{ queued: number }>("POST", `/api/documents/${id}/reindex`),
  searchDocuments: (q: string) => request<DocHit[]>("GET", `/api/documents/search${qs({ q })}`),
  uploadDocument: async (file: File, kind: string) => {
    const res = await fetch(`/api/documents${qs({ filename: file.name, kind })}`, { method: "POST", body: file });
    const data = (await res.json()) as { document?: DocumentInfo; duplicate?: boolean; detail?: string };
    if (!res.ok) throw new ApiError(res.status, data.detail ?? res.statusText);
    return data as { document: DocumentInfo; duplicate: boolean };
  },

  extractFacts: (docId: string) => request<FactRun>("POST", `/api/documents/${docId}/facts/extract`),
  documentFacts: (docId: string) => request<{ run: FactRun | null; facts: Fact[] }>("GET", `/api/documents/${docId}/facts`),
  facts: (params: { kind?: string; status?: string } = {}) => request<Fact[]>("GET", `/api/facts${qs(params)}`),
  reviewFact: (id: string, changes: { status?: FactStatus; statement?: string; note?: string }) => request<Fact>("PATCH", `/api/facts/${id}`, changes),
  career: () => request<CareerMatrix>("GET", "/api/career"),
  addExpectation: (body: { level: string; text: string; competency?: string | null }) => request<Expectation>("POST", "/api/career/expectations", body),
  updateExpectation: (id: string, changes: { level?: string; text?: string; competency?: string }) => request<Expectation>("PATCH", `/api/career/expectations/${id}`, changes),
  deleteExpectation: (id: string) => request<void>("DELETE", `/api/career/expectations/${id}`),
  evidenceSuggestions: (id: string) => request<EvidenceSuggestion[]>("GET", `/api/career/expectations/${id}/suggestions`),
  linkEvidence: (id: string, factId: string) => request<{ id: string; origin: string }>("POST", `/api/career/expectations/${id}/evidence`, { fact_id: factId }),
  unlinkEvidence: (id: string, factId: string) => request<void>("DELETE", `/api/career/expectations/${id}/evidence/${factId}`),
  gapTask: (id: string) => request<Task>("POST", `/api/career/expectations/${id}/gap-task`),

  capture: (text: string) => request<CaptureResult>("POST", "/api/capture", { text }),
  capturePreview: (text: string) => request<CapturePreview>("POST", "/api/capture/preview", { text }),
  health: () => request<Health>("GET", "/api/health"),
  updateProject: (id: string, changes: Partial<Project>) => request<Project>("PATCH", `/api/projects/${id}`, changes),
  search: (q: string) => request<SearchHit[]>("GET", `/api/search${qs({ q })}`),
};
