import { SmilePlus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cx } from "../lib/util";

const CHOICES = ["🎯", "🚀", "📝", "🔎", "🧪", "🛠️", "📊", "🧠", "🤝", "📚", "⚡", "🌱", "🏁", "💡", "🔒", "🎓", "🧭", "🗂️", "🐛", "✨", "📈", "🗓️", "💬", "🏆"];

/**
 * Optional emoji: a small button that opens a grid of common choices, a field for
 * any other emoji, and "None". Calls onChange with null to clear.
 */
export function EmojiPicker({ value, onChange, label = "Emoji" }: { value: string | null | undefined; onChange: (emoji: string | null) => void; label?: string }) {
  const [open, setOpen] = useState(false);
  const [custom, setCustom] = useState("");
  const root = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !root.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  const pick = (e: string | null) => {
    onChange(e);
    setOpen(false);
    setCustom("");
  };
  return (
    <span className="emoji-picker" ref={root}>
      <button type="button" className={cx("emoji-btn", !value && "empty")} aria-label={value ? `${label}: ${value} — change` : `Add ${label.toLowerCase()}`} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {value || <SmilePlus size={15} />}
      </button>
      {open && (
        <div className="emoji-pop" role="dialog" aria-label={label} onKeyDown={(e) => e.key === "Escape" && setOpen(false)}>
          <div className="emoji-grid">
            {CHOICES.map((e) => (
              <button type="button" key={e} className={cx(value === e && "on")} aria-label={e} onClick={() => pick(e)}>
                {e}
              </button>
            ))}
          </div>
          <div className="emoji-foot">
            <input
              className="input"
              value={custom}
              placeholder="any emoji"
              aria-label="Type or paste any emoji"
              maxLength={8}
              onChange={(e) => setCustom(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  if (custom.trim()) pick(custom.trim());
                }
              }}
            />
            <button type="button" className="btn sm ghost" onClick={() => pick(null)}>
              None
            </button>
          </div>
        </div>
      )}
    </span>
  );
}
