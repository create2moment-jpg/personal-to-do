import { useEffect, useRef, useState } from "react";
import { api } from "../api";

const HELP = "#tag  !1–!4 priority  ~45m / ~1h30m estimate  @today @tomorrow @fri @2026-12-01  due:fri  +project   ·   idea: …   note: …";

export function QuickCapture({ onClose, onCaptured }: { onClose: () => void; onCaptured: () => void }) {
  const [text, setText] = useState("");
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => ref.current?.focus(), []);

  const submit = async () => {
    if (!text.trim()) return;
    try {
      const r = await api.capture(text);
      const what = r.task
        ? `Task “${r.task.title}”${r.task.scheduled_date ? ` → ${r.task.scheduled_date}` : " → backlog"}`
        : `${r.kind === "idea" ? "Idea" : "Note"} “${r.note?.title}”`;
      setLog((l) => [what, ...r.warnings.map((w) => `⚠ ${w}`), ...l].slice(0, 6));
      setText("");
      setError(null);
      onCaptured();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal capture" role="dialog" aria-label="Quick capture" onClick={(e) => e.stopPropagation()}>
        <input
          ref={ref}
          value={text}
          placeholder="Capture a task, idea: or note: …  (Enter to save, Esc to close)"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void submit();
            if (e.key === "Escape") onClose();
          }}
        />
        <div className="hint">{HELP}</div>
        {error && <p className="error">{error}</p>}
        <ul className="capture-log">
          {log.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
