/** Whiteboard model and geometry helpers (no React). */

export type ItemKind = "sticky" | "text" | "shape" | "frame" | "connector" | "card";

export interface BoardItem {
  id: string;
  kind: ItemKind;
  x: number;
  y: number;
  w: number;
  h: number;
  z: number;
  text: string;
  color: string | null;
  style: { shape?: "rect" | "ellipse" | "diamond"; size?: "s" | "m" | "l"; end?: "arrow" | "none" } & Record<string, unknown>;
  ref_type: "task" | "note" | null;
  ref_id: string | null;
  from_id: string | null;
  to_id: string | null;
}

export interface BoardMeta {
  id: string;
  title: string;
  emoji: string | null;
  viewport: { x?: number; y?: number; zoom?: number };
  version: number;
  created_at: string;
  updated_at: string;
  item_count: number;
}

export type CardRef = { title: string; status?: string; kind?: string; excerpt?: string; due_date?: string | null; missing?: boolean };

/** Sticky and shape fills; light colours keep text readable in both themes (as on paper). */
export const PALETTE: Record<string, string> = {
  yellow: "#FDF1A5",
  orange: "#FFDDB8",
  red: "#FFC9C9",
  pink: "#FFD1E3",
  purple: "#E2D4FF",
  blue: "#C6E2FF",
  green: "#C9F2C7",
  gray: "#E6E6EA",
  white: "#FFFFFF",
};
export const fill = (c: string | null, fallback = "yellow") => (c && c.startsWith("#") ? c : PALETTE[c ?? fallback] ?? PALETTE[fallback]!);

export const DEFAULT_SIZE: Record<Exclude<ItemKind, "connector">, [number, number]> = {
  sticky: [180, 140],
  text: [220, 44],
  shape: [180, 110],
  frame: [520, 360],
  card: [240, 92],
};

let seq = 0;
export const newId = () => `i${Date.now().toString(36)}${(seq++).toString(36)}${Math.random().toString(36).slice(2, 6)}`;

export const center = (i: BoardItem) => ({ x: i.x + i.w / 2, y: i.y + i.h / 2 });

/** Where the line from the box centre towards (tx, ty) leaves the box. */
export function edgePoint(i: BoardItem, tx: number, ty: number) {
  const c = center(i);
  const dx = tx - c.x;
  const dy = ty - c.y;
  if (dx === 0 && dy === 0) return c;
  const sx = dx === 0 ? Infinity : i.w / 2 / Math.abs(dx);
  const sy = dy === 0 ? Infinity : i.h / 2 / Math.abs(dy);
  const s = Math.min(sx, sy);
  return { x: c.x + dx * s, y: c.y + dy * s };
}

export function bounds(items: BoardItem[]) {
  const boxes = items.filter((i) => i.kind !== "connector");
  if (!boxes.length) return null;
  const x = Math.min(...boxes.map((i) => i.x));
  const y = Math.min(...boxes.map((i) => i.y));
  const r = Math.max(...boxes.map((i) => i.x + i.w));
  const b = Math.max(...boxes.map((i) => i.y + i.h));
  return { x, y, w: r - x, h: b - y };
}

export const inside = (outer: { x: number; y: number; w: number; h: number }, i: BoardItem) => {
  const c = center(i);
  return c.x >= outer.x && c.x <= outer.x + outer.w && c.y >= outer.y && c.y <= outer.y + outer.h;
};

