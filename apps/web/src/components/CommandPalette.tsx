import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { NAV, type ViewId } from "../nav";
import type { SearchHit } from "../types";

interface Item {
  id: string;
  label: string;
  hint: string;
  run: () => void;
}

interface Props {
  onClose: () => void;
  onNavigate: (view: ViewId, arg?: string) => void;
  onOpenTask: (id: string) => void;
  onCapture: () => void;
}

export function CommandPalette({ onClose, onNavigate, onOpenTask, onCapture }: Props) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [index, setIndex] = useState(0);
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => ref.current?.focus(), []);

  useEffect(() => {
    if (q.trim().length < 2) {
      setHits([]);
      return;
    }
    const t = setTimeout(() => {
      api.search(q).then(setHits).catch(() => setHits([]));
    }, 120);
    return () => clearTimeout(t);
  }, [q]);

  const items = useMemo<Item[]>(() => {
    const needle = q.toLowerCase();
    const commands: Item[] = [
      { id: "capture", label: "Quick capture…", hint: "c", run: onCapture },
      ...NAV.filter((n) => !n.phase).map((n) => ({
        id: `go-${n.id}`,
        label: `Go to ${n.label}`,
        hint: n.key ?? "",
        run: () => onNavigate(n.id),
      })),
    ].filter((c) => !needle || c.label.toLowerCase().includes(needle));
    const results: Item[] = hits.map((h) => ({
      id: `${h.entity_type}-${h.entity_id}`,
      label: h.title,
      hint: h.entity_type,
      run: () => (h.entity_type === "task" ? onOpenTask(h.entity_id) : onNavigate("notes", h.entity_id)),
    }));
    return [...commands, ...results];
  }, [q, hits, onCapture, onNavigate, onOpenTask]);

  useEffect(() => setIndex(0), [q]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal palette" role="dialog" aria-label="Command palette" onClick={(e) => e.stopPropagation()}>
        <input
          ref={ref}
          value={q}
          placeholder="Search tasks and notes, or type a command…"
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setIndex((i) => Math.min(i + 1, items.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setIndex((i) => Math.max(i - 1, 0));
            } else if (e.key === "Enter") {
              items[index]?.run();
            } else if (e.key === "Escape") {
              onClose();
            }
          }}
        />
        <ul role="listbox">
          {items.map((item, i) => (
            <li
              key={item.id}
              role="option"
              aria-selected={i === index}
              className={i === index ? "selected" : ""}
              onMouseEnter={() => setIndex(i)}
              onClick={item.run}
            >
              <span>{item.label}</span>
              <span className="hint">{item.hint}</span>
            </li>
          ))}
          {items.length === 0 && <li className="empty">No matches</li>}
        </ul>
      </div>
    </div>
  );
}
