import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  BookOpen,
  BookOpenText,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clipboard,
  FilePlus2,
  FolderPlus,
  GripVertical,
  History,
  Plus,
  Sparkles,
  Trash2,
  Wand2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Stars } from "../components/meetings";
import { Dialog, EmptyState, Sheet } from "../components/primitives";
import { api } from "../lib/api";
import type { BookNode, Improvement, NodeKind, Page } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { cx, debounce, isTypingTarget, relativeTime, wordDiff } from "../lib/util";

const STYLES: { id: string; label: string; hint: string }[] = [
  { id: "clearer", label: "Clearer", hint: "Goal first, then context, then the ask" },
  { id: "specific", label: "More specific", hint: "Inputs, outputs, edge cases, acceptance" },
  { id: "context", label: "Add context", hint: "Language, files, constraints — placeholders for unknowns" },
  { id: "format", label: "Output format", hint: "Say exactly what to return" },
  { id: "concise", label: "Concise", hint: "Shorter, nothing lost" },
];
const LAST_BOOK = "ppos.lastBook";
const SPREAD_KEY = "ppos.bookSpread";

function useMediaQuery(q: string): boolean {
  const [m, setM] = useState(() => window.matchMedia(q).matches);
  useEffect(() => {
    const mq = window.matchMedia(q);
    const on = () => setM(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [q]);
  return m;
}

/** Depth-first reading order of pages = the book's page numbering. */
function readingOrder(nodes: BookNode[]): BookNode[] {
  const kids = new Map<string | null, BookNode[]>();
  for (const n of nodes) kids.set(n.parent_id, [...(kids.get(n.parent_id) ?? []), n]);
  for (const list of kids.values()) list.sort((a, b) => a.position - b.position);
  const out: BookNode[] = [];
  const walk = (pid: string | null) => {
    for (const n of kids.get(pid) ?? []) {
      if (n.kind === "page") out.push(n);
      else walk(n.id);
    }
  };
  walk(null);
  return out;
}

function breadcrumb(nodes: BookNode[], id: string): BookNode[] {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const out: BookNode[] = [];
  let cur = byId.get(id)?.parent_id ?? null;
  while (cur) {
    const n = byId.get(cur);
    if (!n) break;
    out.unshift(n);
    cur = n.parent_id;
  }
  return out;
}

export function PromptBookView({ pageId }: { pageId?: string }) {
  const ui = useUi();
  const qc = useQueryClient();
  const { data: books = [], isLoading } = useQuery({ queryKey: ["books"], queryFn: api.books });
  const { data: pageForRoute } = useQuery({ queryKey: ["page", pageId], queryFn: () => api.node(pageId!), enabled: !!pageId });
  const [bookId, setBookId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(LAST_BOOK);
    } catch {
      return null;
    }
  });
  const activeBookId = pageForRoute?.book_id ?? (books.some((b) => b.id === bookId) ? bookId : books[0]?.id) ?? null;
  useEffect(() => {
    if (!activeBookId) return;
    try {
      localStorage.setItem(LAST_BOOK, activeBookId);
    } catch {
      /* per-browser convenience only */
    }
  }, [activeBookId]);
  const { data: tree } = useQuery({ queryKey: ["book-tree", activeBookId], queryFn: () => api.bookTree(activeBookId!), enabled: !!activeBookId });
  const nodes = useMemo(() => tree?.nodes ?? [], [tree]);
  const pages = useMemo(() => readingOrder(nodes), [nodes]);
  // Never fall back to another page while the requested one is still loading
  // (otherwise typing could land in the wrong page).
  const currentId = pageId && (nodes.some((n) => n.id === pageId) || pageForRoute?.id === pageId) ? pageId : pages[0]?.id;
  const index = pages.findIndex((p) => p.id === currentId);
  const [direction, setDirection] = useState(1);
  const wide = useMediaQuery("(min-width: 1900px)");
  const [spreadPref, setSpreadPref] = useState(() => {
    try {
      return localStorage.getItem(SPREAD_KEY) !== "off";
    } catch {
      return true;
    }
  });
  const spread = wide && spreadPref && index >= 0 && index < pages.length - 1;
  const nextPage = spread ? pages[index + 1] : undefined;
  const refreshTree = useCallback(() => qc.invalidateQueries({ queryKey: ["book-tree"] }), [qc]);

  const go = useCallback(
    (delta: number) => {
      const next = pages[index + delta];
      if (!next) return;
      setDirection(delta);
      ui.navigate("book", next.id);
    },
    [pages, index, ui],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTypingTarget(e.target) || e.metaKey || e.ctrlKey) return;
      if (e.key === "ArrowRight") go(1);
      if (e.key === "ArrowLeft") go(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  const create = async (kind: NodeKind, parentId: string | null) => {
    if (!activeBookId) return;
    const title = kind === "page" ? "" : kind === "chapter" ? "New chapter" : "New section";
    const n = await api.createNode({ book_id: activeBookId, kind, title, parent_id: parentId });
    qc.setQueryData(["page", n.id], n);
    await refreshTree(); // tree contains the new page before we open it
    if (kind === "page") {
      setDirection(1);
      ui.navigate("book", n.id);
    }
  };

  if (isLoading) return <div className="page faint">Loading…</div>;
  if (books.length === 0) return <FirstBook onCreated={(id) => { setBookId(id); void qc.invalidateQueries({ queryKey: ["books"] }); }} />;

  return (
    <div className="book-layout">
      <aside className="book-toc">
        <div className="toc-head">
          <select
            className="select"
            value={activeBookId ?? ""}
            aria-label="Book"
            onChange={(e) => {
              setBookId(e.target.value);
              ui.navigate("book");
            }}
          >
            {books.map((b) => (
              <option key={b.id} value={b.id}>
                {b.emoji ? `${b.emoji} ` : ""}
                {b.title}
              </option>
            ))}
          </select>
          <button
            className="btn icon"
            aria-label="New book"
            title="New book"
            onClick={async () => {
              const t = prompt("Name of the new book", "Prompts");
              if (!t) return;
              const b = await api.createBook({ title: t, emoji: "📘" });
              setBookId(b.id);
              void qc.invalidateQueries({ queryKey: ["books"] });
              ui.navigate("book");
            }}
          >
            <Plus />
          </button>
        </div>
        <div className="toc-actions">
          <button className="btn sm" onClick={() => void create("page", null)}>
            <FilePlus2 /> Page
          </button>
          <button className="btn sm ghost" onClick={() => void create("chapter", null)}>
            <FolderPlus /> Chapter
          </button>
          {wide && (
            <button
              className="btn sm ghost"
              aria-pressed={spreadPref}
              title="Show two pages side by side"
              style={{ marginLeft: "auto" }}
              onClick={() => {
                setSpreadPref((v) => {
                  try {
                    localStorage.setItem(SPREAD_KEY, v ? "off" : "on");
                  } catch {
                    /* per-browser preference only */
                  }
                  return !v;
                });
              }}
            >
              <BookOpen /> {spreadPref ? "Spread" : "Single"}
            </button>
          )}
        </div>
        <Toc nodes={nodes} currentId={currentId} onOpen={(id) => ui.navigate("book", id)} onCreate={create} onChanged={() => void refreshTree()} pageNumbers={pages} />
      </aside>

      <main className="book-desk">
        {currentId ? (
          <div className={cx("book-stage", spread && "spread")}>
            <button className="page-turn left" aria-label="Previous page" disabled={index <= 0} onClick={() => go(-1)}>
              <ChevronLeft />
            </button>
            <AnimatePresence mode="wait" custom={direction} initial={false}>
              <motion.div
                key={currentId}
                custom={direction}
                className="page-sheet-wrap"
                initial={{ opacity: 0, rotateY: direction > 0 ? -14 : 14, x: direction > 0 ? 40 : -40 }}
                animate={{ opacity: 1, rotateY: 0, x: 0 }}
                exit={{ opacity: 0, rotateY: direction > 0 ? 10 : -10, x: direction > 0 ? -30 : 30 }}
                transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}
                style={{ transformOrigin: direction > 0 ? "left center" : "right center" }}
              >
                <PageEditor
                  key={currentId}
                  pageId={currentId}
                  nodes={nodes}
                  number={index + 1}
                  total={pages.length}
                  onChanged={() => void refreshTree()}
                  onDeleted={() => {
                    void refreshTree();
                    const fallback = pages[index - 1] ?? pages[index + 1];
                    ui.navigate("book", fallback?.id);
                  }}
                />
              </motion.div>
            </AnimatePresence>
            {nextPage && (
              <AnimatePresence mode="wait" initial={false}>
                <motion.div key={nextPage.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
                  <FacingPage id={nextPage.id} number={index + 2} total={pages.length} onOpen={() => go(1)} />
                </motion.div>
              </AnimatePresence>
            )}
            <button className="page-turn right" aria-label="Next page" disabled={index >= pages.length - 1} onClick={() => go(1)}>
              <ChevronRight />
            </button>
          </div>
        ) : (
          <div style={{ height: "100%", display: "grid", placeItems: "center" }}>
            <EmptyState icon={BookOpenText} title="An empty book">
              Add a page for your first prompt, or a chapter to organise them.
            </EmptyState>
          </div>
        )}
      </main>
    </div>
  );
}

function FirstBook({ onCreated }: { onCreated: (id: string) => void }) {
  const [title, setTitle] = useState("My prompts");
  return (
    <div className="page" style={{ maxWidth: 52 + "rem", margin: "6vh auto" }}>
      <div className="soon-hero">
        <div className="project-icon" style={{ background: "var(--accent)", width: "2.6rem", height: "2.6rem", borderRadius: 10 }}>
          <BookOpenText size={20} />
        </div>
        <h2>Your Prompt Book</h2>
        <p>
          A book for everything you ask AI assistants: write prompts page by page, organise them in chapters and sections, reuse them with
          <code> {"{{variables}}"}</code>, keep every version, and polish them with your local AI before copying to Copilot.
        </p>
        <form
          style={{ display: "flex", gap: 8, marginTop: 18 }}
          onSubmit={async (e) => {
            e.preventDefault();
            const b = await api.createBook({ title, emoji: "📘" });
            onCreated(b.id);
          }}
        >
          <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Book title" autoFocus />
          <button className="btn primary" type="submit">
            <Plus /> Create book
          </button>
        </form>
      </div>
    </div>
  );
}

function Toc({
  nodes,
  currentId,
  onOpen,
  onCreate,
  onChanged,
  pageNumbers,
}: {
  nodes: BookNode[];
  currentId?: string;
  onOpen: (id: string) => void;
  onCreate: (kind: NodeKind, parent: string | null) => Promise<void>;
  onChanged: () => void;
  pageNumbers: BookNode[];
}) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [dragId, setDragId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);
  const byParent = useMemo(() => {
    const m = new Map<string | null, BookNode[]>();
    for (const n of nodes) m.set(n.parent_id, [...(m.get(n.parent_id) ?? []), n]);
    for (const l of m.values()) l.sort((a, b) => a.position - b.position);
    return m;
  }, [nodes]);
  const numberOf = useMemo(() => new Map(pageNumbers.map((p, i) => [p.id, i + 1])), [pageNumbers]);

  const drop = async (target: BookNode | null) => {
    setOverId(null);
    const id = dragId;
    setDragId(null);
    if (!id || id === target?.id) return;
    // Onto a chapter/section: move inside. Onto a page: place right after it.
    const parent = target ? (target.kind === "page" ? target.parent_id : target.id) : null;
    const position = target && target.kind === "page" ? target.position + 0.5 : undefined;
    try {
      await api.moveNode(id, parent, position);
      onChanged();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const render = (parent: string | null, depth: number): JSX.Element[] =>
    (byParent.get(parent) ?? []).map((n) => {
      const isOpen = !collapsed.has(n.id);
      return (
        <div key={n.id}>
          <div
            className={cx("toc-row", `kind-${n.kind}`, n.id === currentId && "active", overId === n.id && "drop")}
            style={{ paddingLeft: `${0.5 + depth * 0.9}rem` }}
            draggable
            onDragStart={(e) => {
              setDragId(n.id);
              e.dataTransfer.effectAllowed = "move";
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setOverId(n.id);
            }}
            onDragLeave={() => setOverId((o) => (o === n.id ? null : o))}
            onDrop={(e) => {
              e.preventDefault();
              void drop(n);
            }}
            onClick={() => (n.kind === "page" ? onOpen(n.id) : setCollapsed((c) => { const s = new Set(c); if (s.has(n.id)) s.delete(n.id); else s.add(n.id); return s; }))}
            role="treeitem"
            aria-expanded={n.kind === "page" ? undefined : isOpen}
            aria-selected={n.id === currentId}
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && n.kind === "page" && onOpen(n.id)}
          >
            <GripVertical className="grip" />
            {n.kind !== "page" && <ChevronDown className={cx("caret", !isOpen && "closed")} />}
            <span className="toc-emoji">{n.emoji ?? (n.kind === "page" ? "📄" : n.kind === "chapter" ? "📚" : "🗂️")}</span>
            <span className="toc-title">{n.title}</span>
            {n.kind === "page" ? (
              <span className="toc-num">{numberOf.get(n.id)}</span>
            ) : (
              <span className="toc-add">
                <button className="btn icon sm ghost" title="Add page here" aria-label={`Add page to ${n.title}`} onClick={(e) => { e.stopPropagation(); void onCreate("page", n.id); }}>
                  <FilePlus2 />
                </button>
                <button className="btn icon sm ghost" title="Add section here" aria-label={`Add section to ${n.title}`} onClick={(e) => { e.stopPropagation(); void onCreate("section", n.id); }}>
                  <FolderPlus />
                </button>
              </span>
            )}
          </div>
          {n.kind !== "page" && isOpen && render(n.id, depth + 1)}
        </div>
      );
    });

  return (
    <div className="toc" role="tree" aria-label="Table of contents">
      {render(null, 0)}
      <div
        className={cx("toc-root-drop", dragId && "visible", overId === "__root" && "drop")}
        onDragOver={(e) => {
          e.preventDefault();
          setOverId("__root");
        }}
        onDrop={(e) => {
          e.preventDefault();
          void drop(null);
        }}
      >
        Drop here to move to the top level
      </div>
    </div>
  );
}

type SaveState = "saved" | "saving" | "dirty";

function PageEditor({ pageId, nodes, number, total, onChanged, onDeleted }: { pageId: string; nodes: BookNode[]; number: number; total: number; onChanged: () => void; onDeleted: () => void }) {
  const qc = useQueryClient();
  const { data: page } = useQuery({ queryKey: ["page", pageId], queryFn: () => api.node(pageId) });
  const [title, setTitle] = useState<string | null>(null);
  const [body, setBody] = useState<string | null>(null);
  const [state, setState] = useState<SaveState>("saved");
  const [improveOpen, setImproveOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [vars, setVars] = useState<string[] | null>(null);
  const pending = useRef<{ title?: string; body?: string }>({});

  useEffect(() => {
    if (page && body === null) {
      setBody(page.body);
      setTitle(page.title === "Untitled page" ? "" : page.title);
    }
  }, [page, body]);

  const save = useMemo(
    () =>
      debounce(async () => {
        const changes = pending.current;
        pending.current = {};
        if (!Object.keys(changes).length) return;
        setState("saving");
        const p = await api.updateNode(pageId, changes);
        qc.setQueryData(["page", pageId], p);
        setState(Object.keys(pending.current).length ? "dirty" : "saved");
        if (changes.title !== undefined) onChanged();
      }, 600),
    [pageId, qc, onChanged],
  );
  useEffect(() => () => save.flush(), [save]);

  if (!page || body === null || title === null) return <div className="page-sheet faint">Loading…</div>;
  const crumbs = breadcrumb(nodes, pageId);
  const variables = Array.from(new Set([...body.matchAll(/\{\{\s*([A-Za-z_][\w.-]{0,40})\s*\}\}/g)].map((m) => m[1]!)));

  const copy = async (values: Record<string, string>) => {
    save.flush();
    const { text } = await api.usePage(pageId, values, body);
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Copied — paste it into Copilot", { description: `${text.length} characters` });
    } catch {
      toast("Copy blocked by the browser", { description: "Select the text and copy it manually." });
    }
    void qc.invalidateQueries({ queryKey: ["page", pageId] });
  };

  return (
    <article className="page-sheet" aria-label={`Page ${number} of ${total}`}>
      <header className="sheet-top">
        <div className="crumbs">
          {crumbs.map((c) => (
            <span key={c.id}>
              {c.emoji ?? ""} {c.title} ›
            </span>
          ))}
        </div>
        <span className="page-no">
          Page {number} of {total}
        </span>
      </header>
      <div className="page-date">{new Date(page.created_at).toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</div>
      <input
        className="page-title"
        value={title}
        placeholder="Untitled prompt"
        aria-label="Page title"
        onChange={(e) => {
          setTitle(e.target.value);
          pending.current.title = e.target.value || "Untitled page";
          setState("dirty");
          save();
        }}
      />
      <textarea
        className="page-body"
        value={body}
        aria-label="Prompt text"
        placeholder={"Write your prompt…\n\nTip: use {{variables}} for parts that change — you'll be asked for them when copying."}
        onChange={(e) => {
          setBody(e.target.value);
          pending.current.body = e.target.value;
          setState("dirty");
          save();
        }}
      />
      {variables.length > 0 && (
        <div className="page-vars">
          Variables:{" "}
          {variables.map((v) => (
            <code key={v}>{`{{${v}}}`}</code>
          ))}
        </div>
      )}
      <footer className="sheet-actions">
        <button className="btn primary" onClick={() => (variables.length ? setVars(variables) : void copy({}))}>
          <Clipboard /> Copy for Copilot
        </button>
        <button className="btn" onClick={() => setImproveOpen(true)}>
          <Wand2 /> Improve with AI
        </button>
        <button className="btn ghost" onClick={() => setHistoryOpen(true)}>
          <History /> History
        </button>
        <span className="sheet-meta">
          {page.use_count > 0 ? `Used ${page.use_count}× · ${relativeTime(page.last_used_at!)}` : "Not used yet"}
          <span className="faint"> · {state === "saved" ? "Saved" : state === "saving" ? "Saving…" : "Editing"}</span>
        </span>
        <span title="Did this prompt work well?">
          <Stars value={page.rating} onChange={(v) => api.updateNode(pageId, { rating: v }).then((p) => qc.setQueryData(["page", pageId], p))} />
        </span>
        <button
          className="btn icon ghost danger"
          aria-label="Delete page"
          onClick={async () => {
            if (!confirm("Delete this page and its history?")) return;
            await api.deleteNode(pageId);
            onDeleted();
          }}
        >
          <Trash2 />
        </button>
      </footer>

      <VariablesDialog vars={vars} onClose={() => setVars(null)} onSubmit={(v) => { setVars(null); void copy(v); }} />
      <ImproveDialog
        open={improveOpen}
        pageId={pageId}
        body={body}
        onClose={() => setImproveOpen(false)}
        onAccepted={(p) => {
          setBody(p.body);
          qc.setQueryData(["page", pageId], p);
        }}
      />
      <HistorySheet
        open={historyOpen}
        pageId={pageId}
        onClose={() => setHistoryOpen(false)}
        onRestored={(p) => {
          setBody(p.body);
          qc.setQueryData(["page", pageId], p);
        }}
      />
    </article>
  );
}

function VariablesDialog({ vars, onClose, onSubmit }: { vars: string[] | null; onClose: () => void; onSubmit: (v: Record<string, string>) => void }) {
  const [values, setValues] = useState<Record<string, string>>({});
  return (
    <Dialog open={vars !== null} onClose={onClose} label="Fill in variables" width={520}>
      <form
        className="log-call"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(values);
        }}
      >
        <div className="lc-head">
          <Clipboard size={18} />
          <h3>Fill in before copying</h3>
        </div>
        {vars?.map((v, i) => (
          <label key={v} className="lc-field">
            <span>
              <code>{`{{${v}}}`}</code>
            </span>
            <input className="input" autoFocus={i === 0} value={values[v] ?? ""} onChange={(e) => setValues({ ...values, [v]: e.target.value })} />
          </label>
        ))}
        <div className="lc-foot">
          <span className="faint" style={{ fontSize: "0.857rem" }}>
            Empty values stay as placeholders.
          </span>
          <button type="submit" className="btn primary">
            <Clipboard /> Copy
          </button>
        </div>
      </form>
    </Dialog>
  );
}

