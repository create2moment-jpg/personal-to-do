import { AnimatePresence, motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { type ReactNode, useEffect } from "react";
import { createPortal } from "react-dom";
import type { TaskStatus } from "../lib/types";

export const spring = { type: "spring", stiffness: 520, damping: 38, mass: 0.7 } as const;

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="kbd">{children}</kbd>;
}

export function Keys({ combo }: { combo: string }) {
  return (
    <>
      {combo.split(" ").map((k, i) => (
        <Kbd key={i}>{k}</Kbd>
      ))}
    </>
  );
}

export function StatusDot({ status }: { status: TaskStatus }) {
  return <span className={`status-dot ${status}`} aria-hidden />;
}

/** Centered modal with backdrop. Closes on Escape and backdrop click. */
export function Dialog({
  open,
  onClose,
  children,
  label,
  width,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  label: string;
  width?: number;
}) {
  useEscape(open, onClose);
  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          <motion.div className="overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }} onClick={onClose} />
          <div className="dialog-wrap" onClick={onClose}>
            <motion.div
              className="dialog"
              role="dialog"
              aria-modal
              aria-label={label}
              style={width ? { width: `min(${width}px, calc(100vw - 24px))` } : undefined}
              initial={{ opacity: 0, scale: 0.97, y: -8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.98, y: -4 }}
              transition={{ duration: 0.16, ease: [0.2, 0.8, 0.2, 1] }}
              onClick={(e) => e.stopPropagation()}
            >
              {children}
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>,
    document.body,
  );
}

/** Right-hand slide-over panel. */
export function Sheet({ open, onClose, children, label }: { open: boolean; onClose: () => void; children: ReactNode; label: string }) {
  useEscape(open, onClose);
  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          <motion.div className="overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }} onClick={onClose} />
          <motion.aside
            className="sheet"
            role="dialog"
            aria-modal
            aria-label={label}
            initial={{ x: 40, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 40, opacity: 0 }}
            transition={spring}
          >
            {children}
          </motion.aside>
        </>
      )}
    </AnimatePresence>,
    document.body,
  );
}

function useEscape(active: boolean, onClose: () => void) {
  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [active, onClose]);
}

export function EmptyState({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon />
      </div>
      <h4>{title}</h4>
      {children && <p>{children}</p>}
    </div>
  );
}

export function ProgressRing({ value, size = 64, stroke = 6, label }: { value: number; size?: number; stroke?: number; label?: string }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(1, value));
  return (
    <div className="ring" style={{ width: size, height: size }} role="img" aria-label={label ?? `${Math.round(v * 100)}%`}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--bg-sunken)" strokeWidth={stroke} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="url(#ring-grad)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - v) }}
          transition={{ duration: 0.8, ease: [0.2, 0.8, 0.2, 1] }}
        />
        <defs>
          <linearGradient id="ring-grad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--accent)" />
            <stop offset="100%" stopColor="var(--green)" />
          </linearGradient>
        </defs>
      </svg>
      <div className="ring-label">{Math.round(v * 100)}%</div>
    </div>
  );
}
