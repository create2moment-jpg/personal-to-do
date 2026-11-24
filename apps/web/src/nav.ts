export type ViewId =
  | "today"
  | "week"
  | "sprint"
  | "backlog"
  | "projects"
  | "notes"
  | "goals"
  | "skills"
  | "reviews"
  | "knowledge"
  | "ai"
  | "analytics"
  | "settings";

export const NAV: { id: ViewId; label: string; key?: string; phase?: string }[] = [
  { id: "today", label: "Today", key: "1" },
  { id: "week", label: "Week", phase: "Phase 2" },
  { id: "sprint", label: "Sprint", phase: "Phase 2" },
  { id: "backlog", label: "Backlog", key: "2" },
  { id: "projects", label: "Projects & Areas", key: "3" },
  { id: "notes", label: "Notes", key: "4" },
  { id: "goals", label: "Goals", phase: "Phase 7" },
  { id: "skills", label: "Skills", phase: "Phase 7" },
  { id: "reviews", label: "Reviews", phase: "Phase 8" },
  { id: "knowledge", label: "Knowledge", phase: "Phase 4" },
  { id: "ai", label: "AI", phase: "Phase 5" },
  { id: "analytics", label: "Analytics", phase: "Phase 8" },
  { id: "settings", label: "Settings", phase: "Phase 9" },
];
