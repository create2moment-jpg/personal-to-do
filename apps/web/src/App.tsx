import { useCallback, useEffect, useState } from "react";
import { CommandPalette } from "./components/CommandPalette";
import { QuickCapture } from "./components/QuickCapture";
import { RightRail } from "./components/RightRail";
import { TaskDrawer } from "./components/TaskDrawer";
import { isTypingTarget } from "./util";
import { BacklogView } from "./views/BacklogView";
import { NotesView } from "./views/NotesView";
import { PlaceholderView } from "./views/PlaceholderView";
import { ProjectsView } from "./views/ProjectsView";
import { TodayView } from "./views/TodayView";
import { NAV, type ViewId } from "./nav";

function viewFromHash(): { view: ViewId; arg?: string } {
  const [view, arg] = window.location.hash.replace(/^#\/?/, "").split("/");
  const found = NAV.find((n) => n.id === view);
  return { view: found ? found.id : "today", arg };
}

export function App() {
  const [{ view, arg }, setRoute] = useState(viewFromHash);
  const [openTaskId, setOpenTaskId] = useState<string | null>(null);
  const [captureOpen, setCaptureOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((r) => r + 1), []);

  const navigate = useCallback((v: ViewId, a?: string) => {
    window.location.hash = a ? `/${v}/${a}` : `/${v}`;
  }, []);

  useEffect(() => {
    const onHash = () => setRoute(viewFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
        return;
      }
      if (e.key === "Escape") {
        setPaletteOpen(false);
        setCaptureOpen(false);
        setOpenTaskId(null);
        return;
      }
      if (isTypingTarget(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "c" || e.key === "q") {
        e.preventDefault();
        setCaptureOpen(true);
      }
      const nav = NAV.find((n) => n.key === e.key);
      if (nav) navigate(nav.id);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate]);

  const current = NAV.find((n) => n.id === view)!;
  let main: JSX.Element;
  switch (view) {
    case "today":
      main = <TodayView revision={revision} onChanged={refresh} onOpenTask={setOpenTaskId} />;
      break;
    case "backlog":
      main = <BacklogView revision={revision} onChanged={refresh} onOpenTask={setOpenTaskId} />;
      break;
    case "notes":
      main = <NotesView revision={revision} noteId={arg} onSelect={(id) => navigate("notes", id)} />;
      break;
    case "projects":
      main = <ProjectsView revision={revision} onChanged={refresh} onOpenTask={setOpenTaskId} />;
      break;
    default:
      main = <PlaceholderView title={current.label} phase={current.phase ?? ""} />;
  }

  return (
    <div className="shell">
      <nav className="nav" aria-label="Primary">
        <div className="brand">Personal OS</div>
        {NAV.map((n) => (
          <a
            key={n.id}
            href={`#/${n.id}`}
            className={`nav-item ${n.id === view ? "active" : ""} ${n.phase ? "later" : ""}`}
            title={n.phase ? `Planned: ${n.phase}` : n.key ? `Shortcut: ${n.key}` : undefined}
          >
            <span>{n.label}</span>
            {n.key && <kbd>{n.key}</kbd>}
          </a>
        ))}
        <div className="nav-foot">
          <button className="ghost" onClick={() => setPaletteOpen(true)}>
            Search <kbd>Ctrl K</kbd>
          </button>
        </div>
      </nav>

      <main className="main">{main}</main>

      <RightRail revision={revision} onCapture={() => setCaptureOpen(true)} onOpenTask={setOpenTaskId} />

      {captureOpen && (
        <QuickCapture
          onClose={() => setCaptureOpen(false)}
          onCaptured={() => {
            refresh();
          }}
        />
      )}
      {paletteOpen && (
        <CommandPalette
          onClose={() => setPaletteOpen(false)}
          onNavigate={(v, a) => {
            navigate(v, a);
            setPaletteOpen(false);
          }}
          onOpenTask={(id) => {
            setOpenTaskId(id);
            setPaletteOpen(false);
          }}
          onCapture={() => {
            setPaletteOpen(false);
            setCaptureOpen(true);
          }}
        />
      )}
      {openTaskId && (
        <TaskDrawer
          taskId={openTaskId}
          onClose={() => setOpenTaskId(null)}
          onChanged={refresh}
          onOpenTask={setOpenTaskId}
        />
      )}
    </div>
  );
}
