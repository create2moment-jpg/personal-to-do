// Mirrors apps/api/ppos_api/schemas.py. Keep in sync (OpenAPI codegen is a Phase 9 item).

export type TaskStatus = "backlog" | "planned" | "in_progress" | "blocked" | "done";

export const STATUS_LABEL: Record<TaskStatus, string> = {
  backlog: "Backlog",
  planned: "Planned",
  in_progress: "In progress",
  blocked: "Blocked / waiting",
  done: "Done",
};

export interface Task {
  id: string;
  title: string;
  description: string;
  notes: string;
  status: TaskStatus;
  priority: number;
  estimate_minutes: number | null;
  actual_minutes: number;
  project_id: string | null;
  area: string | null;
  parent_id: string | null;
  tags: string[];
  due_date: string | null;
  scheduled_date: string | null;
  recurrence: string | null;
  position: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export type NoteKind =
  | "general"
  | "journal"
  | "meeting"
  | "technical"
  | "project"
  | "idea"
  | "learning"
  | "career_evidence";

export const NOTE_KINDS: NoteKind[] = [
  "general",
  "journal",
  "meeting",
  "technical",
  "project",
  "idea",
  "learning",
  "career_evidence",
];

export interface NoteSummary {
  id: string;
  title: string;
  kind: NoteKind;
  note_date: string | null;
  tags: string[];
  version: number;
  updated_at: string;
}

export interface Note extends NoteSummary {
  body: string;
  project_id: string | null;
  created_at: string;
}

export interface NoteVersion {
  note_id: string;
  version: number;
  title: string;
  body: string;
  created_at: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  area: string | null;
  status: "active" | "paused" | "archived";
  color: string | null;
  created_at: string;
  updated_at: string;
}

export interface DailyReview {
  unfinished: string;
  blockers: string;
  learning: string;
  wins: string;
  tomorrow_first_task: string;
  completed_at: string | null;
}

export interface DailyPlan {
  day: string;
  capacity_minutes: number;
  objective: string;
  top_priority_ids: string[];
  review: DailyReview;
}

export interface Capacity {
  capacity_minutes: number;
  planned_minutes: number;
  unestimated_count: number;
  done_minutes: number;
  remaining_capacity: number;
  load_ratio: number;
  overcommitted: boolean;
}

export interface Today {
  day: string;
  plan: DailyPlan;
  tasks: Task[];
  overdue: Task[];
  due_today_unscheduled: Task[];
  capacity: Capacity;
  journal: Note | null;
}

export interface SearchHit {
  entity_type: "task" | "note" | "project" | "day";
  entity_id: string;
  title: string;
  snippet: string;
}

export interface CaptureResult {
  kind: string;
  task: Task | null;
  note: Note | null;
  warnings: string[];
}

export interface CapturePreview {
  kind: "task" | "idea" | "note";
  title: string;
  tags: string[];
  priority: number;
  estimate_minutes: number | null;
  scheduled_date: string | null;
  due_date: string | null;
  project_hint: string | null;
  project_name: string | null;
}

export interface Health {
  status: string;
  version: string;
  schema_version: number;
  data_dir: string;
  demo: boolean;
  ai: { enabled: boolean; note: string };
}
