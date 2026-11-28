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
  Workflow,
  LayoutDashboard,
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
      { id: "ai", label: "Assistant", icon: Sparkles, shortcut: "G J" },
      { id: "boards", label: "Boards", icon: LayoutDashboard, shortcut: "G O" },
      { id: "workflows", label: "Workflows", icon: Workflow, shortcut: "G F" },
    ],
  },
  {
    label: "Grow",
    items: [
      { id: "career", label: "Career", icon: TrendingUp, shortcut: "G C" },
      { id: "goals", label: "Goals", icon: Target, shortcut: "G G" },
      { id: "skills", label: "Skills", icon: Brain, shortcut: "G L" },
      { id: "reviews", label: "Reviews", icon: FileText, shortcut: "G V" },
      { id: "analytics", label: "Insights", icon: BarChart3, shortcut: "G I" },
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
  g: "goals",
  l: "skills",
  v: "reviews",
  i: "analytics",
  j: "ai",
  f: "workflows",
  o: "boards",
  s: "settings",
};

