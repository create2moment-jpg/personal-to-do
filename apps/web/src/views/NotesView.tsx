import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import Table from "@tiptap/extension-table";
import TableCell from "@tiptap/extension-table-cell";
import TableHeader from "@tiptap/extension-table-header";
import TableRow from "@tiptap/extension-table-row";
import TaskItem from "@tiptap/extension-task-item";
import TaskList from "@tiptap/extension-task-list";
import Typography from "@tiptap/extension-typography";
import { type Editor, EditorContent, useEditor } from "@tiptap/react";
import { NoteAssist } from "../components/NoteAssist";
import { NoteConnections } from "../components/NoteConnections";
import { NoteGraph } from "../components/NoteGraph";
import { refreshWikiLinks, titleKey, WikiLink, type WikiLinkStorage } from "../components/wikilink";
import StarterKit from "@tiptap/starter-kit";
import { motion } from "framer-motion";
import {
  Bold,
  BookOpen,
  Briefcase,
  Code,
  FileText,
  Heading1,
  Heading2,
  History,
  Italic,
  Lightbulb,
  List,
  ListChecks,
  ListOrdered,
  NotebookPen,
  Plus,
  Quote,
  Search,
  Trash2,
  Users,
  Wrench,
  X,
  FolderKanban,
  GraduationCap,
  LayoutTemplate,
  Network,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Markdown } from "tiptap-markdown";
import { toast } from "sonner";
import { EmptyState, Sheet } from "../components/primitives";
import { api } from "../lib/api";
import { startNoteDrag } from "../lib/drop";
import { keys, useNotes, useUpdateNote } from "../lib/queries";
import type { Note, NoteKind, NoteVersion } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { cx, debounce, relativeTime } from "../lib/util";

export const KIND_META: Record<NoteKind, { label: string; icon: LucideIcon }> = {
  general: { label: "Note", icon: FileText },
  journal: { label: "Journal", icon: BookOpen },
  meeting: { label: "Meeting", icon: Users },
  technical: { label: "Technical", icon: Wrench },
  project: { label: "Project", icon: FolderKanban },
  idea: { label: "Idea", icon: Lightbulb },
  learning: { label: "Learning", icon: GraduationCap },
  career_evidence: { label: "Career evidence", icon: Briefcase },
  template: { label: "Template", icon: LayoutTemplate },
};

const GRAPH = "~graph";

/** Open a note by title — or create it, like clicking an unresolved [[link]] in Obsidian. */
function useOpenByTitle() {
  const ui = useUi();
  const qc = useQueryClient();
  return async (title: string) => {
    const titles = qc.getQueryData<{ id: string; title: string }[]>(["note-titles"]) ?? (await api.noteTitles());
    const hit = titles.find((t) => titleKey(t.title) === titleKey(title));
    if (hit) return ui.navigate("notes", hit.id);
    const n = await api.createNote({ title, kind: "general" });
    for (const k of ["notes", "note-titles", "note-graph", "note-connections"]) void qc.invalidateQueries({ queryKey: [k] });
    toast.success(`Created “${title}”`);
    ui.navigate("notes", n.id);
  };
}

