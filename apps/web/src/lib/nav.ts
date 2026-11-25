import {
  BarChart3,
  BookOpenText,
  Brain,
  CalendarDays,
  CalendarRange,
  Clock3,
  FileText,
  FolderKanban,
  Inbox,
  Library,
  type LucideIcon,
  NotebookPen,
  Rocket,
  Settings,
  Sparkles,
  SquareKanban,
  Sun,
  Target,
  TrendingUp,
} from "lucide-react";
import type { ViewId } from "./ui-store";

export interface NavItem {
  id: ViewId;
  label: string;
  icon: LucideIcon;
  shortcut?: string; // "g t" style sequence
  phase?: string; // set = not built yet
}

export const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "Plan",
    items: [
      { id: "today", label: "Today", icon: Sun, shortcut: "G T" },
      { id: "board", label: "Task board", icon: SquareKanban, shortcut: "G A" },
      { id: "week", label: "Week", icon: CalendarRange, shortcut: "G W" },
      { id: "sprint", label: "Sprint", icon: Rocket, shortcut: "G R" },
      { id: "upcoming", label: "Upcoming", icon: CalendarDays, shortcut: "G U" },
      { id: "backlog", label: "Backlog", icon: Inbox, shortcut: "G B" },
      { id: "projects", label: "Projects", icon: FolderKanban, shortcut: "G P" },
      { id: "meetings", label: "Meetings & time", icon: Clock3, shortcut: "G M" },
    ],
  },
  {
    label: "Think",
    items: [
      { id: "notes", label: "Notes", icon: NotebookPen, shortcut: "G N" },
      { id: "book", label: "Prompt Book", icon: BookOpenText, shortcut: "G K" },
      { id: "knowledge", label: "Knowledge", icon: Library, shortcut: "G D" },
      { id: "ai", label: "Assistant", icon: Sparkles, phase: "Phase 5" },
    ],
  },
  {
    label: "Grow",
    items: [
      { id: "career", label: "Career", icon: TrendingUp, shortcut: "G C" },
      { id: "goals", label: "Goals", icon: Target, phase: "Phase 7" },
      { id: "skills", label: "Skills", icon: Brain, phase: "Phase 7" },
      { id: "reviews", label: "Reviews", icon: FileText, phase: "Phase 8" },
      { id: "analytics", label: "Insights", icon: BarChart3, phase: "Phase 8" },
    ],
  },
];

export const SETTINGS_ITEM: NavItem = { id: "settings", label: "Settings", icon: Settings, shortcut: "G S" };

export const ALL_NAV: NavItem[] = [...NAV_GROUPS.flatMap((g) => g.items), SETTINGS_ITEM];

/** Second key of the "g <key>" navigation chords. */
export const GOTO_KEYS: Record<string, ViewId> = {
  t: "today",
  a: "board",
  w: "week",
  r: "sprint",
  m: "meetings",
  u: "upcoming",
  b: "backlog",
  p: "projects",
  n: "notes",
  k: "book",
  d: "knowledge",
  c: "career",
  s: "settings",
};

