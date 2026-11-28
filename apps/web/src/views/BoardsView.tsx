import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowUpRight,
  BringToFront,
  Circle,
  Copy,
  Diamond,
  Download,
  Frame,
  Hand,
  LayoutDashboard,
  Link2,
  ListTodo,
  Maximize,
  Minus,
  MousePointer2,
  Plus,
  Redo2,
  SendToBack,
  Square,
  StickyNote,
  Trash2,
  Type,
  Undo2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { EmptyState } from "../components/primitives";
import { api } from "../lib/api";
import { type BoardItem, type BoardMeta, type CardRef, DEFAULT_SIZE, PALETTE, bounds, center, edgePoint, fill, inside, newId, snap, toSvg } from "../lib/board";
import { invalidateTasks } from "../lib/queries";
import { useUi } from "../lib/ui-store";
import { cx, debounce, isTypingTarget, relativeTime } from "../lib/util";

type Tool = "select" | "hand" | "sticky" | "text" | "shape" | "frame" | "connector";
const TOOLS: { id: Tool; label: string; key: string; icon: typeof Square }[] = [
  { id: "select", label: "Select", key: "V", icon: MousePointer2 },
  { id: "hand", label: "Pan", key: "H", icon: Hand },
  { id: "sticky", label: "Sticky note", key: "S", icon: StickyNote },
  { id: "text", label: "Text", key: "T", icon: Type },
  { id: "shape", label: "Shape", key: "R", icon: Square },
  { id: "frame", label: "Frame", key: "F", icon: Frame },
  { id: "connector", label: "Arrow (drag from one item to another)", key: "L", icon: ArrowUpRight },
];

/** Boards: a list of whiteboards, or one board's canvas. */
export function BoardsView({ boardId }: { boardId?: string }) {
  return boardId ? <BoardCanvas key={boardId} boardId={boardId} /> : <BoardList />;
}