export function NotesView({ noteId }: { noteId?: string }) {
  const ui = useUi();
  const qc = useQueryClient();
  const [kind, setKind] = useState<NoteKind | undefined>();
  const [filter, setFilter] = useState("");
  const { data: notes = [] } = useNotes(kind);
  const openByTitle = useOpenByTitle();

  const shown = notes.filter((n) => !filter || n.title.toLowerCase().includes(filter.toLowerCase()));

  const create = async () => {
    const n = await api.createNote({ title: "", kind: kind ?? "general" });
    void qc.invalidateQueries({ queryKey: ["notes"] });
    ui.navigate("notes", n.id);
  };

  return (
    <div className="notes-layout">
      <aside className="notes-sidebar">
        <div className="notes-sidebar-head">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <h1 className="page-title" style={{ fontSize: "1.4286rem" }}>
              Notes
            </h1>
            <div style={{ display: "flex", gap: 4 }}>
              <button className={cx("btn sm", noteId === GRAPH ? "primary" : "ghost")} onClick={() => ui.navigate("notes", GRAPH)} title="Graph of linked notes">
                <Network /> Graph
              </button>
              <TemplateMenu />
              <button className="btn sm primary" onClick={create}>
                <Plus /> New
              </button>
            </div>
          </div>
          <div className="search-input" style={{ maxWidth: "none" }}>
            <Search />
            <input className="input" placeholder="Filter notes" value={filter} onChange={(e) => setFilter(e.target.value)} />
          </div>
        </div>
        <div className="notes-filter" role="group" aria-label="Filter by kind">
          <button className="filter-chip" aria-pressed={!kind} onClick={() => setKind(undefined)}>
            All
          </button>
          {(["idea", "journal", "meeting", "technical", "learning", "career_evidence", "template"] as NoteKind[]).map((k) => {
            const M = KIND_META[k];
            return (
              <button key={k} className="filter-chip" aria-pressed={kind === k} onClick={() => setKind(kind === k ? undefined : k)}>
                <M.icon /> {k === "idea" ? "Ideas" : M.label}
              </button>
            );
          })}
        </div>
        <div className="notes-items">
          {shown.map((n) => {
            const M = KIND_META[n.kind];
            return (
              <button
                key={n.id}
                className={cx("note-item", n.id === noteId && "active")}
                onClick={() => ui.navigate("notes", n.id)}
                draggable
                onDragStart={(e) => startNoteDrag(e, n.id, n.title)}
                title="Drag onto Prompt Book in the sidebar to turn it into a prompt page"
              >
                <span className="n-title">{n.title}</span>
                <span className="n-meta">
                  <M.icon /> {M.label} · {relativeTime(n.updated_at)}
                </span>
              </button>
            );
          })}
          {shown.length === 0 && <div className="faint" style={{ padding: 14, fontSize: "0.9286rem" }}>No notes here yet.</div>}
        </div>
      </aside>
      <div className="editor-wrap">
        {noteId === GRAPH ? (
          <div className="doc graph-page">
            <h1 className="page-title" style={{ fontSize: "1.4rem", marginBottom: 6 }}>
              Graph
            </h1>
            <p className="faint" style={{ marginTop: 0 }}>Every note and the [[links]] between them. Hover to highlight neighbours; click to open; drag to pin, double-click to release.</p>
            <NoteGraph height={620} onOpen={(id, ghost) => (id ? ui.navigate("notes", id) : ghost && void openByTitle(ghost))} />
          </div>
        ) : noteId ? (
          <NoteEditor key={noteId} noteId={noteId} />
        ) : (
          <div style={{ height: "100%", display: "grid", placeItems: "center" }}>
            <EmptyState icon={NotebookPen} title="Your second brain">
              Pick a note on the left or create one. Markdown shortcuts work as you type — <code>#</code> heading, <code>-</code> list, <code>[ ]</code> checklist.
            </EmptyState>
          </div>
        )}
      </div>
    </div>
  );
}

type SaveState = "saved" | "saving" | "dirty" | "error";

