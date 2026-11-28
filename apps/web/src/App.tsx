import { AnimatePresence, motion } from "framer-motion";
import { NotebookPen, Plus, Search, Sun, Inbox } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CommandMenu } from "./components/CommandMenu";
import { QuickCapture } from "./components/QuickCapture";
import { RightRail } from "./components/RightRail";
import { ShortcutsDialog } from "./components/ShortcutsDialog";
import { Sidebar } from "./components/Sidebar";
import { TaskSheet } from "./components/TaskSheet";
import { ALL_NAV, GOTO_KEYS } from "./lib/nav";
import { type ScheduleOptions, UiContext, type UiActions, type ViewId } from "./lib/ui-store";
import { cx, isTypingTarget } from "./lib/util";
import { ComingSoonView } from "./views/ComingSoonView";
import { BacklogView, UpcomingView } from "./views/ListViews";
import { MeetingsView } from "./views/MeetingsView";
import { PromptBookView } from "./views/PromptBookView";
import { AssistantView } from "./views/AssistantView";
import { BoardView } from "./views/BoardView";
import { CareerView } from "./views/CareerView";
import { GoalsView } from "./views/GoalsView";
import { InsightsView } from "./views/InsightsView";
import { WorkflowsView } from "./views/WorkflowsView";
import { BoardsView } from "./views/BoardsView";
import { PeopleView } from "./views/PeopleView";
import { useGadgetPrefs } from "./lib/gadgets";
import { ReminderRunner } from "./components/Reminders";
import { ReviewsView } from "./views/ReviewsView";
import { SkillsView } from "./views/SkillsView";
import { KnowledgeView } from "./views/KnowledgeView";
import { SprintView } from "./views/SprintView";
import { WeekView } from "./views/WeekView";
import { LogCallDialog, type CallDraft } from "./components/meetings";
import { ScheduleMeetingDialog } from "./components/ScheduleMeeting";
import { useSettings } from "./lib/queries";
import { setWorkspaceTimeZone } from "./lib/util";
import { ProjectsView } from "./views/ProjectsView";
import { SettingsView } from "./views/SettingsView";
import { TodayView } from "./views/TodayView";

// The rich-text editor is heavy; load it only when Notes is opened.
const NotesView = lazy(() => import("./views/NotesView").then((m) => ({ default: m.NotesView })));

