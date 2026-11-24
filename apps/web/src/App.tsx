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
import { UiContext, type UiActions, type ViewId } from "./lib/ui-store";
import { cx, isTypingTarget } from "./lib/util";
import { ComingSoonView } from "./views/ComingSoonView";
import { BacklogView, UpcomingView } from "./views/ListViews";
import { MeetingsView } from "./views/MeetingsView";
import { PromptBookView } from "./views/PromptBookView";
import { SprintView } from "./views/SprintView";
import { WeekView } from "./views/WeekView";
import { LogCallDialog, type CallDraft } from "./components/meetings";
import { useSettings } from "./lib/queries";
import { setWorkspaceTimeZone } from "./lib/util";
import { ProjectsView } from "./views/ProjectsView";
import { SettingsView } from "./views/SettingsView";
import { TodayView } from "./views/TodayView";

// The rich-text editor is heavy; load it only when Notes is opened.
const NotesView = lazy(() => import("./views/NotesView").then((m) => ({ default: m.NotesView })));

function routeFromHash(): { view: ViewId; arg?: string } {
  const [view, arg] = window.location.hash.replace(/^#\/?/, "").split("/");
  const found = ALL_NAV.find((n) => n.id === view);
  return { view: found ? found.id : "today", arg: arg || undefined };
}

export function App() {
  const [{ view, arg }, setRoute] = useState(routeFromHash);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [capture, setCapture] = useState<{ open: boolean; initial?: string }>({ open: false });
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [callDraft, setCallDraft] = useState<CallDraft | null>(null);
  const { data: settings } = useSettings();
  if (settings) setWorkspaceTimeZone(settings.timezone);
  const gPressed = useRef(0);

  const navigate = useCallback((v: ViewId, a?: string) => {
    window.location.hash = a ? `/${v}/${a}` : `/${v}`;
  }, []);

  const ui = useMemo<UiActions>(
    () => ({
      navigate,
      openTask: setTaskId,
      openCapture: (initial) => setCapture({ open: true, initial }),
      openPalette: () => setPaletteOpen(true),
      openShortcuts: () => setShortcutsOpen(true),
      openLogCall: (draft) => setCallDraft(draft ?? {}),
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
      const overlayOpen = capture.open || paletteOpen || shortcutsOpen || taskId !== null || callDraft !== null;
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
  }, [navigate, capture.open, paletteOpen, shortcutsOpen, taskId, callDraft]);

  const current = ALL_NAV.find((n) => n.id === view)!;
  let page: JSX.Element;
  if (current.phase) page = <ComingSoonView view={view} />;
  else if (view === "today") page = <TodayView />;
  else if (view === "upcoming") page = <UpcomingView />;
  else if (view === "week") page = <WeekView initialTab={arg === "review" ? "review" : "plan"} />;
  else if (view === "sprint") page = <SprintView />;
  else if (view === "meetings") page = <MeetingsView />;
  else if (view === "book") page = <PromptBookView pageId={arg} />;
  else if (view === "backlog") page = <BacklogView />;
  else if (view === "projects") page = <ProjectsView />;
  else if (view === "notes") page = <NotesView noteId={arg} />;
  else page = <SettingsView />;

  const showRail = !["notes", "settings", "week", "book"].includes(view);

  return (
    <UiContext.Provider value={ui}>
      <div className={cx("shell", !showRail && "no-rail")}>
        <Sidebar view={view} />
        <main className="main" id="main">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={view} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.14 }} style={{ height: "100%" }}>
              <Suspense fallback={<div className="page faint">Loading…</div>}>{page}</Suspense>
            </motion.div>
          </AnimatePresence>
        </main>
        {showRail && <RightRail />}
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
      <TaskSheet taskId={taskId} onClose={() => setTaskId(null)} onOpenTask={setTaskId} />
    </UiContext.Provider>
  );
}
