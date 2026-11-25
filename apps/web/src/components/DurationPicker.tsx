import { Clock } from "lucide-react";
import { type KeyboardEvent, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../lib/api";
import { invalidateTasks, useSettings } from "../lib/queries";
import type { Task } from "../lib/types";
import { cx, formatMinutes, parseDuration } from "../lib/util";

const PRESETS = [15, 30, 45, 60, 90, 120, 180, 240];
const stop = { onPointerDown: (e: React.PointerEvent) => e.stopPropagation(), onClick: (e: React.MouseEvent) => e.stopPropagation() };

/** Estimate chip on a task card; click to pick any duration. */
export function DurationChip({ task }: { task: Task }) {
  const { data: settings } = useSettings();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLButtonElement>(null);
  const est = task.estimate_minutes;
  const fallback = settings?.default_task_minutes ?? 30;

  const set = async (minutes: number | null) => {
    setOpen(false);
    await api.updateTask(task.id, { estimate_minutes: minutes });
    invalidateTasks();
  };

  return (
    <>
      <button
        ref={ref}
        type="button"
        className={cx("duration-chip", est === null && "unset")}
        aria-label={est === null ? `Set time for ${task.title}` : `Time for ${task.title}: ${formatMinutes(est)} — change`}
        title={est === null ? `No estimate — counts as ${formatMinutes(fallback)} in capacity. Click to set.` : "Estimate — click to change"}
        aria-expanded={open}
        {...stop}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        onKeyDown={(e) => e.stopPropagation()}
      >
        <Clock />
        {est === null ? "+ time" : (
          <>
            {task.actual_minutes > 0 ? `${formatMinutes(task.actual_minutes)} / ` : ""}
            {formatMinutes(est)}
          </>
        )}
      </button>
      {open && <DurationPopover anchor={ref.current} value={est} onPick={(m) => void set(m)} onClose={() => setOpen(false)} />}
    </>
  );
}

function DurationPopover({ anchor, value, onPick, onClose }: { anchor: HTMLElement | null; value: number | null; onPick: (m: number | null) => void; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const [custom, setCustom] = useState(value !== null && !PRESETS.includes(value) ? formatMinutes(value) : "");
  const parsed = parseDuration(custom);

  useLayoutEffect(() => {
    if (!anchor) return;
    const r = anchor.getBoundingClientRect();
    const width = 236;
    setPos({ top: r.bottom + 6, left: Math.max(8, Math.min(r.left, window.innerWidth - width - 8)) });
  }, [anchor]);
  useEffect(() => {
    const away = (e: PointerEvent) => !ref.current?.contains(e.target as Node) && !anchor?.contains(e.target as Node) && onClose();
    const esc = (e: globalThis.KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [anchor, onClose]);

  return createPortal(
    <div ref={ref} className="duration-pop" role="dialog" aria-label="Choose a duration" style={pos} {...stop} onKeyDown={(e) => e.stopPropagation()}>
      <div className="duration-presets">
        {PRESETS.map((m) => (
          <button key={m} type="button" className="filter-chip" aria-pressed={value === m} onClick={() => onPick(m)}>
            {formatMinutes(m)}
          </button>
        ))}
      </div>
      <form
        className="duration-custom"
        onSubmit={(e) => {
          e.preventDefault();
          if (parsed) onPick(parsed);
        }}
      >
        <input className="input" autoFocus placeholder="Custom: 50, 1h20, 1.5h" value={custom} onChange={(e) => setCustom(e.target.value)} aria-label="Custom duration" />
        <button className="btn sm primary" type="submit" disabled={!parsed}>
          {parsed ? formatMinutes(parsed) : "Set"}
        </button>
      </form>
      {value !== null && (
        <button type="button" className="link-btn duration-clear" onClick={() => onPick(null)}>
          Clear estimate
        </button>
      )}
    </div>,
    document.body,
  );
}

/** Free-text minutes field ("50", "1h20", "1.5h") that saves on blur / Enter. */
export function DurationInput({ value, onSave, placeholder = "e.g. 50, 1h20", label }: { value: number | null; onSave: (m: number | null) => void; placeholder?: string; label: string }) {
  const [text, setText] = useState(value === null ? "" : formatMinutes(value));
  const [bad, setBad] = useState(false);
  useEffect(() => setText(value === null ? "" : formatMinutes(value)), [value]);
  const commit = () => {
    if (!text.trim()) {
      setBad(false);
      if (value !== null) onSave(null);
      return;
    }
    const m = parseDuration(text);
    setBad(m === null);
    if (m !== null && m !== value) onSave(m);
    if (m !== null) setText(formatMinutes(m));
  };
  return (
    <input
      className={cx("input", bad && "invalid")}
      value={text}
      placeholder={placeholder}
      aria-label={label}
      aria-invalid={bad}
      title={bad ? "Use minutes or hours, e.g. 50, 1h20, 1.5h" : undefined}
      onChange={(e) => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
    />
  );
}
