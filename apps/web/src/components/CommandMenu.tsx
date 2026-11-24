import { Command } from "cmdk";
import { BookOpenText, FileText, Keyboard, Monitor, Moon, NotebookPen, Phone, Plus, Search, SquareCheck, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { ALL_NAV } from "../lib/nav";
import { DARK_PALETTES, type DarkPalette, loadAppearance, setAppearance } from "../lib/theme";
import type { SearchHit } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { Dialog, Keys, Kbd } from "./primitives";

export function CommandMenu({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} label="Command menu" width={640}>
      {open && <MenuBody onClose={onClose} />}
    </Dialog>
  );
}

function MenuBody({ onClose }: { onClose: () => void }) {
  const ui = useUi();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);

  useEffect(() => {
    if (q.trim().length < 2) {
      setHits([]);
      return;
    }
    const t = setTimeout(() => api.search(q).then(setHits).catch(() => setHits([])), 100);
    return () => clearTimeout(t);
  }, [q]);

  const run = (fn: () => void) => () => {
    onClose();
    // let the dialog close before opening the next surface
    requestAnimationFrame(fn);
  };

  return (
    <Command label="Command menu" shouldFilter loop>
      <div style={{ position: "relative" }}>
        <Search className="cmdk-search-icon" />
        <Command.Input value={q} onValueChange={setQ} placeholder="Search tasks and notes, or type a command…" autoFocus />
      </div>
      <Command.List>
        <Command.Empty>No results for “{q}”.</Command.Empty>

        {hits.length > 0 && (
          <Command.Group heading="Results">
            {hits.map((h) => (
              <Command.Item
                key={`${h.entity_type}-${h.entity_id}`}
                value={`${h.title} ${h.entity_id} ${q}`}
                onSelect={run(() =>
                  h.entity_type === "task" ? ui.openTask(h.entity_id) : h.entity_type === "page" ? ui.navigate("book", h.entity_id) : ui.navigate("notes", h.entity_id),
                )}
              >
                {h.entity_type === "task" ? <SquareCheck /> : h.entity_type === "page" ? <BookOpenText /> : <FileText />}
                <span>{h.title}</span>
                {h.entity_type === "note" && h.snippet.trim() && <span className="cmd-snippet">{h.snippet.replace(/[[\]]/g, "")}</span>}
                <span className="cmd-hint">{h.entity_type}</span>
              </Command.Item>
            ))}
          </Command.Group>
        )}

        <Command.Group heading="Actions">
          <Command.Item value="new task capture" onSelect={run(() => ui.openCapture())}>
            <Plus /> New task or capture <span className="cmd-hint"><Kbd>C</Kbd></span>
          </Command.Item>
          <Command.Item value="log a call meeting" onSelect={run(() => ui.openLogCall())}>
            <Phone /> Log a call
          </Command.Item>
          <Command.Item value="new idea inbox" onSelect={run(() => ui.openCapture("idea: "))}>
            <NotebookPen /> New idea
          </Command.Item>
          <Command.Item value="keyboard shortcuts help" onSelect={run(ui.openShortcuts)}>
            <Keyboard /> Keyboard shortcuts <span className="cmd-hint"><Kbd>?</Kbd></span>
          </Command.Item>
        </Command.Group>

        <Command.Group heading="Go to">
          {ALL_NAV.map((n) => (
            <Command.Item key={n.id} value={`go to ${n.label}`} onSelect={run(() => ui.navigate(n.id))}>
              <n.icon /> {n.label}
              <span className="cmd-hint">{n.phase ? n.phase : n.shortcut ? <Keys combo={n.shortcut} /> : null}</span>
            </Command.Item>
          ))}
        </Command.Group>

        <Command.Group heading="Appearance">
          {(
            [
              ["light", "Light theme", Sun],
              ["dark", "Dark theme", Moon],
              ["system", "System theme", Monitor],
            ] as const
          ).map(([mode, label, Icon]) => (
            <Command.Item key={mode} value={`theme ${label}`} onSelect={run(() => setAppearance({ ...loadAppearance(), theme: mode }))}>
              <Icon /> {label}
            </Command.Item>
          ))}
          {(Object.keys(DARK_PALETTES) as DarkPalette[]).map((d) => (
            <Command.Item key={d} value={`theme dark palette ${DARK_PALETTES[d].label}`} onSelect={run(() => setAppearance({ ...loadAppearance(), theme: "dark", dark: d }))}>
              <Moon /> Dark · {DARK_PALETTES[d].label}
              <span className="cmd-hint">{DARK_PALETTES[d].hint}</span>
            </Command.Item>
          ))}
        </Command.Group>
      </Command.List>
      <div className="cmdk-footer">
        <span><Kbd>↑</Kbd><Kbd>↓</Kbd> navigate</span>
        <span><Kbd>↵</Kbd> open</span>
        <span><Kbd>esc</Kbd> close</span>
      </div>
    </Command>
  );
}