function BoardList() {
  const ui = useUi();
  const qc = useQueryClient();
  const { data: boards = [] } = useQuery({ queryKey: ["boards"], queryFn: api.boards });
  const { data: templates = {} } = useQuery({ queryKey: ["board-templates"], queryFn: api.boardTemplates, staleTime: Infinity });
  const create = async (template: string) => {
    const b = await api.createBoard({ template });
    void qc.invalidateQueries({ queryKey: ["boards"] });
    ui.navigate("boards", b.id);
  };
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Boards</h1>
          <div className="page-sub">Whiteboards for thinking visually: sticky notes, shapes, frames, arrows — and live cards for your tasks and notes.</div>
        </div>
      </header>
      <div className="section-label">Start a board</div>
      <div className="board-templates">
        {Object.entries(templates).map(([id, name]) => (
          <button key={id} className="card board-template" onClick={() => void create(id)}>
            <LayoutDashboard size={18} />
            <span>{name}</span>
          </button>
        ))}
      </div>
      <div className="section-label" style={{ marginTop: 22 }}>
        Your boards
      </div>
      {boards.length === 0 ? (
        <EmptyState icon={LayoutDashboard} title="No boards yet">
          Pick a template above. Everything stays on this machine.
        </EmptyState>
      ) : (
        <div className="board-grid">
          {boards.map((b) => (
            <button key={b.id} className="card board-tile" onClick={() => ui.navigate("boards", b.id)}>
              <strong>
                {b.emoji ? `${b.emoji} ` : ""}
                {b.title}
              </strong>
              <span className="faint">
                {b.item_count} item{b.item_count === 1 ? "" : "s"} · edited {relativeTime(b.updated_at)}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

type Drag =
  | { mode: "move"; start: { x: number; y: number }; origin: Map<string, { x: number; y: number }>; moved: boolean }
  | { mode: "resize"; id: string; start: { x: number; y: number }; box: { w: number; h: number } }
  | { mode: "pan"; start: { x: number; y: number }; vp: { x: number; y: number } }
  | { mode: "marquee"; start: { x: number; y: number }; now: { x: number; y: number }; additive: boolean }
  | { mode: "link"; from: string; now: { x: number; y: number } };

function BoardCanvas({ boardId }: { boardId: string }) {
  const ui = useUi();
  const qc = useQueryClient();
  const [meta, setMeta] = useState<BoardMeta | null>(null);
  const [items, setItems] = useState<BoardItem[]>([]);
  const [refs, setRefs] = useState<Record<string, CardRef>>({});
  const [vp, setVp] = useState({ x: 120, y: 120, zoom: 1 });
  const [tool, setTool] = useState<Tool>("select");
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<string | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [gridSnap, setGridSnap] = useState(true);
  const [cardPicker, setCardPicker] = useState(false);
  const [saveState, setSaveState] = useState<"saved" | "saving" | "error">("saved");
  const stage = useRef<HTMLDivElement>(null);
  const space = useRef(false);
  const history = useRef<{ undo: BoardItem[][]; redo: BoardItem[][] }>({ undo: [], redo: [] });
  const pending = useRef<{ up: Set<string>; del: Set<string> }>({ up: new Set(), del: new Set() });
  const itemsRef = useRef(items);
  itemsRef.current = items;
  const clipboard = useRef<BoardItem[]>([]);

  // ---- load
  const load = useCallback(async () => {
    const r = await api.board(boardId);
    setMeta(r.board);
    setItems(r.items);
    setRefs(r.refs);
    const v = r.board.viewport;
    if (v && v.zoom) setVp({ x: v.x ?? 0, y: v.y ?? 0, zoom: v.zoom });
  }, [boardId]);
  useEffect(() => {
    load().catch((e: Error) => toast.error(e.message));
  }, [load]);

  // ---- save (batched; saves run one after another, in order)
  const inFlight = useRef<Promise<void>>(Promise.resolve());
  const flush = useMemo(
    () =>
      debounce(() => {
        inFlight.current = inFlight.current.then(async () => {
          const { up, del } = pending.current;
          if (!up.size && !del.size) return;
          pending.current = { up: new Set(), del: new Set() };
          const byId = new Map(itemsRef.current.map((i) => [i.id, i]));
          const upserts = [...up].map((id) => byId.get(id)).filter((i): i is BoardItem => !!i);
          setSaveState("saving");
          try {
            await api.boardChanges(boardId, upserts, [...del].filter((id) => !byId.has(id)));
            setSaveState("saved");
            void qc.invalidateQueries({ queryKey: ["boards"] });
          } catch (e) {
            setSaveState("error");
            toast.error(`Board not saved: ${(e as Error).message}`);
          }
        });
      }, 500),
    [boardId, qc],
  );
  /** Send what is pending and wait until every save has landed. */
  const settle = useCallback(async () => {
    flush.flush();
    await inFlight.current;
  }, [flush]);
  useEffect(() => () => flush.flush(), [flush]);
  const saveViewport = useMemo(() => debounce((v: { x: number; y: number; zoom: number }) => void api.updateBoard(boardId, { viewport: v }).catch(() => undefined), 1200), [boardId]);
  useEffect(() => saveViewport(vp), [vp, saveViewport]);

  /** Apply a change: remember the previous state for undo, mark what to save. */
  const commit = useCallback(
    (next: BoardItem[], opts: { record?: boolean } = {}) => {
      const prev = itemsRef.current;
      if (opts.record !== false) {
        history.current.undo.push(prev);
        if (history.current.undo.length > 100) history.current.undo.shift();
        history.current.redo = [];
      }
      const prevById = new Map(prev.map((i) => [i.id, i]));
      const nextIds = new Set(next.map((i) => i.id));
      for (const i of next) if (prevById.get(i.id) !== i) pending.current.up.add(i.id);
      for (const i of prev) if (!nextIds.has(i.id)) pending.current.del.add(i.id);
      // arrows whose ends are gone go too
      const filtered = next.filter((i) => i.kind !== "connector" || (nextIds.has(i.from_id ?? "") && nextIds.has(i.to_id ?? "")));
      for (const i of next) if (!filtered.includes(i)) pending.current.del.add(i.id);
      itemsRef.current = filtered;
      setItems(filtered);
      flush();
    },
    [flush],
  );
  const update = (ids: Set<string> | string[], patch: Partial<BoardItem> | ((i: BoardItem) => Partial<BoardItem>)) => {
    const set = new Set(ids);
    commit(items.map((i) => (set.has(i.id) ? { ...i, ...(typeof patch === "function" ? patch(i) : patch) } : i)));
  };
  const undo = () => {
    const prev = history.current.undo.pop();
    if (!prev) return;
    history.current.redo.push(itemsRef.current);
    commit(prev, { record: false });
  };
  const redo = () => {
    const next = history.current.redo.pop();
    if (!next) return;
    history.current.undo.push(itemsRef.current);
    commit(next, { record: false });
  };

  // ---- geometry
  const toWorld = (sx: number, sy: number) => {
    const r = stage.current!.getBoundingClientRect();
    return { x: (sx - r.left - vp.x) / vp.zoom, y: (sy - r.top - vp.y) / vp.zoom };
  };
  const zoomAt = (factor: number, sx?: number, sy?: number) => {
    const r = stage.current!.getBoundingClientRect();
    const px = sx ?? r.left + r.width / 2;
    const py = sy ?? r.top + r.height / 2;
    const zoom = Math.max(0.1, Math.min(4, vp.zoom * factor));
    const wx = (px - r.left - vp.x) / vp.zoom;
    const wy = (py - r.top - vp.y) / vp.zoom;
    setVp({ zoom, x: px - r.left - wx * zoom, y: py - r.top - wy * zoom });
  };
  const fit = () => {
    const bb = bounds(items);
    const r = stage.current?.getBoundingClientRect();
    if (!bb || !r) return setVp({ x: 120, y: 120, zoom: 1 });
    const zoom = Math.max(0.1, Math.min(2, Math.min((r.width - 120) / bb.w, (r.height - 120) / bb.h)));
    setVp({ zoom, x: r.width / 2 - (bb.x + bb.w / 2) * zoom, y: r.height / 2 - (bb.y + bb.h / 2) * zoom });
  };

  const topZ = () => Math.max(0, ...items.map((i) => i.z)) + 1;
  const add = (kind: Exclude<BoardItem["kind"], "connector">, at: { x: number; y: number }, extra: Partial<BoardItem> = {}) => {
    const [w, h] = DEFAULT_SIZE[kind];
    const item: BoardItem = {
      id: newId(),
      kind,
      x: snap(at.x - w / 2, gridSnap),
      y: snap(at.y - h / 2, gridSnap),
      w,
      h,
      z: kind === "frame" ? Math.min(0, ...items.map((i) => i.z)) - 1 : topZ(),
      text: kind === "frame" ? "Frame" : kind === "shape" ? "" : "",
      color: kind === "sticky" ? "yellow" : kind === "shape" ? "white" : kind === "frame" ? "gray" : null,
      style: kind === "shape" ? { shape: "rect" } : {},
      ref_type: null,
      ref_id: null,
      from_id: null,
      to_id: null,
      ...extra,
    };
    commit([...items, item]);
    setSel(new Set([item.id]));
    if (kind === "sticky" || kind === "text" || kind === "shape") setEditing(item.id);
    return item;
  };

  // ---- pointer handling
  const onPointerDown = (e: React.PointerEvent) => {
    if (editing) return;
    // Keep focus where it is: otherwise the browser's default focus change right
    // after this handler would blur a text box we have just opened.
    e.preventDefault();
    (document.activeElement as HTMLElement | null)?.blur?.();
    const target = e.target as HTMLElement;
    const itemEl = target.closest<HTMLElement>("[data-item]");
    const handle = target.closest<HTMLElement>("[data-resize]");
    const w = toWorld(e.clientX, e.clientY);
    stage.current?.setPointerCapture(e.pointerId);
    if (e.button === 1 || tool === "hand" || space.current) {
      setDrag({ mode: "pan", start: { x: e.clientX, y: e.clientY }, vp: { x: vp.x, y: vp.y } });
      return;
    }
    if (handle) {
      const it = items.find((i) => i.id === handle.dataset.resize)!;
      setDrag({ mode: "resize", id: it.id, start: w, box: { w: it.w, h: it.h } });
      return;
    }
    if (itemEl) {
      const id = itemEl.dataset.item!;
      if (tool === "connector") {
        setDrag({ mode: "link", from: id, now: w });
        return;
      }
      let next = sel;
      if (e.shiftKey) {
        next = new Set(sel);
        if (next.has(id)) next.delete(id);
        else next.add(id);
      } else if (!sel.has(id)) next = new Set([id]);
      setSel(next);
      // moving a frame carries what is inside it
      const moving = new Set(next);
      for (const id2 of next) {
        const f = items.find((i) => i.id === id2);
        if (f?.kind === "frame") for (const i of items) if (i.kind !== "frame" && i.kind !== "connector" && inside(f, i)) moving.add(i.id);
      }
      const origin = new Map(items.filter((i) => moving.has(i.id) && i.kind !== "connector").map((i) => [i.id, { x: i.x, y: i.y }]));
      setDrag({ mode: "move", start: w, origin, moved: false });
      return;
    }
    // empty canvas
    if (tool === "sticky" || tool === "text" || tool === "shape" || tool === "frame") {
      add(tool, w);
      if (!e.shiftKey) setTool("select");
      return;
    }
    setSel(e.shiftKey ? sel : new Set());
    setDrag({ mode: "marquee", start: w, now: w, additive: e.shiftKey });
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag) return;
    const w = toWorld(e.clientX, e.clientY);
    if (drag.mode === "pan") setVp({ ...vp, x: drag.vp.x + e.clientX - drag.start.x, y: drag.vp.y + e.clientY - drag.start.y });
    else if (drag.mode === "marquee" || drag.mode === "link") setDrag({ ...drag, now: w });
    else if (drag.mode === "move") {
      const dx = w.x - drag.start.x;
      const dy = w.y - drag.start.y;
      if (!drag.moved && Math.abs(dx) + Math.abs(dy) < 2 / vp.zoom) return;
      if (!drag.moved) {
        history.current.undo.push(items);
        history.current.redo = [];
        setDrag({ ...drag, moved: true });
      }
      setItems((cur) => cur.map((i) => (drag.origin.has(i.id) ? { ...i, x: snap(drag.origin.get(i.id)!.x + dx, gridSnap), y: snap(drag.origin.get(i.id)!.y + dy, gridSnap) } : i)));
    } else if (drag.mode === "resize") {
      setItems((cur) => cur.map((i) => (i.id === drag.id ? { ...i, w: Math.max(40, snap(drag.box.w + w.x - drag.start.x, gridSnap)), h: Math.max(30, snap(drag.box.h + w.y - drag.start.y, gridSnap)) } : i)));
    }
  };
  const onPointerUp = (e: React.PointerEvent) => {
    const d = drag;
    setDrag(null);
    if (!d) return;
    if (d.mode === "move" && d.moved) {
      for (const id of d.origin.keys()) pending.current.up.add(id);
      flush();
    } else if (d.mode === "resize") {
      history.current.undo.push(itemsRef.current.map((i) => (i.id === d.id ? { ...i, w: d.box.w, h: d.box.h } : i)));
      pending.current.up.add(d.id);
      flush();
    } else if (d.mode === "marquee") {
      const x = Math.min(d.start.x, d.now.x);
      const y = Math.min(d.start.y, d.now.y);
      const box = { x, y, w: Math.abs(d.now.x - d.start.x), h: Math.abs(d.now.y - d.start.y) };
      if (box.w > 4 || box.h > 4) {
        const hit = items.filter((i) => i.kind !== "connector" && i.x >= box.x && i.y >= box.y && i.x + i.w <= box.x + box.w && i.y + i.h <= box.y + box.h).map((i) => i.id);
        setSel(new Set([...(d.additive ? sel : []), ...hit]));
      }
    } else if (d.mode === "link") {
      const el = document.elementFromPoint(e.clientX, e.clientY)?.closest<HTMLElement>("[data-item]");
      const to = el?.dataset.item;
      if (to && to !== d.from && items.find((i) => i.id === to)?.kind !== "connector") {
        const c: BoardItem = { id: newId(), kind: "connector", x: 0, y: 0, w: 0, h: 0, z: topZ(), text: "", color: null, style: { end: "arrow" }, ref_type: null, ref_id: null, from_id: d.from, to_id: to };
        commit([...items, c]);
        setSel(new Set([c.id]));
      }
    }
  };
  const onWheel = (e: React.WheelEvent) => {
    if (e.ctrlKey || e.metaKey) zoomAt(e.deltaY < 0 ? 1.1 : 1 / 1.1, e.clientX, e.clientY);
    else setVp({ ...vp, x: vp.x - e.deltaX, y: vp.y - e.deltaY });
  };
  const onDoubleClick = (e: React.MouseEvent) => {
    const el = (e.target as HTMLElement).closest<HTMLElement>("[data-item]");
    if (!el) {
      add("sticky", toWorld(e.clientX, e.clientY));
      return;
    }
    const it = items.find((i) => i.id === el.dataset.item);
    if (!it) return;
    if (it.kind === "card") {
      if (it.ref_type === "task" && it.ref_id) ui.openTask(it.ref_id);
      else if (it.ref_id) ui.navigate("notes", it.ref_id);
    } else setEditing(it.id);
  };

  // ---- keyboard
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (editing || isTypingTarget(e.target)) return;
      const mod = e.metaKey || e.ctrlKey;
      if (e.key === " ") {
        space.current = e.type === "keydown";
        e.preventDefault();
        return;
      }
      if (e.type !== "keydown") return;
      const k = e.key.toLowerCase();
      if (mod && k === "z") {
        e.preventDefault();
        if (e.shiftKey) redo();
        else undo();
      } else if (mod && k === "y") {
        e.preventDefault();
        redo();
      } else if (mod && k === "a") {
        e.preventDefault();
        setSel(new Set(items.map((i) => i.id)));
      } else if (mod && k === "c" && sel.size) {
        clipboard.current = items.filter((i) => sel.has(i.id));
      } else if (mod && (k === "v" || k === "d") && (k === "d" ? sel.size : clipboard.current.length)) {
        e.preventDefault();
        duplicate(k === "d" ? items.filter((i) => sel.has(i.id)) : clipboard.current);
      } else if ((e.key === "Delete" || e.key === "Backspace") && sel.size) {
        e.preventDefault();
        commit(items.filter((i) => !sel.has(i.id)));
        setSel(new Set());
      } else if (e.key === "Escape") {
        setSel(new Set());
        setTool("select");
      } else if (e.key.startsWith("Arrow") && sel.size) {
        e.preventDefault();
        const step = e.shiftKey ? 10 : 1;
        const dx = e.key === "ArrowLeft" ? -step : e.key === "ArrowRight" ? step : 0;
        const dy = e.key === "ArrowUp" ? -step : e.key === "ArrowDown" ? step : 0;
        update(sel, (i) => ({ x: i.x + dx, y: i.y + dy }));
      } else if (!mod && (k === "+" || k === "=")) zoomAt(1.2);
      else if (!mod && k === "-") zoomAt(1 / 1.2);
      else if (!mod && e.shiftKey && k === "1") fit();
      else if (!mod) {
        const t = TOOLS.find((x) => x.key.toLowerCase() === k || (k === "o" && x.id === "shape"));
        if (t) setTool(t.id);
      }
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("keyup", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("keyup", onKey);
    };
  });

  const duplicate = (src: BoardItem[]) => {
    const map = new Map<string, string>();
    const boxes = src.filter((i) => i.kind !== "connector").map((i) => {
      const id = newId();
      map.set(i.id, id);
      return { ...i, id, x: i.x + 30, y: i.y + 30, z: i.kind === "frame" ? i.z : i.z + 0.5 };
    });
    const links = src.filter((i) => i.kind === "connector" && map.has(i.from_id ?? "") && map.has(i.to_id ?? "")).map((i) => ({ ...i, id: newId(), from_id: map.get(i.from_id!)!, to_id: map.get(i.to_id!)! }));
    commit([...items, ...boxes, ...links]);
    setSel(new Set([...boxes, ...links].map((i) => i.id)));
  };

  const toTask = async (id: string) => {
    await settle(); // a late save must not turn the new card back into a sticky
    try {
      await api.boardItemToTask(boardId, id);
      await load();
      invalidateTasks(qc);
      toast.success("Sticky turned into a task", { description: "It stays on the board as a live card." });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  if (!meta) return <div className="page faint">Loading board…</div>;
  const byId = new Map(items.map((i) => [i.id, i]));
  const frames = items.filter((i) => i.kind === "frame").sort((a, b) => a.z - b.z);
  const boxes = items.filter((i) => i.kind !== "frame" && i.kind !== "connector").sort((a, b) => a.z - b.z);
  const links = items.filter((i) => i.kind === "connector");
  const selected = items.filter((i) => sel.has(i.id));
  const selBox = bounds(selected);
  const one = selected.length === 1 ? selected[0]! : null;
  const grid = 20 * vp.zoom;

  return (
    <div className="board-shell">
      <div className="board-top">
        <button className="btn icon sm ghost" aria-label="All boards" onClick={() => ui.navigate("boards")}>
          <ArrowLeft />
        </button>
        <input
          className="board-title"
          aria-label="Board title"
          defaultValue={meta.title}
          onBlur={(e) => e.target.value.trim() && e.target.value !== meta.title && void api.updateBoard(boardId, { title: e.target.value }).then((b) => setMeta(b))}
          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        />
        <span className={cx("board-save", saveState)} aria-live="polite">
          {saveState === "saved" ? "Saved" : saveState === "saving" ? "Saving…" : "Not saved"}
        </span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
          <button className="btn sm ghost" onClick={() => setCardPicker(true)} title="Add a live card for a task or note">
            <Link2 /> Card
          </button>
          <button
            className="btn sm ghost"
            title="Export as SVG"
            onClick={() => {
              const blob = new Blob([toSvg(items, refs, meta.title)], { type: "image/svg+xml" });
              const a = document.createElement("a");
              a.href = URL.createObjectURL(blob);
              a.download = `${meta.title.replace(/[^\w -]+/g, "").trim() || "board"}.svg`;
              a.click();
              URL.revokeObjectURL(a.href);
            }}
          >
            <Download /> SVG
          </button>
          <button
            className="btn icon sm ghost danger"
            aria-label="Delete board"
            onClick={async () => {
              if (!confirm(`Delete the board “${meta.title}” and everything on it?`)) return;
              await api.deleteBoard(boardId);
              void qc.invalidateQueries({ queryKey: ["boards"] });
              ui.navigate("boards");
            }}
          >
            <Trash2 />
          </button>
        </div>
      </div>

      <div
        ref={stage}
        className={cx("board-stage", `tool-${tool}`, drag?.mode === "pan" && "panning")}
        style={{ backgroundSize: `${grid}px ${grid}px`, backgroundPosition: `${vp.x}px ${vp.y}px` }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onWheel={onWheel}
        onDoubleClick={onDoubleClick}
        aria-label="Board canvas"
        role="application"
      >
        <div className="board-world" style={{ transform: `translate(${vp.x}px, ${vp.y}px) scale(${vp.zoom})` }}>
          {frames.map((f) => (
            <div key={f.id} data-item={f.id} className={cx("b-frame", sel.has(f.id) && "sel")} style={{ left: f.x, top: f.y, width: f.w, height: f.h, ["--tint" as string]: fill(f.color, "gray") }}>
              <div className="b-frame-title">{editing === f.id ? <Editor item={f} onDone={(t) => { setEditing(null); if (t !== f.text) update([f.id], { text: t }); }} single /> : f.text || "Frame"}</div>
              {sel.has(f.id) && <span data-resize={f.id} className="b-resize" />}
            </div>
          ))}
          <svg className="b-links" aria-hidden>
            <defs>
              <marker id="b-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" />
              </marker>
            </defs>
            {links.map((c) => {
              const a = byId.get(c.from_id ?? "");
              const b = byId.get(c.to_id ?? "");
              if (!a || !b) return null;
              const p = edgePoint(a, center(b).x, center(b).y);
              const q = edgePoint(b, center(a).x, center(a).y);
              return (
                <g key={c.id} data-item={c.id} className={cx("b-link", sel.has(c.id) && "sel")}>
                  <line x1={p.x} y1={p.y} x2={q.x} y2={q.y} className="hit" />
                  <line x1={p.x} y1={p.y} x2={q.x} y2={q.y} markerEnd={c.style.end === "none" ? undefined : "url(#b-arrow)"} />
                  {c.text && editing !== c.id && (
                    <text x={(p.x + q.x) / 2} y={(p.y + q.y) / 2 - 6} textAnchor="middle">
                      {c.text}
                    </text>
                  )}
                </g>
              );
            })}
            {drag?.mode === "link" && byId.get(drag.from) && <line className="b-link-draft" x1={center(byId.get(drag.from)!).x} y1={center(byId.get(drag.from)!).y} x2={drag.now.x} y2={drag.now.y} />}
          </svg>
          {links
            .filter((c) => editing === c.id)
            .map((c) => {
              const a = byId.get(c.from_id ?? "")!;
              const b = byId.get(c.to_id ?? "")!;
              return (
                <div key={c.id} className="b-link-edit" style={{ left: (center(a).x + center(b).x) / 2 - 80, top: (center(a).y + center(b).y) / 2 - 18 }}>
                  <Editor item={c} single onDone={(t) => { setEditing(null); if (t !== c.text) update([c.id], { text: t }); }} />
                </div>
              );
            })}
          {boxes.map((i) => {
            const r = i.kind === "card" ? refs[`${i.ref_type}:${i.ref_id}`] : undefined;
            return (
              <div
                key={i.id}
                data-item={i.id}
                className={cx("b-item", `b-${i.kind}`, i.kind === "shape" && `shape-${i.style.shape ?? "rect"}`, `size-${i.style.size ?? "m"}`, sel.has(i.id) && "sel", r?.missing && "missing")}
                style={{ left: i.x, top: i.y, width: i.w, height: i.h, zIndex: 2, ["--fill" as string]: fill(i.color, i.kind === "shape" ? "white" : "yellow") }}
              >
                {i.kind === "card" ? (
                  <div className="b-card-body">
                    <span className="b-card-kind">
                      {i.ref_type === "task" ? <ListTodo size={12} /> : <StickyNote size={12} />} {i.ref_type === "task" ? `Task · ${r?.status?.replace("_", " ") ?? ""}` : "Note"}
                    </span>
                    <strong className={cx(r?.status === "done" && "done")}>{r?.title ?? "…"}</strong>
                    {r?.excerpt && <span className="b-card-excerpt">{r.excerpt}</span>}
                  </div>
                ) : editing === i.id ? (
                  <Editor item={i} onDone={(t) => { setEditing(null); if (t !== i.text) update([i.id], { text: t }); }} />
                ) : (
                  <div className="b-text">{i.text || (i.kind === "text" ? "Text" : "")}</div>
                )}
                {sel.has(i.id) && selected.length === 1 && <span data-resize={i.id} className="b-resize" />}
              </div>
            );
          })}
          {drag?.mode === "marquee" && (
            <div className="b-marquee" style={{ left: Math.min(drag.start.x, drag.now.x), top: Math.min(drag.start.y, drag.now.y), width: Math.abs(drag.now.x - drag.start.x), height: Math.abs(drag.now.y - drag.start.y) }} />
          )}
        </div>

        {selBox && !drag && !editing && (
          <div className="b-toolbar" style={{ left: Math.max(8, selBox.x * vp.zoom + vp.x), top: Math.max(8, selBox.y * vp.zoom + vp.y - 52) }} onPointerDown={(e) => e.stopPropagation()}>
            {selected.some((i) => i.kind === "sticky" || i.kind === "shape" || i.kind === "frame") &&
              Object.entries(PALETTE).map(([name, hex]) => (
                <button key={name} className="b-swatch" style={{ background: hex }} aria-label={`Colour ${name}`} onClick={() => update(sel, { color: name })} />
              ))}
            {one?.kind === "shape" && (
              <>
                <span className="b-sep" />
                <button className="btn icon sm ghost" aria-label="Rectangle" onClick={() => update(sel, (i) => ({ style: { ...i.style, shape: "rect" } }))}>
                  <Square />
                </button>
                <button className="btn icon sm ghost" aria-label="Ellipse" onClick={() => update(sel, (i) => ({ style: { ...i.style, shape: "ellipse" } }))}>
                  <Circle />
                </button>
                <button className="btn icon sm ghost" aria-label="Diamond" onClick={() => update(sel, (i) => ({ style: { ...i.style, shape: "diamond" } }))}>
                  <Diamond />
                </button>
              </>
            )}
            {selected.some((i) => i.kind === "sticky" || i.kind === "text" || i.kind === "shape") && (
              <>
                <span className="b-sep" />
                {(["s", "m", "l"] as const).map((s) => (
                  <button key={s} className="btn sm ghost" aria-label={`Text size ${s}`} onClick={() => update(sel, (i) => ({ style: { ...i.style, size: s } }))}>
                    {s.toUpperCase()}
                  </button>
                ))}
              </>
            )}
            {one?.kind === "connector" && (
              <button className="btn sm ghost" onClick={() => update(sel, (i) => ({ style: { ...i.style, end: i.style.end === "none" ? "arrow" : "none" } }))}>
                {one.style.end === "none" ? "Add arrowhead" : "Plain line"}
              </button>
            )}
            {one && (one.kind === "sticky" || one.kind === "text") && one.text.trim() && (
              <>
                <span className="b-sep" />
                <button className="btn sm ghost" onClick={() => void toTask(one.id)} title="Create a task from this and keep it here as a live card">
                  <ListTodo /> To task
                </button>
              </>
            )}
            <span className="b-sep" />
            <button className="btn icon sm ghost" aria-label="Bring to front" onClick={() => update(sel, { z: topZ() })}>
              <BringToFront />
            </button>
            <button className="btn icon sm ghost" aria-label="Send to back" onClick={() => update(sel, (i) => ({ z: Math.min(...items.map((x) => x.z)) - (i.kind === "frame" ? 2 : 1) }))}>
              <SendToBack />
            </button>
            <button className="btn icon sm ghost" aria-label="Duplicate" onClick={() => duplicate(selected)}>
              <Copy />
            </button>
            <button className="btn icon sm ghost danger" aria-label="Delete selection" onClick={() => { commit(items.filter((i) => !sel.has(i.id))); setSel(new Set()); }}>
              <Trash2 />
            </button>
          </div>
        )}

        <div className="b-tools" role="toolbar" aria-label="Board tools" onPointerDown={(e) => e.stopPropagation()}>
          {TOOLS.map((t) => (
            <button key={t.id} className={cx("btn icon ghost", tool === t.id && "on")} aria-pressed={tool === t.id} aria-label={`${t.label} (${t.key})`} title={`${t.label} — ${t.key}`} onClick={() => setTool(t.id)}>
              <t.icon />
            </button>
          ))}
          <span className="b-sep h" />
          <button className="btn icon ghost" aria-label="Undo" title="Undo — Ctrl+Z" onClick={undo}>
            <Undo2 />
          </button>
          <button className="btn icon ghost" aria-label="Redo" title="Redo — Ctrl+Shift+Z" onClick={redo}>
            <Redo2 />
          </button>
        </div>

        <div className="b-zoom" onPointerDown={(e) => e.stopPropagation()}>
          <label className="b-snap" title="Snap to a 10 px grid">
            <input type="checkbox" checked={gridSnap} onChange={(e) => setGridSnap(e.target.checked)} /> Snap
          </label>
          <button className="btn icon sm ghost" aria-label="Zoom out" onClick={() => zoomAt(1 / 1.2)}>
            <Minus />
          </button>
          <span className="b-zoom-pct">{Math.round(vp.zoom * 100)}%</span>
          <button className="btn icon sm ghost" aria-label="Zoom in" onClick={() => zoomAt(1.2)}>
            <Plus />
          </button>
          <button className="btn icon sm ghost" aria-label="Fit to content" title="Fit — Shift+1" onClick={fit}>
            <Maximize />
          </button>
        </div>
        {items.length === 0 && (
          <div className="b-hint" aria-hidden>
            Double-click anywhere for a sticky note · <b>S</b> sticky · <b>T</b> text · <b>R</b> shape · <b>F</b> frame · <b>L</b> arrow · Ctrl+scroll to zoom · Space+drag to pan
          </div>
        )}
      </div>
      {cardPicker && (
        <CardPicker
          onClose={() => setCardPicker(false)}
          onPick={async (refType, refId) => {
            setCardPicker(false);
            const r = stage.current!.getBoundingClientRect();
            add("card", toWorld(r.left + r.width / 2, r.top + r.height / 2), { ref_type: refType, ref_id: refId, color: null });
            setEditing(null);
            await settle();
            await load(); // the card's live title and status
          }}
        />
      )}
    </div>
  );
}

/** In-place text editing: Enter for a new line (single-line: Enter saves), Esc or click away saves. */
function Editor({ item, onDone, single }: { item: BoardItem; onDone: (text: string) => void; single?: boolean }) {
  const [v, setV] = useState(item.text);
  return (
    <textarea
      className={cx("b-editor", single && "single")}
      autoFocus
      value={v}
      aria-label="Edit text"
      onChange={(e) => setV(e.target.value)}
      onPointerDown={(e) => e.stopPropagation()}
      onFocus={(e) => e.currentTarget.select()}
      onBlur={() => onDone(v)}
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === "Escape" || (e.key === "Enter" && (single || e.metaKey || e.ctrlKey))) {
          e.preventDefault();
          (e.target as HTMLTextAreaElement).blur();
        }
      }}
    />
  );
}

function CardPicker({ onClose, onPick }: { onClose: () => void; onPick: (refType: "task" | "note", id: string) => void }) {
  const [q, setQ] = useState("");
  const { data: tasks = [] } = useQuery({ queryKey: ["tasks", "board-picker"], queryFn: () => api.tasks({ top_level: true }) });
  const { data: notes = [] } = useQuery({ queryKey: ["note-titles"], queryFn: api.noteTitles });
  const m = q.trim().toLowerCase();
  const t = tasks.filter((x) => x.status !== "done" && x.title.toLowerCase().includes(m)).slice(0, 8);
  const n = notes.filter((x) => x.title.toLowerCase().includes(m)).slice(0, 8);
  return (
    <div className="b-picker-backdrop" onPointerDown={onClose}>
      <div className="card b-picker" role="dialog" aria-label="Add a card" onPointerDown={(e) => e.stopPropagation()}>
        <input className="input" autoFocus placeholder="Find a task or note…" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Escape" && onClose()} aria-label="Find a task or note" />
        <div className="section-label">Tasks</div>
        {t.map((x) => (
          <button key={x.id} onClick={() => onPick("task", x.id)}>
            <ListTodo size={13} /> {x.title}
          </button>
        ))}
        {t.length === 0 && <div className="faint">No open tasks match.</div>}
        <div className="section-label">Notes</div>
        {n.map((x) => (
          <button key={x.id} onClick={() => onPick("note", x.id)}>
            <StickyNote size={13} /> {x.title}
          </button>
        ))}
        {n.length === 0 && <div className="faint">No notes match.</div>}
      </div>
    </div>
  );
}
