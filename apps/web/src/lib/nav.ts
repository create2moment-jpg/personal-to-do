import {
  BarChart3,
  Brain,
  CalendarDays,
  CalendarRange,
  FileText,
  FolderKanban,
  Inbox,
  Library,
  type LucideIcon,
  NotebookPen,
  Rocket,
  Settings,
  Sparkles,
  Sun,
  Target,
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
      { id: "upcoming", label: "Upcoming", icon: CalendarDays, shortcut: "G U" },
      { id: "backlog", label: "Backlog", icon: Inbox, shortcut: "G B" },
      { id: "projects", label: "Projects", icon: FolderKanban, shortcut: "G P" },
      { id: "week", label: "Week", icon: CalendarRange, phase: "Phase 2" },
      { id: "sprint", label: "Sprint", icon: Rocket, phase: "Phase 2" },
    ],
  },
  {
    label: "Think",
    items: [
      { id: "notes", label: "Notes", icon: NotebookPen, shortcut: "G N" },
      { id: "knowledge", label: "Knowledge", icon: Library, phase: "Phase 4" },
      { id: "ai", label: "Assistant", icon: Sparkles, phase: "Phase 5" },
    ],
  },
  {
    label: "Grow",
    items: [
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
  u: "upcoming",
  b: "backlog",
  p: "projects",
  n: "notes",
  s: "settings",
};