function NoteEditor({ noteId }: { noteId: string }) {
  const ui = useUi();
  const qc = useQueryClient();
  const { data: note } = useQuery({ queryKey: keys.note(noteId), queryFn: () => api.note(noteId) });
  const update = useUpdateNote(noteId);
  const [title, setTitle] = useState<string | null>(null);
  const [state, setState] = useState<SaveState>("saved");
  const [historyOpen, setHistoryOpen] = useState(false);
  const pending = useRef<{ title?: string; body?: string }>({});

  const persist = useCallback(
    (snapshot = false) => {
      const changes = pending.current;
      pending.current = {};
      if (!snapshot && changes.title === undefined && changes.body === undefined) return;
      setState("saving");
      update.mutate(
        { ...changes, snapshot },
        {
          onSuccess: () => setState(Object.keys(pending.current).length ? "dirty" : "saved"),
          onError: () => setState("error"),
        },
      );
    },
    [update],
  );
  const autosave = useMemo(() => debounce(() => persist(false), 700), [persist]);

  useEffect(() => {
    const flush = () => autosave.flush();
    window.addEventListener("beforeunload", flush);
    return () => {
      window.removeEventListener("beforeunload", flush);
      flush();
    };
  }, [autosave]);

  const { data: aiStatus } = useQuery({ queryKey: ["ai-status"], queryFn: api.aiStatus, staleTime: 60_000 });
  const { data: titlesData } = useQuery({ queryKey: ["note-titles"], queryFn: api.noteTitles, staleTime: 30_000 });
  const titles = useMemo(() => titlesData ?? [], [titlesData]);
  const openByTitle = useOpenByTitle();
  const openRef = useRef(openByTitle);
  openRef.current = openByTitle;
  const flushRef = useRef(() => autosave.flush());
  flushRef.current = () => autosave.flush();
  const [suggest, setSuggest] = useState<{ query: string; from: number; to: number; left: number; top: number; index: number } | null>(null);
  const editor = useEditor(
    {
      extensions: [
        StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
        Placeholder.configure({ placeholder: "Start writing… use # for headings, - for lists, [ ] for checklists" }),
        TaskList,
        TaskItem.configure({ nested: true }),
        Link.configure({ openOnClick: false, autolink: true }),
        Typography,
        Table.configure({ resizable: false }),
        TableRow,
        TableHeader,
        TableCell,
        Markdown.configure({ html: false, transformPastedText: true, linkify: true }),
        WikiLink,
      ],
      content: note?.body ?? "",
      editable: true,
      onUpdate: ({ editor: ed }) => {
        pending.current.body = (ed.storage as { markdown: { getMarkdown: () => string } }).markdown.getMarkdown();
        setState("dirty");
        autosave();
      },
      onSelectionUpdate: ({ editor: ed }) => {
        // [[ autocomplete: the text typed since the last "[[" on this line
        const { $from, empty } = ed.state.selection;
        const before = empty ? $from.parent.textBetween(0, $from.parentOffset, undefined, "\ufffc") : "";
        const m = /\[\[([^[\]|#\n]{0,60})$/.exec(before);
        if (!m) return setSuggest((s) => (s === null ? s : null));
        const c = ed.view.coordsAtPos($from.pos);
        setSuggest((s) => ({ query: m[1]!, from: $from.pos - m[1]!.length, to: $from.pos, left: c.left, top: c.bottom + 4, index: s && s.query === m[1] ? s.index : 0 }));
      },
    },
    [note?.id],
  );

  // keep [[link]] colours (existing vs. not created yet) and clicks in sync with the note list
  useEffect(() => {
    if (!editor) return;
    const st = (editor.storage as unknown as { wikiLink: WikiLinkStorage }).wikiLink;
    st.known = new Set(titles.map((t) => titleKey(t.title)));
    st.onOpen = (title) => {
      flushRef.current();
      void openRef.current(title);
    };
    refreshWikiLinks(editor as never);
  }, [editor, titles]);

  const matches = suggest
    ? titles
        .filter((t) => t.id !== noteId && t.title.toLowerCase().includes(suggest.query.toLowerCase()))
        .slice(0, 8)
    : [];
  const pick = (title: string) => {
    if (!editor || !suggest) return;
    editor.chain().focus().insertContentAt({ from: suggest.from, to: suggest.to }, `${title}]]`).run();
    setSuggest(null);
  };
  useEffect(() => {
    if (!editor || !suggest) return;
    const options = [...matches.map((m) => m.title), ...(suggest.query.trim() && !matches.some((m) => titleKey(m.title) === titleKey(suggest.query)) ? [suggest.query.trim()] : [])];
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") return setSuggest(null);
      if (!options.length) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        e.stopPropagation();
        setSuggest({ ...suggest, index: (suggest.index + (e.key === "ArrowDown" ? 1 : options.length - 1)) % options.length });
      } else if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        e.stopPropagation();
        pick(options[Math.min(suggest.index, options.length - 1)]!);
      }
    };
    const dom = editor.view.dom;
    dom.addEventListener("keydown", onKey, true);
    return () => dom.removeEventListener("keydown", onKey, true);
  });

  useEffect(() => {
    if (note && title === null) setTitle(note.title === "Untitled" ? "" : note.title);
  }, [note, title]);

  // ⌘S closes the current version window.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        autosave.flush();
        persist(true);
        toast.success("Version saved");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [autosave, persist]);

  if (!note) return <div className="doc faint">Loading…</div>;
  const M = KIND_META[note.kind];

  return (
    <>
      <div className="editor-top">
        <div className="crumbs">
          <M.icon /> {M.label}
          {note.note_date && <span>· {note.note_date}</span>}
        </div>
        {editor && <FormatBar editor={editor} />}
        {editor && (
          <NoteAssist
            editor={editor}
            enabled={!!aiStatus?.enabled}
            saveVersion={async () => {
              autosave.flush();
              await persist(true);
            }}
          />
        )}
        <span className="save-indicator" aria-live="polite">
          <span className="dot" style={{ background: state === "saved" ? "var(--green)" : state === "error" ? "var(--red)" : "var(--orange)" }} />
          {state === "saved" ? `Saved · v${note.version}` : state === "saving" ? "Saving…" : state === "dirty" ? "Editing" : "Save failed"}
        </span>
        <button className="btn sm ghost" onClick={() => setHistoryOpen(true)} title="Version history">
          <History /> History
        </button>
        <button
          className="btn icon sm ghost danger"
          aria-label="Delete note"
          onClick={async () => {
            if (!confirm("Delete this note and its version history?")) return;
            await api.deleteNote(noteId);
            void qc.invalidateQueries({ queryKey: ["notes"] });
            toast(`Deleted “${note.title}”`);
            ui.navigate("notes");
          }}
        >
          <Trash2 />
        </button>
      </div>
      <motion.article className="doc" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
        <input
          className="doc-title"
          value={title ?? ""}
          placeholder="Untitled"
          aria-label="Title"
          onChange={(e) => {
            setTitle(e.target.value);
            pending.current.title = e.target.value || "Untitled";
            setState("dirty");
            autosave();
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              editor?.commands.focus("start");
            }
          }}
        />
        <div className="doc-props">
          <select
            className="prop-select"
            value={note.kind}
            aria-label="Kind"
            onChange={(e) => update.mutate({ kind: e.target.value as NoteKind })}
          >
            {(Object.keys(KIND_META) as NoteKind[]).map((k) => (
              <option key={k} value={k}>
                {KIND_META[k].label}
              </option>
            ))}
          </select>
          {note.tags.map((t) => (
            <span key={t} className="chip accent">
              #{t}
            </span>
          ))}
          <span className="faint" style={{ fontSize: "0.8571rem" }}>
            Edited {relativeTime(note.updated_at)}
          </span>
        </div>
        <EditorContent editor={editor} />
        {suggest && (
          <div className="wiki-suggest" role="listbox" aria-label="Link to a note" style={{ left: suggest.left, top: suggest.top }}>
            {matches.map((t, i) => (
              <button key={t.id} role="option" aria-selected={i === suggest.index} className={cx(i === suggest.index && "on")} onMouseDown={(e) => { e.preventDefault(); pick(t.title); }}>
                {t.title}
              </button>
            ))}
            {suggest.query.trim() && !matches.some((m) => titleKey(m.title) === titleKey(suggest.query)) && (
              <button role="option" aria-selected={suggest.index === matches.length} className={cx("new", suggest.index === matches.length && "on")} onMouseDown={(e) => { e.preventDefault(); pick(suggest.query.trim()); }}>
                + Link to new note “{suggest.query.trim()}”
              </button>
            )}
            {!suggest.query.trim() && matches.length === 0 && <div className="faint">Type a note title…</div>}
          </div>
        )}
        <NoteConnections
          noteId={note.id}
          onOpenNote={(id) => {
            autosave.flush();
            ui.navigate("notes", id);
          }}
          onOpenTitle={(t) => void openByTitle(t)}
          onJumpHeading={(i) => editor?.view.dom.querySelectorAll("h1, h2, h3, h4, h5, h6")[i]?.scrollIntoView({ behavior: "smooth", block: "center" })}
        />
      </motion.article>
      <HistorySheet
        open={historyOpen}
        note={note}
        onClose={() => setHistoryOpen(false)}
        onRestored={(n) => {
          editor?.commands.setContent(n.body);
          setTitle(n.title);
        }}
        beforeRestore={() => autosave.flush()}
      />
    </>
  );
}