function routeFromHash(): { view: ViewId; arg?: string } {
  const [view, raw] = window.location.hash.replace(/^#\/?/, "").split("/");
  const found = ALL_NAV.find((n) => n.id === view);
  let arg = raw || undefined;
  try {
    arg = raw ? decodeURIComponent(raw) : undefined; // e.g. a question from the Assistant gadget
  } catch {
    /* malformed escape: use it as is */
  }
  return { view: found ? found.id : "today", arg };
}

export function App() {
  const [{ view, arg }, setRoute] = useState(routeFromHash);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [capture, setCapture] = useState<{ open: boolean; initial?: string }>({ open: false });
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [callDraft, setCallDraft] = useState<CallDraft | null>(null);
  const [schedule, setSchedule] = useState<ScheduleOptions | null>(null);
  const { data: settings } = useSettings();
  if (settings) setWorkspaceTimeZone(settings.timezone);
  const gPressed = useRef(0);

  const navigate = useCallback((v: ViewId, a?: string) => {
    window.location.hash = a ? `/${v}/${encodeURIComponent(a)}` : `/${v}`;
  }, []);

  const ui = useMemo<UiActions>(
    () => ({
      navigate,
      openTask: setTaskId,
      openCapture: (initial) => setCapture({ open: true, initial }),
      openPalette: () => setPaletteOpen(true),
      openShortcuts: () => setShortcutsOpen(true),
      openLogCall: (draft) => setCallDraft(draft ?? {}),
      openScheduleMeeting: (opts) => setSchedule(opts ?? {}),
    }),
    [navigate],
  );

  useEffect(() => {
    const onHash = () => setRoute(routeFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
        return;
      }
      const overlayOpen = capture.open || paletteOpen || shortcutsOpen || taskId !== null || callDraft !== null || schedule !== null;
      if (overlayOpen || isTypingTarget(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
      if (Date.now() - gPressed.current < 900) {
        const target = GOTO_KEYS[e.key.toLowerCase()];
        gPressed.current = 0;
        if (target) {
          e.preventDefault();
          navigate(target);
          return;
        }
      }
      if (e.key === "g" || e.key === "G") {
        gPressed.current = Date.now();
      } else if (e.key === "c" || e.key === "C") {
        e.preventDefault();
        setCapture({ open: true });
      } else if (e.key === "?") {
        e.preventDefault();
        setShortcutsOpen(true);
      } else if (e.key === "/") {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate, capture.open, paletteOpen, shortcutsOpen, taskId, callDraft, schedule]);

  const gadgets = useGadgetPrefs();
  const current = ALL_NAV.find((n) => n.id === view)!;
  let page: JSX.Element;
  if (current.phase) page = <ComingSoonView view={view} />;
  else if (view === "today") page = <TodayView initialDay={arg} />;
  else if (view === "board") page = <BoardView />;
  else if (view === "upcoming") page = <UpcomingView />;
  else if (view === "week") page = <WeekView initialTab={arg === "review" ? "review" : "plan"} />;
  else if (view === "sprint") page = <SprintView />;
  else if (view === "meetings") page = <MeetingsView />;
  else if (view === "book") page = <PromptBookView pageId={arg} />;
  else if (view === "knowledge") page = <KnowledgeView arg={arg} />;
  else if (view === "career") page = <CareerView />;
  else if (view === "goals") page = <GoalsView />;
  else if (view === "skills") page = <SkillsView />;
  else if (view === "reviews") page = <ReviewsView reviewId={arg} />;
  else if (view === "analytics") page = <InsightsView />;
  else if (view === "ai") page = <AssistantView initialQuestion={arg} />;
  else if (view === "workflows") page = <WorkflowsView />;
  else if (view === "boards") page = <BoardsView boardId={arg} />;
  else if (view === "people") page = <PeopleView personId={arg} />;
  else if (view === "backlog") page = <BacklogView />;
  else if (view === "projects") page = <ProjectsView />;
  else if (view === "notes") page = <NotesView noteId={arg} />;
  else page = <SettingsView section={arg} />;

  const slimRail = gadgets.isCollapsed(view);

  return (
    <UiContext.Provider value={ui}>
      <div className={cx("shell", slimRail && "slim-rail")}>
        <Sidebar view={view} />
        <main className="main" id="main">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={view} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.14 }} style={{ height: "100%" }}>
              <Suspense fallback={<div className="page faint">Loading…</div>}>{page}</Suspense>
            </motion.div>
          </AnimatePresence>
        </main>
        <RightRail view={view} />
        <ReminderRunner />
      </div>

      <nav className="mobile-bar" aria-label="Mobile navigation">
        {(
          [
            ["today", Sun],
            ["backlog", Inbox],
            ["notes", NotebookPen],
          ] as const
        ).map(([v, Icon]) => (
          <button key={v} className={cx(view === v && "active")} onClick={() => navigate(v)} aria-label={v}>
            <Icon />
          </button>
        ))}
        <button onClick={() => setPaletteOpen(true)} aria-label="Search">
          <Search />
        </button>
        <button onClick={() => setCapture({ open: true })} aria-label="Capture" style={{ background: "var(--accent)", color: "#fff" }}>
          <Plus />
        </button>
      </nav>

      <QuickCapture open={capture.open} initial={capture.initial} onClose={() => setCapture({ open: false })} />
      <CommandMenu open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <ShortcutsDialog open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
      <LogCallDialog open={callDraft !== null} draft={callDraft ?? undefined} onClose={() => setCallDraft(null)} />
      <ScheduleMeetingDialog open={schedule !== null} options={schedule ?? {}} onClose={() => setSchedule(null)} />
      <TaskSheet taskId={taskId} onClose={() => setTaskId(null)} onOpenTask={setTaskId} />
    </UiContext.Provider>
  );
}
