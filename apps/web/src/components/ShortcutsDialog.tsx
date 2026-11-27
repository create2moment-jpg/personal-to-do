import { Dialog, Keys } from "./primitives";

const SHORTCUTS: [string, string][] = [
  ["Command menu / search", "⌘ K"],
  ["Quick capture", "C"],
  ["Keyboard shortcuts", "?"],
  ["Go to Today", "G T"],
  ["Go to Week", "G W"],
  ["Go to Sprint", "G R"],
  ["Go to Meetings & time", "G M"],
  ["Go to Upcoming", "G U"],
  ["Go to Backlog", "G B"],
  ["Go to Projects", "G P"],
  ["Go to Notes", "G N"],
  ["Go to Prompt Book", "G K"],
  ["Go to Knowledge", "G D"],
  ["Go to Career", "G C"],
  ["Go to Task board", "G A"],
  ["Go to Goals", "G G"],
  ["Go to Skills", "G L"],
  ["Go to Reviews", "G V"],
  ["Prompt Book: previous / next page", "← →"],
  ["Go to Settings", "G S"],
  ["Open focused task", "↵"],
  ["Complete focused task", "X"],
  ["Pick up / drop task (keyboard)", "Space"],
  ["Move picked-up task", "← ↑ → ↓"],
  ["Save capture, keep open", "⌘ ↵"],
  ["Close panel", "Esc"],
  ["New version of note", "⌘ S"],
];

export function ShortcutsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} label="Keyboard shortcuts" width={720}>
      <div style={{ padding: "18px 22px 0" }}>
        <h3 style={{ fontSize: "1.2143rem", fontWeight: 650 }}>Keyboard shortcuts</h3>
        <p className="muted" style={{ margin: "4px 0 0", fontSize: "0.9286rem" }}>
          Everything is reachable without the mouse.
        </p>
      </div>
      <div className="shortcuts-grid">
        {SHORTCUTS.map(([label, combo]) => (
          <div key={label} className="shortcut">
            <span>{label}</span>
            <span>
              <Keys combo={combo} />
            </span>
          </div>
        ))}
      </div>
    </Dialog>
  );
}