function ImproveDialog({ open, pageId, body, onClose, onAccepted }: { open: boolean; pageId: string; body: string; onClose: () => void; onAccepted: (p: Page) => void }) {
  const { data: status } = useQuery({ queryKey: ["ai-status"], queryFn: api.aiStatus, enabled: open, staleTime: 30_000 });
  const [style, setStyle] = useState("clearer");
  const [result, setResult] = useState<Improvement | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!open) setResult(null);
  }, [open]);

  const run = async () => {
    setBusy(true);
    try {
      setResult(await api.improvePage(pageId, style, body));
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} label="Improve with local AI" width={960}>
      <div className="improve">
        <div className="lc-head">
          <Sparkles size={18} />
          <h3>Improve with local AI</h3>
          <span className={cx("chip", status?.reachable ? "green" : "orange")} style={{ marginLeft: "auto" }}>
            {status?.enabled ? `${status.provider} · ${status.model}${status.reachable ? "" : " · not reachable"}` : "Local AI off"}
          </span>
          <button className="btn icon ghost" aria-label="Close" onClick={onClose}>
            <X />
          </button>
        </div>
        {!status?.enabled && (
          <div className="ai-off">
            <strong>Runs entirely on your machine — nothing is sent to the cloud.</strong>
            <ol>
              <li>
                Install <a href="https://ollama.com" target="_blank" rel="noreferrer">Ollama</a> and pull a model, e.g. <code>ollama pull qwen3:8b</code>.
              </li>
              <li>
                Start the app with <code>PPOS_LLM_PROVIDER=ollama</code> and <code>PPOS_LLM_MODEL=qwen3:8b</code> (or put them in <code>.env</code>).
              </li>
            </ol>
            <span className="faint">Your original prompt is never overwritten — every suggestion is kept as a version.</span>
          </div>
        )}
        <div className="style-chips" role="radiogroup" aria-label="Improvement style">
          {STYLES.map((s) => (
            <button key={s.id} role="radio" aria-checked={style === s.id} className={cx("style-chip", style === s.id && "on")} onClick={() => setStyle(s.id)} title={s.hint}>
              <strong>{s.label}</strong>
              <span>{s.hint}</span>
            </button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn primary" disabled={busy || !status?.enabled} onClick={() => void run()}>
            <Wand2 /> {busy ? "Thinking…" : result ? "Try again" : "Improve"}
          </button>
          {result && (
            <span className="faint" style={{ fontSize: "0.857rem", alignSelf: "center" }}>
              {result.model} · {result.template} · {(result.latency_ms / 1000).toFixed(1)} s
            </span>
          )}
        </div>
        {result && (
          <>
            <div className="compare">
              <section>
                <div className="section-label">Original</div>
                <pre>{result.original}</pre>
              </section>
              <section>
                <div className="section-label">Suggestion · changes highlighted</div>
                <pre>
                  {wordDiff(result.original, result.improved).map((p, i) =>
                    p.kind === "del" ? null : (
                      <span key={i} className={p.kind === "add" ? "diff-add" : undefined}>
                        {p.text}
                      </span>
                    ),
                  )}
                </pre>
              </section>
            </div>
            <div className="lc-foot">
              <span className="faint" style={{ fontSize: "0.857rem" }}>
                Saved as version {result.version}. Accepting keeps the original in History.
              </span>
              <button
                className="btn"
                onClick={async () => {
                  await navigator.clipboard.writeText(result.improved).catch(() => undefined);
                  toast.success("Suggestion copied");
                }}
              >
                <Clipboard /> Copy suggestion
              </button>
              <button
                className="btn primary"
                onClick={async () => {
                  const p = await api.acceptVersion(pageId, result.version);
                  onAccepted(p);
                  toast.success("Suggestion accepted", { description: "The original is still in History." });
                  onClose();
                }}
              >
                Use suggestion
              </button>
            </div>
          </>
        )}
      </div>
    </Dialog>
  );
}

const SOURCE_LABEL: Record<string, string> = { original: "Original", edited: "Saved", ai: "AI suggestion", used: "Copied", restored: "Restored" };

function HistorySheet({ open, pageId, onClose, onRestored }: { open: boolean; pageId: string; onClose: () => void; onRestored: (p: Page) => void }) {
  const { data: versions = [] } = useQuery({ queryKey: ["page-versions", pageId], queryFn: () => api.pageVersions(pageId), enabled: open });
  const [sel, setSel] = useState<number | null>(null);
  const current = versions.find((v) => v.version === sel) ?? versions[0];
  return (
    <Sheet open={open} onClose={onClose} label="Prompt history">
      <div className="sheet-head">
        <History size={16} />
        <strong style={{ fontWeight: 600 }}>History</strong>
        <span className="faint" style={{ fontSize: "0.857rem" }}>
          {versions.length} versions
        </span>
        <button className="btn icon ghost" style={{ marginLeft: "auto" }} aria-label="Close" onClick={onClose}>
          <X />
        </button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "13rem 1fr", minHeight: 0, flex: 1 }}>
        <div style={{ borderRight: "1px solid var(--border)", overflowY: "auto", padding: 8 }}>
          {versions.map((v) => (
            <button key={v.version} className={cx("note-item", current?.version === v.version && "active")} onClick={() => setSel(v.version)}>
              <span className="n-title">
                v{v.version} · {SOURCE_LABEL[v.source]}
              </span>
              <span className="n-meta">{relativeTime(v.created_at)}</span>
            </button>
          ))}
        </div>
        <div style={{ overflowY: "auto", padding: "16px 20px" }}>
          {current && (
            <>
              <div className="faint" style={{ fontSize: "0.857rem", marginBottom: 8 }}>
                {SOURCE_LABEL[current.source]} · {new Date(current.created_at).toLocaleString()}
                {current.model && ` · ${current.model}`}
                {current.note && ` · ${current.note}`}
              </div>
              <pre className="history-text">{current.body || "(empty)"}</pre>
              <button
                className="btn primary"
                onClick={async () => {
                  const p = await api.restorePage(pageId, current.version);
                  onRestored(p);
                  toast.success(`Restored version ${current.version}`);
                  onClose();
                }}
              >
                <History /> Restore this version
              </button>
            </>
          )}
        </div>
      </div>
    </Sheet>
  );
}


/** Read-only right-hand page of the spread; click to turn to it. */
function FacingPage({ id, number, total, onOpen }: { id: string; number: number; total: number; onOpen: () => void }) {
  const { data: page } = useQuery({ queryKey: ["page", id], queryFn: () => api.node(id) });
  return (
    <button className="page-sheet facing" onClick={onOpen} aria-label={`Open page ${number}: ${page?.title ?? ""}`}>
      <header className="sheet-top">
        <span />
        <span className="page-no">
          Page {number} of {total}
        </span>
      </header>
      {page && (
        <>
          <div className="page-date">{new Date(page.created_at).toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</div>
          <div className="page-title">{page.title}</div>
          <div className="page-body facing-body">{page.body || "—"}</div>
        </>
      )}
      <span className="facing-hint">Click to turn the page →</span>
    </button>
  );
}