export const snap = (v: number, on: boolean, step = 10) => (on ? Math.round(v / step) * step : v);

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** A standalone SVG of the board (stickies, shapes, frames, cards, arrows, text). */
export function toSvg(items: BoardItem[], refs: Record<string, CardRef>, title: string): string {
  const bb = bounds(items) ?? { x: 0, y: 0, w: 400, h: 300 };
  const pad = 40;
  const byId = new Map(items.map((i) => [i.id, i]));
  const text = (i: BoardItem, s: string, size = 14) =>
    s
      .split("\n")
      .slice(0, 12)
      .map((line, n) => `<text x="${i.x + 12}" y="${i.y + 24 + n * (size + 5)}" font-size="${size}" fill="#1d1d22">${esc(line.slice(0, 60))}</text>`)
      .join("");
  const parts: string[] = [];
  for (const i of [...items].sort((a, b) => (a.kind === "frame" ? -1 : 0) - (b.kind === "frame" ? -1 : 0) || a.z - b.z)) {
    if (i.kind === "frame") parts.push(`<rect x="${i.x}" y="${i.y}" width="${i.w}" height="${i.h}" rx="10" fill="#fafafa" stroke="#c9c9d1"/><text x="${i.x + 10}" y="${i.y - 8}" font-size="14" font-weight="600" fill="#55555c">${esc(i.text)}</text>`);
    else if (i.kind === "sticky") parts.push(`<rect x="${i.x}" y="${i.y}" width="${i.w}" height="${i.h}" rx="4" fill="${fill(i.color)}"/>${text(i, i.text)}`);
    else if (i.kind === "shape") {
      const f = fill(i.color, "white");
      const shape = i.style.shape ?? "rect";
      if (shape === "ellipse") parts.push(`<ellipse cx="${i.x + i.w / 2}" cy="${i.y + i.h / 2}" rx="${i.w / 2}" ry="${i.h / 2}" fill="${f}" stroke="#55555c"/>`);
      else if (shape === "diamond") parts.push(`<polygon points="${i.x + i.w / 2},${i.y} ${i.x + i.w},${i.y + i.h / 2} ${i.x + i.w / 2},${i.y + i.h} ${i.x},${i.y + i.h / 2}" fill="${f}" stroke="#55555c"/>`);
      else parts.push(`<rect x="${i.x}" y="${i.y}" width="${i.w}" height="${i.h}" rx="8" fill="${f}" stroke="#55555c"/>`);
      parts.push(`<text x="${i.x + i.w / 2}" y="${i.y + i.h / 2 + 5}" font-size="14" text-anchor="middle" fill="#1d1d22">${esc(i.text.slice(0, 60))}</text>`);
    } else if (i.kind === "text") parts.push(text(i, i.text, 16));
    else if (i.kind === "card") {
      const r = refs[`${i.ref_type}:${i.ref_id}`];
      parts.push(`<rect x="${i.x}" y="${i.y}" width="${i.w}" height="${i.h}" rx="8" fill="#ffffff" stroke="#c9c9d1"/><text x="${i.x + 12}" y="${i.y + 20}" font-size="11" fill="#8b8b93">${i.ref_type === "task" ? `Task · ${esc(r?.status ?? "")}` : "Note"}</text><text x="${i.x + 12}" y="${i.y + 42}" font-size="14" fill="#1d1d22">${esc((r?.title ?? "").slice(0, 40))}</text>`);
    } else if (i.kind === "connector") {
      const a = i.from_id ? byId.get(i.from_id) : undefined;
      const b = i.to_id ? byId.get(i.to_id) : undefined;
      if (!a || !b) continue;
      const p = edgePoint(a, center(b).x, center(b).y);
      const q = edgePoint(b, center(a).x, center(a).y);
      parts.push(`<line x1="${p.x}" y1="${p.y}" x2="${q.x}" y2="${q.y}" stroke="#55555c" stroke-width="2" ${i.style.end === "none" ? "" : 'marker-end="url(#arrow)"'}/>`);
      if (i.text) parts.push(`<text x="${(p.x + q.x) / 2}" y="${(p.y + q.y) / 2 - 6}" font-size="12" text-anchor="middle" fill="#55555c">${esc(i.text)}</text>`);
    }
  }
  const vb = `${bb.x - pad} ${bb.y - pad - 20} ${bb.w + pad * 2} ${bb.h + pad * 2 + 20}`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb}" width="${bb.w + pad * 2}" height="${bb.h + pad * 2 + 20}" font-family="Inter, system-ui, sans-serif"><title>${esc(title)}</title><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#55555c"/></marker></defs><rect x="${bb.x - pad}" y="${bb.y - pad - 20}" width="100%" height="100%" fill="#ffffff"/>${parts.join("")}</svg>`;
}