function FormatBar({ editor }: { editor: Editor }) {
  const [, force] = useState(0);
  useEffect(() => {
    const f = () => force((x) => x + 1);
    editor.on("transaction", f);
    return () => {
      editor.off("transaction", f);
    };
  }, [editor]);
  const b = (label: string, icon: LucideIcon, active: boolean, run: () => void) => {
    const I = icon;
    return (
      <button key={label} className={cx(active && "on")} aria-label={label} title={label} onMouseDown={(e) => e.preventDefault()} onClick={run}>
        <I />
      </button>
    );
  };
  const c = () => editor.chain().focus();
  return (
    <div className="format-bar" role="toolbar" aria-label="Formatting">
      {b("Heading 1", Heading1, editor.isActive("heading", { level: 1 }), () => c().toggleHeading({ level: 1 }).run())}
      {b("Heading 2", Heading2, editor.isActive("heading", { level: 2 }), () => c().toggleHeading({ level: 2 }).run())}
      {b("Bold", Bold, editor.isActive("bold"), () => c().toggleBold().run())}
      {b("Italic", Italic, editor.isActive("italic"), () => c().toggleItalic().run())}
      {b("Bulleted list", List, editor.isActive("bulletList"), () => c().toggleBulletList().run())}
      {b("Numbered list", ListOrdered, editor.isActive("orderedList"), () => c().toggleOrderedList().run())}
      {b("Checklist", ListChecks, editor.isActive("taskList"), () => c().toggleTaskList().run())}
      {b("Quote", Quote, editor.isActive("blockquote"), () => c().toggleBlockquote().run())}
      {b("Code block", Code, editor.isActive("codeBlock"), () => c().toggleCodeBlock().run())}
    </div>
  );
}

