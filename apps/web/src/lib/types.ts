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
  sprint_id?: string | null;
  commitment?: "committed" | "stretch" | null;
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
  capacity_mode?: "auto" | "manual";
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
  time: DayTime | null;
  meetings: Meeting[];
}

export interface SearchHit {
  entity_type: "task" | "note" | "project" | "day" | "page" | "chunk";
  entity_id: string;
  title: string;
  snippet: string;
}

export interface CaptureResult {
  kind: string;
  task: Task | null;
  note: Note | null;
  warnings: string[];
  meeting?: Meeting | null;
}

export interface CapturePreview {
  kind: "task" | "idea" | "note" | "call";
  people?: string[];
  start_time?: string | null;
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

// ------------------------------------------------------------------ Phase 2/3

export interface WorkspaceSettings {
  timezone: string;
  work_start: string;
  work_end: string;
  workdays: number[];
  buffer_percent: number;
  sprint_length_days: number;
  work_minutes: number;
}

export type SprintStatus = "planned" | "active" | "completed";

export interface Sprint {
  id: string;
  name: string;
  goal: string;
  start_date: string;
  end_date: string;
  status: SprintStatus;
  review_summary: string;
  review_lessons: string;
  completed_at: string | null;
}

export interface BurndownPoint {
  day: string;
  remaining_minutes: number; // -1 = future
  ideal_minutes: number;
  scope_minutes: number;
}

export interface SprintSummary {
  sprint: Sprint;
  tasks: Task[];
  committed_total: number;
  committed_done: number;
  stretch_total: number;
  stretch_done: number;
  committed_minutes: number;
  remaining_minutes: number;
  added_after_start: string[];
  removed_after_start: string[];
  burndown: BurndownPoint[];
  days_total: number;
  days_elapsed: number;
  completion_rate: number;
}

export type Attendance = "attended" | "skipped" | "partial";

export interface Meeting {
  id: string;
  source: "ics" | "manual";
  kind: "meeting" | "call";
  title: string;
  start_at: string;
  end_at: string;
  all_day: boolean;
  location: string | null;
  organizer: string | null;
  series_key: string | null;
  status: Attendance | null;
  effective_status: Attendance;
  counted_minutes: number;
  duration_minutes: number;
  attended_minutes: number | null;
  rating: number | null;
  note: string;
  topic: string | null;
  people: string[];
  series_default_status: "attending" | "skipped" | null;
  cadence: string | null;
}

export interface MeetingSeries {
  series_key: string;
  title: string;
  cadence: string | null;
  default_status: "attending" | "skipped";
  rating: number | null;
  notes: string;
  topic: string | null;
  occurrences_4w: number;
  avg_minutes: number;
  minutes_per_month: number;
  next_start: string | null;
  last_start: string | null;
}

export interface DayTime {
  day: string;
  work_minutes: number;
  meeting_minutes: number;
  meeting_minutes_total: number;
  available_minutes: number;
  capacity_minutes: number;
}

export interface WeekDay {
  day: string;
  tasks: Task[];
  time: DayTime;
  capacity_minutes: number;
  planned_minutes: number;
  meetings: Meeting[];
}

export interface WeeklyObjective {
  text: string;
  done: boolean;
}

export interface WeeklyPlan {
  week_start: string;
  objectives: WeeklyObjective[];
  notes: string;
  review_wins: string;
  review_lessons: string;
  review_risks: string;
  review_next_focus: string;
  review_completed_at: string | null;
}

export interface Week {
  week_start: string;
  plan: WeeklyPlan;
  days: WeekDay[];
  sprint: Sprint | null;
  sprint_backlog: Task[];
}

export interface WeekReview {
  week_start: string;
  planned: number;
  done: number;
  open: number;
  done_titles: string[];
  open_titles: string[];
  estimate_minutes: number;
  actual_minutes: number;
  meeting_minutes: number;
  available_minutes: number;
  work_minutes: number;
  objectives: WeeklyObjective[];
}

export interface Ranked {
  name: string;
  minutes: number;
  count: number;
}

export interface TimeInsights {
  start: string;
  end: string;
  days: DayTime[];
  meeting_minutes: number;
  work_minutes: number;
  available_minutes: number;
  meetings_count: number;
  calls_count: number;
  by_person: Ranked[];
  by_topic: Ranked[];
  by_series: { series_key: string; title: string; minutes: number; count: number; rating: number | null }[];
  rated_minutes: number;
  avg_rating: number | null;
  reconsider: { series_key: string; title: string; minutes: number; rating: number | null; suggestion: string }[];
}

export interface Named {
  id: string;
  name: string;
}

export interface IcsImportResult {
  events: number;
  created: number;
  updated: number;
  cancelled: number;
  series: number;
}

// ------------------------------------------------------------------ Prompt Book
export type NodeKind = "chapter" | "section" | "page";

export interface Book {
  id: string;
  title: string;
  emoji: string | null;
  description: string;
}

export interface BookNode {
  id: string;
  book_id: string;
  parent_id: string | null;
  kind: NodeKind;
  title: string;
  emoji: string | null;
  position: number;
  updated_at: string;
  use_count: number;
  variables: string[];
}

export interface Page extends BookNode {
  body: string;
  tags: string[];
  version: number;
  last_used_at: string | null;
  rating: number | null;
  created_at: string;
}

export interface PromptVersion {
  version: number;
  body: string;
  source: "original" | "edited" | "ai" | "used" | "restored";
  model: string | null;
  prompt_template: string | null;
  note: string;
  created_at: string;
}

export interface Improvement {
  original: string;
  improved: string;
  style: string;
  model: string;
  template: string;
  latency_ms: number;
  version: number;
}

export interface AiStatus {
  enabled: boolean;
  provider: string;
  model: string;
  reachable: boolean;
  local_only: boolean;
}

// ------------------------------------------------------------------ Knowledge
export type DocStatus = "queued" | "processing" | "ready" | "needs_ocr" | "failed";

export interface DocumentInfo {
  id: string;
  title: string;
  filename: string;
  mime: string;
  sha256: string;
  size_bytes: number;
  kind: string;
  status: DocStatus;
  error: string | null;
  pages: number | null;
  chars: number | null;
  extractor_version: string | null;
  created_at: string;
  processed_at: string | null;
}

export interface DocChunk {
  id: string;
  seq: number;
  page_start: number | null;
  page_end: number | null;
  section: string | null;
  text: string;
}

export interface DocumentDetail extends DocumentInfo {
  chunks: DocChunk[];
}

export interface DocHit {
  document_id: string;
  document_title: string;
  chunk_id: string;
  page_start: number | null;
  page_end: number | null;
  section: string | null;
  snippet: string;
}

export type FactStatus = "proposed" | "accepted" | "rejected";

export interface Fact {
  id: string;
  document_id: string;
  chunk_id: string | null;
  page: number | null;
  section: string | null;
  kind: string;
  statement: string;
  quote: string;
  confidence: number;
  epistemic: string;
  status: FactStatus;
  model: string;
  prompt_template: string;
  note: string;
}

export interface FactRun {
  id: string;
  status: "queued" | "running" | "done" | "failed";
  model: string | null;
  prompt_template: string | null;
  chunks_total: number;
  chunks_done: number;
  facts_found: number;
  facts_dropped: number;
  error: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface Expectation {
  id: string;
  level: string;
  text: string;
  competency: string | null;
  source_fact_id: string | null;
  position: number;
  created_at: string;
  updated_at: string;
}

export interface Evidence {
  fact: Fact;
  document_title: string;
  origin: "user" | "suggestion";
  score: number | null;
  note: string;
}

export interface CareerRow {
  expectation: Expectation;
  evidence: Evidence[];
  suggestion_count: number;
}

export interface CareerLevel {
  level: string;
  total: number;
  covered: number;
  rows: CareerRow[];
}

export interface CareerMatrix {
  levels: CareerLevel[];
  evidence_pool: number;
  disclaimer: string;
}

export interface EvidenceSuggestion {
  fact: Fact;
  document_title: string;
  score: number;
  shared: string[];
}
