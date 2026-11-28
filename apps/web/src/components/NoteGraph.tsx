import { useQuery } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { cx } from "../lib/util";

interface GNode {
  id: string;
  title: string;
  kind: string;
  ghost: boolean;
  degree: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  fixed?: boolean;
}

/**
 * Obsidian-style graph of [[linked]] notes: a small force layout in SVG.
 * Drag a node to pin it, scroll to zoom, drag the background to pan, click to open.
 */
export function NoteGraph({ focusId, onOpen, height = 560, compact = false }: { focusId?: string; onOpen: (id: string, ghostTitle?: string) => void; height?: number; compact?: boolean }) {
  const { data, isLoading } = useQuery({ queryKey: ["note-graph", focusId ?? "all"], queryFn: () => api.noteGraph(focusId, focusId ? 2 : 1) });
  const [showGhosts, setShowGhosts] = useState(true);
  const [showOrphans, setShowOrphans] = useState(!compact);
  const [q, setQ] = useState("");
  const [hover, setHover] = useState<string | null>(null);
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const [, tick] = useState(0);
  const nodes = useRef<GNode[]>([]);
  const svg = useRef<SVGSVGElement>(null);
  const drag = useRef<{ node?: GNode; panFrom?: { x: number; y: number; vx: number; vy: number }; moved?: boolean } | null>(null);

  const graph = useMemo(() => {
    if (!data) return { nodes: [] as GNode[], edges: [] as { source: string; target: string }[] };
    const keep = data.nodes.filter((n) => (showGhosts || !n.ghost) && (showOrphans || n.degree > 0 || n.id === focusId));
    const ids = new Set(keep.map((n) => n.id));
    const prev = new Map(nodes.current.map((n) => [n.id, n]));
    const out = keep.map((n, i) => {
      const p = prev.get(n.id);
      const a = (i / Math.max(1, keep.length)) * Math.PI * 2;
      const r = 80 + 140 * Math.random();
      return { ...n, x: p?.x ?? Math.cos(a) * r, y: p?.y ?? Math.sin(a) * r, vx: 0, vy: 0, fixed: p?.fixed };
    });
    return { nodes: out, edges: data.edges.filter((e) => ids.has(e.source) && ids.has(e.target)) };
  }, [data, showGhosts, showOrphans, focusId]);

  useEffect(() => {
    nodes.current = graph.nodes;
    const byId = new Map(graph.nodes.map((n) => [n.id, n]));
    let frame = 0;
    let alpha = 1;
    const step = () => {
      const ns = nodes.current;
      for (let i = 0; i < ns.length; i++) {
        const a = ns[i]!;
        for (let j = i + 1; j < ns.length; j++) {
          const b = ns[j]!;
          let dx = a.x - b.x;
          let dy = a.y - b.y;
          let d2 = dx * dx + dy * dy;
          if (d2 < 0.01) {
            dx = Math.random() - 0.5;
            dy = Math.random() - 0.5;
            d2 = 1;
          }
          const f = (2600 / d2) * alpha;
          const d = Math.sqrt(d2);
          a.vx += (dx / d) * f;
          a.vy += (dy / d) * f;
          b.vx -= (dx / d) * f;
          b.vy -= (dy / d) * f;
        }
      }
      for (const e of graph.edges) {
        const a = byId.get(e.source);
        const b = byId.get(e.target);
        if (!a || !b) continue;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const f = (d - 120) * 0.02 * alpha;
        a.vx += (dx / d) * f;
        a.vy += (dy / d) * f;
        b.vx -= (dx / d) * f;
        b.vy -= (dy / d) * f;
      }
      for (const n of ns) {
        n.vx -= n.x * 0.002 * alpha;
        n.vy -= n.y * 0.002 * alpha;
        if (n.fixed) {
          n.vx = n.vy = 0;
          continue;
        }
        n.x += Math.max(-12, Math.min(12, n.vx));
        n.y += Math.max(-12, Math.min(12, n.vy));
        n.vx *= 0.6;
        n.vy *= 0.6;
      }
      alpha = Math.max(0.02, alpha * 0.985);
      tick((t) => t + 1);
      if (alpha > 0.03 || drag.current?.node) frame = requestAnimationFrame(step);
      else if (!touched.current) fit(); // settled: show the whole graph once
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [graph]);

  const touched = useRef(false); // the user zoomed or panned: stop auto-fitting
  function fit() {
    const ns = nodes.current;
    const el = svg.current;
    if (!ns.length || !el) return;
    const xs = ns.map((n) => n.x);
    const ys = ns.map((n) => n.y);
    const w = Math.max(...xs) - Math.min(...xs) + 160;
    const h = Math.max(...ys) - Math.min(...ys) + 80;
    const k = Math.max(0.3, Math.min(2, Math.min(el.clientWidth / w, height / h)));
    const cx = (Math.max(...xs) + Math.min(...xs)) / 2;
    const cy = (Math.max(...ys) + Math.min(...ys)) / 2;
    setView({ x: -cx * k, y: -cy * k, k });
  }

  const neighbours = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const e of graph.edges) {
      if (!m.has(e.source)) m.set(e.source, new Set());
      if (!m.has(e.target)) m.set(e.target, new Set());
      m.get(e.source)!.add(e.target);
      m.get(e.target)!.add(e.source);
    }
    return m;
  }, [graph]);

  const toWorld = (cx: number, cy: number) => {
    const r = svg.current!.getBoundingClientRect();
    return { x: (cx - r.left - r.width / 2 - view.x) / view.k, y: (cy - r.top - r.height / 2 - view.y) / view.k };
  };
  const match = q.trim().toLowerCase();
  const byId = new Map(nodes.current.map((n) => [n.id, n]));
  const lit = hover ? new Set([hover, ...(neighbours.get(hover) ?? [])]) : null;

  return (
    <div className={cx("graph", compact && "compact")}>
      {!compact && (
        <div className="graph-tools">
          <div className="search-input" style={{ maxWidth: 260 }}>
            <Search />
            <input className="input" placeholder="Find a note" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Find in graph" />
          </div>
          <label className="graph-opt">
            <input type="checkbox" checked={showGhosts} onChange={(e) => setShowGhosts(e.target.checked)} /> Notes not created yet
          </label>
          <label className="graph-opt">
            <input type="checkbox" checked={showOrphans} onChange={(e) => setShowOrphans(e.target.checked)} /> Unlinked notes
          </label>
          <span className="faint" style={{ marginLeft: "auto", fontSize: "0.8rem" }}>
            {graph.nodes.length} notes · {graph.edges.length} links · scroll to zoom, drag to pan
          </span>
        </div>
      )}
      {isLoading && (
        <div className="faint" style={{ padding: 20 }}>
          <Loader2 className="spin" size={14} /> Loading graph…
        </div>
      )}
      <svg
        ref={svg}
        className="graph-svg"
        style={{ height }}
        role="img"
        aria-label={`Graph of ${graph.nodes.length} notes and ${graph.edges.length} links`}
        onWheel={(e) => {
          touched.current = true;
          const k = Math.max(0.2, Math.min(4, view.k * (e.deltaY < 0 ? 1.12 : 1 / 1.12)));
          setView({ ...view, k });
        }}
        onPointerDown={(e) => {
          if ((e.target as Element).closest("[data-node]")) return;
          touched.current = true;
          drag.current = { panFrom: { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y } };
          (e.currentTarget as Element).setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          const d = drag.current;
          if (!d) return;
          if (d.node) {
            const w = toWorld(e.clientX, e.clientY);
            d.node.x = w.x;
            d.node.y = w.y;
            d.moved = true;
            tick((t) => t + 1);
          } else if (d.panFrom) {
            setView({ ...view, x: d.panFrom.vx + e.clientX - d.panFrom.x, y: d.panFrom.vy + e.clientY - d.panFrom.y });
          }
        }}
        onPointerUp={() => {
          const d = drag.current;
          drag.current = null;
          if (d?.node && !d.moved) onOpen(d.node.ghost ? "" : d.node.id, d.node.ghost ? d.node.title : undefined);
        }}
      >
        <g transform={`translate(${(svg.current?.clientWidth ?? 0) / 2 + view.x} ${height / 2 + view.y}) scale(${view.k})`}>
          {graph.edges.map((e) => {
            const a = byId.get(e.source);
            const b = byId.get(e.target);
            if (!a || !b) return null;
            const on = lit ? lit.has(a.id) && lit.has(b.id) : true;
            return <line key={`${e.source}>${e.target}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className={cx("g-edge", !on && "dim")} />;
          })}
          {nodes.current.map((n) => {
            const r = 4 + Math.min(10, Math.sqrt(n.degree) * 2.4);
            const found = match && n.title.toLowerCase().includes(match);
            const dim = (lit && !lit.has(n.id)) || (match && !found);
            return (
              <g
                key={n.id}
                data-node
                className={cx("g-node", `k-${n.kind}`, n.ghost && "ghost", n.id === focusId && "focus", dim && "dim", found && "found")}
                transform={`translate(${n.x} ${n.y})`}
                onPointerEnter={() => setHover(n.id)}
                onPointerLeave={() => setHover(null)}
                onPointerDown={(e) => {
                  e.stopPropagation();
                  n.fixed = true;
                  drag.current = { node: n };
                  svg.current?.setPointerCapture(e.pointerId);
                }}
                onDoubleClick={() => {
                  n.fixed = false;
                }}
              >
                <circle r={r} />
                {(view.k > 0.7 || n.degree > 2 || n.id === hover || n.id === focusId || found) && (
                  <text y={r + 11} textAnchor="middle">
                    {n.title.length > 28 ? `${n.title.slice(0, 27)}…` : n.title}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </svg>
      {!isLoading && graph.nodes.length <= 1 && (
        <div className="faint graph-empty">No links yet — type <code>[[</code> in a note to link it to another.</div>
      )}
    </div>
  );
}
