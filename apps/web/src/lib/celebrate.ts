import { loadAppearance } from "./theme";

export type Celebration = "top3" | "sprint" | "week" | "day" | "goal";

const KEY = "ppos.celebrated";

/** Once per event type per day; never blocks input; respects reduced motion. */
export function celebrate(kind: Celebration): boolean {
  const mode = loadAppearance().celebrations;
  if (mode === "off") return false;
  const today = new Date().toDateString();
  try {
    const seen = JSON.parse(localStorage.getItem(KEY) ?? "{}") as Record<string, string>;
    if (seen[kind] === today) return false; // already celebrated this today
    seen[kind] = today;
    localStorage.setItem(KEY, JSON.stringify(seen));
  } catch {
    /* storage unavailable: still celebrate once for this view */
  }
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (mode === "on" && !reduced) confetti();
  return true;
}

function confetti() {
  const canvas = document.createElement("canvas");
  canvas.setAttribute("aria-hidden", "true");
  Object.assign(canvas.style, { position: "fixed", inset: "0", pointerEvents: "none", zIndex: "80" });
  canvas.width = innerWidth * devicePixelRatio;
  canvas.height = innerHeight * devicePixelRatio;
  canvas.style.width = `${innerWidth}px`;
  canvas.style.height = `${innerHeight}px`;
  document.body.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas.remove();
  ctx.scale(devicePixelRatio, devicePixelRatio);
  const accent = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#5b5bd6";
  const colors = [accent, "#f2c94c", "#4cc38a", "#f2645f", "#5c9dff"];
  const originX = innerWidth / 2;
  const originY = innerHeight * 0.35;
  const parts = Array.from({ length: 70 }, () => {
    const angle = Math.random() * Math.PI * 2;
    const speed = 4 + Math.random() * 7;
    return {
      x: originX, y: originY, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed - 4,
      size: 4 + Math.random() * 5, rot: Math.random() * Math.PI, vr: (Math.random() - 0.5) * 0.4,
      color: colors[Math.floor(Math.random() * colors.length)]!,
    };
  });
  const start = performance.now();
  const duration = 800;
  const frame = (t: number) => {
    const p = (t - start) / duration;
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    for (const c of parts) {
      c.vy += 0.35;
      c.vx *= 0.98;
      c.x += c.vx;
      c.y += c.vy;
      c.rot += c.vr;
      ctx.save();
      ctx.globalAlpha = Math.max(0, 1 - p * p);
      ctx.translate(c.x, c.y);
      ctx.rotate(c.rot);
      ctx.fillStyle = c.color;
      ctx.fillRect(-c.size / 2, -c.size / 4, c.size, c.size / 2);
      ctx.restore();
    }
    if (p < 1) requestAnimationFrame(frame);
    else canvas.remove();
  };
  requestAnimationFrame(frame);
}