function HistorySheet({
  open,
  note,
  onClose,
  onRestored,
  beforeRestore,
}: {
  open: boolean;
  note: Note;
  onClose: () => void;
  onRestored: (n: Note) => void;
  beforeRestore: () => void;
}) {
  const qc = useQueryClient();
  const { data: versions = [] } = useQuery({ queryKey: keys.versions(note.id), queryFn: () => api.versions(note.id), enabled: open });
  const [selected, setSelected] = useState<NoteVersion | null>(null);
  const current = selected ?? versions[0];

  return (
    <Sheet open={open} onClose={onClose} label="Version history">
      <div className="sheet-head">
        <History size={16} />
        <strong style={{ fontWeight: 600 }}>Version history</strong>
        <span className="faint" style={{ fontSize: "0.8571rem" }}>
          {versions.length} versions · restoring never deletes history
        </span>
        <button className="btn icon ghost" style={{ marginLeft: "auto" }} aria-label="Close" onClick={onClose}>
          <X />
        </button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "180px 1fr", minHeight: 0, flex: 1 }}>
        <div style={{ borderRight: "1px solid var(--border)", overflowY: "auto", padding: 8 }}>
          {versions.map((v) => (
            <button key={v.version} className={cx("note-item", current?.version === v.version && "active")} onClick={() => setSelected(v)}>
              <span className="n-title">Version {v.version}</span>
              <span className="n-meta">{relativeTime(v.created_at)}</span>
            </button>
          ))}
        </div>
        <div style={{ overflowY: "auto", padding: "16px 20px" }}>
          {current && (
            <>
              <h3 style={{ fontSize: "1.2857rem", fontWeight: 650 }}>{current.title}</h3>
              <div className="faint" style={{ fontSize: "0.8571rem", margin: "4px 0 14px" }}>
                {new Date(current.created_at).toLocaleString()}
              </div>
              <pre style={{ whiteSpace: "pre-wrap", fontFamily: "var(--mono)", fontSize: "0.8929rem", lineHeight: 1.6, color: "var(--text-2)" }}>{current.body || "(empty)"}</pre>
              {current.version !== note.version && (
                <button
                  className="btn primary"
                  onClick={async () => {
                    beforeRestore();
                    const n = await api.restoreVersion(note.id, current.version);
                    qc.setQueryData(keys.note(note.id), n);
                    void qc.invalidateQueries({ queryKey: keys.versions(note.id) });
                    void qc.invalidateQueries({ queryKey: ["notes"] });
                    onRestored(n);
                    toast.success(`Restored version ${current.version} as version ${n.version}`);
                    setSelected(null);
                    onClose();
                  }}
                >
                  <History /> Restore as new version
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </Sheet>
  );
}

/** New note from a template (notes of kind “Template”; {{date}}, {{time}}, {{weekday}}, {{title}} are filled in). */
function TemplateMenu() {
  const ui = useUi();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const { data: templates = [] } = useNotes("template");
  return (
    <span style={{ position: "relative" }}>
      <button className="btn sm ghost" aria-expanded={open} title="New note from a template" onClick={() => setOpen((o) => !o)}>
        <LayoutTemplate />
      </button>
      {open && (
        <div className="menu-pop" role="menu" aria-label="Templates" onMouseLeave={() => setOpen(false)}>
          {templates.map((t) => (
            <button
              key={t.id}
              role="menuitem"
              onClick={async () => {
                setOpen(false);
                const name = prompt("Title for the new note", `${t.title.replace(/\s*template$/i, "")} ${new Date().toISOString().slice(0, 10)}`.trim());
                if (name === null) return;
                const n = await api.noteFromTemplate(t.id, name);
                void qc.invalidateQueries({ queryKey: ["notes"] });
                ui.navigate("notes", n.id);
              }}
            >
              {t.title}
            </button>
          ))}
          {templates.length === 0 && (
            <div className="faint" style={{ padding: "6px 8px", fontSize: "0.82rem", maxWidth: 230 }}>
              No templates yet. Set a note’s kind to <b>Template</b>; use {"{{date}}"}, {"{{weekday}}"}, {"{{title}}"} inside.
            </div>
          )}
        </div>
      )}
    </span>
  );
}
