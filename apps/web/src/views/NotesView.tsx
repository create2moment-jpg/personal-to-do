import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { Note, NoteKind, NoteSummary, NoteVersion } from "../types";
import { NOTE_KINDS } from "../types";
import { debounce } from "../util";

interface Props {
  revision: number;
  noteId?: string;
  onSelect: (id: string) => void;
}

const KIND_LABEL = (k: string) => k.replace("_", " ");

export function NotesView({ revision, noteId, onSelect }: Props) {
  const [notes, setNotes] = useState<NoteSummary[]>([]);
  const [kind, setKind] = useState<NoteKind | "">("");
  const [listVersion, setListVersion] = useState(0);

  useEffect(() => {
    api.notes(kind ? { kind } : {}).then(setNotes).catch(() => setNotes([]));
  }, [kind, revision, listVersion]);

  const create = async () => {
    const n = await api.createNote({ title: "Untitled", kind: kind || "general" });
    setListVersion((v) => v + 1);
    onSelect(n.id);
  };

  return (
    <div className="view notes">
      <div className="notes-list">
        <div className="notes-list-head">
          <select value={kind} onChange={(e) => setKind(e.target.value as NoteKind | "")} aria-label="Filter by kind">
            <option value="">All notes</option>
            {NOTE_KINDS.map((k) => (
              <option key={k} value={k}>
                {k === "idea" ? "Ideas inbox" : KIND_LABEL(k)}
              </option>
            ))}
          </select>
          <button className="primary" onClick={create}>
            New
          </button>
        </div>
        <ul>
          {notes.map((n) => (
            <li key={n.id} className={n.id === noteId ? "active" : ""}>
              <button className="note-item" onClick={() => onSelect(n.id)}>
                <span className="note-title">{n.title}</span>
                <span className="hint">
                  {KIND_LABEL(n.kind)} · {new Date(n.updated_at).toLocaleDateString()}
                </span>
              </button>
            </li>
          ))}
          {notes.length === 0 && <li className="empty">No notes yet.</li>}
        </ul>
      </div>
      {noteId ? (
        <NoteEditor key={noteId} noteId={noteId} onSaved={() => setListVersion((v) => v + 1)} />
      ) : (
        <div className="editor empty-editor">Select or create a note.</div>
      )}
    </div>
  );
}

type SaveState = "saved" | "saving" | "dirty" | "error";

function NoteEditor({ noteId, onSaved }: { noteId: string; onSaved: () => void }) {
  const [note, setNote] = useState<Note | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [state, setState] = useState<SaveState>("saved");
  const [versions, setVersions] = useState<NoteVersion[] | null>(null);
  const [preview, setPreview] = useState<NoteVersion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef({ title: "", body: "" });

  useEffect(() => {
    api
      .note(noteId)
      .then((n) => {
        setNote(n);
        setTitle(n.title);
        setBody(n.body);
        latest.current = { title: n.title, body: n.body };
      })
      .catch((e: Error) => setError(e.message));
  }, [noteId]);

  const persist = useCallback(
    async (changes: { title: string; body: string }, snapshot = false) => {
      setState("saving");
      try {
        const n = await api.updateNote(noteId, { ...changes, snapshot });
        setNote(n);
        setState(latest.current.title === changes.title && latest.current.body === changes.body ? "saved" : "dirty");
        onSaved();
      } catch (e) {
        setState("error");
        setError((e as Error).message);
      }
    },
    [noteId, onSaved],
  );

  const autosave = useMemo(() => debounce((c: { title: string; body: string }) => void persist(c), 800), [persist]);

  // Flush pending edits when leaving the note or the page.
  useEffect(() => {
    const flush = () => autosave.flush();
    window.addEventListener("beforeunload", flush);
    return () => {
      window.removeEventListener("beforeunload", flush);
      flush();
    };
  }, [autosave]);

  const change = (t: string, b: string) => {
    setTitle(t);
    setBody(b);
    latest.current = { title: t, body: b };
    setState("dirty");
    autosave({ title: t, body: b });
  };

  if (!note) return <div className="editor">{error ?? "Loading…"}</div>;

  return (
    <div className="editor">
      <div className="editor-head">
        <input className="title-input" value={title} onChange={(e) => change(e.target.value, body)} aria-label="Title" />
        <select
          value={note.kind}
          aria-label="Kind"
          onChange={async (e) => setNote(await api.updateNote(noteId, { kind: e.target.value as NoteKind }))}
        >
          {NOTE_KINDS.map((k) => (
            <option key={k} value={k}>
              {KIND_LABEL(k)}
            </option>
          ))}
        </select>
        <span className={`save-state ${state}`} aria-live="polite">
          {state === "saved" ? `Saved · v${note.version}` : state === "saving" ? "Saving…" : state === "dirty" ? "Editing…" : "Save failed"}
        </span>
        <button
          onClick={() => {
            autosave.flush();
            void persist({ title, body }, true);
          }}
          title="Close the current version and start a new one"
        >
          Save version
        </button>
        <button onClick={async () => setVersions(versions ? null : await api.versions(noteId))}>History</button>
        <button
          className="danger"
          onClick={async () => {
            if (!confirm("Delete this note and its history?")) return;
            await api.deleteNote(noteId);
            window.location.hash = "/notes";
            onSaved();
          }}
        >
          Delete
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="editor-body">
        <textarea
          value={body}
          onChange={(e) => change(title, e.target.value)}
          placeholder="Markdown supported. Autosaves as you type; history is kept."
          aria-label="Note body"
        />
        {versions && (
          <aside className="history">
            <h3>Version history</h3>
            <ul>
              {versions.map((v) => (
                <li key={v.version}>
                  <button className={`link ${preview?.version === v.version ? "active" : ""}`} onClick={() => setPreview(v)}>
                    v{v.version} · {new Date(v.created_at).toLocaleString()}
                  </button>
                </li>
              ))}
            </ul>
            {preview && (
              <div className="version-preview">
                <strong>{preview.title}</strong>
                <pre>{preview.body}</pre>
                <button
                  onClick={async () => {
                    autosave.flush();
                    const n = await api.restoreVersion(noteId, preview.version);
                    setNote(n);
                    setTitle(n.title);
                    setBody(n.body);
                    latest.current = { title: n.title, body: n.body };
                    setVersions(await api.versions(noteId));
                    setPreview(null);
                    onSaved();
                  }}
                >
                  Restore as new version
                </button>
              </div>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}
