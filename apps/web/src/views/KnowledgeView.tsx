import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ExternalLink, FileText, Library, Loader2, RefreshCw, ScanText, Search, ShieldCheck, Trash2, Upload } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { FactsPanel } from "../components/FactsPanel";
import { EmptyState } from "../components/primitives";
import { api } from "../lib/api";
import type { DocChunk, DocStatus, DocumentInfo } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { cx, relativeTime } from "../lib/util";

const KINDS: [string, string][] = [
  ["other", "Other"],
  ["performance_report", "Performance report"],
  ["experience_letter", "Experience letter"],
  ["framework", "Level framework"],
  ["feedback", "Manager feedback"],
  ["technical", "Technical document"],
  ["own_note", "My evidence note"],
];
const KIND_LABEL = Object.fromEntries(KINDS);

const STATUS: Record<DocStatus, { label: string; tone: string }> = {
  queued: { label: "Queued", tone: "" },
  processing: { label: "Processing", tone: "accent" },
  ready: { label: "Ready", tone: "green" },
  needs_ocr: { label: "Needs OCR", tone: "orange" },
  failed: { label: "Failed", tone: "red" },
};

const fmtSize = (b: number) => (b > 1_048_576 ? `${(b / 1_048_576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

export function KnowledgeView({ arg }: { arg?: string }) {
  const ui = useUi();
  const qc = useQueryClient();
  const [docId, chunkId] = (arg ?? "").split("~");
  const { data: docs = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: api.documents,
    // poll only while something is being processed
    refetchInterval: (q) => ((q.state.data ?? []).some((d) => d.status === "queued" || d.status === "processing") ? 1200 : false),
  });
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("other");
  const [over, setOver] = useState(false);
  const { data: hits = [] } = useQuery({ queryKey: ["doc-search", q], queryFn: () => api.searchDocuments(q), enabled: q.trim().length > 1 });
  const fileRef = useRef<HTMLInputElement>(null);
  const selected = docs.find((d) => d.id === docId) ?? (q ? undefined : docs[0]);

  const upload = async (files: FileList | File[]) => {
    for (const f of Array.from(files)) {
      try {
        const r = await api.uploadDocument(f, kind);
        toast[r.duplicate ? "info" : "success"](r.duplicate ? "Already in your library" : "Added — extracting text…", { description: f.name });
        ui.navigate("knowledge", r.document.id);
      } catch (e) {
        toast.error((e as Error).message, { description: f.name });
      }
    }
    void qc.invalidateQueries({ queryKey: ["documents"] });
  };

  return (
    <div
      className={cx("knowledge-layout", over && "drop-over-zone")}
      onDragOver={(e) => {
        if (e.dataTransfer.types.includes("Files")) {
          e.preventDefault();
          setOver(true);
        }
      }}
      onDragLeave={(e) => e.currentTarget === e.target && setOver(false)}
      onDrop={(e) => {
        if (!e.dataTransfer.files.length) return;
        e.preventDefault();
        setOver(false);
        void upload(e.dataTransfer.files);
      }}
    >
      <aside className="notes-sidebar">
        <div className="notes-sidebar-head">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <h1 className="page-title" style={{ fontSize: "1.43rem" }}>
              Knowledge
            </h1>
            <button className="btn sm primary" onClick={() => fileRef.current?.click()}>
              <Upload /> Add
            </button>
          </div>
          <select className="select" value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Document type for uploads">
            {KINDS.map(([v, l]) => (
              <option key={v} value={v}>
                Add as: {l}
              </option>
            ))}
          </select>
          <div className="search-input" style={{ maxWidth: "none" }}>
            <Search />
            <input className="input" placeholder="Search inside documents" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search documents" />
          </div>
          <input ref={fileRef} type="file" hidden multiple accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown" onChange={(e) => e.target.files && void upload(e.target.files).then(() => { if (fileRef.current) fileRef.current.value = ""; })} />
        </div>
        <div className="notes-items">
          {q.trim().length > 1
            ? hits.map((h) => (
                <button key={h.chunk_id} className="note-item" onClick={() => ui.navigate("knowledge", `${h.document_id}~${h.chunk_id}`)}>
                  <span className="n-title">{h.document_title}</span>
                  <span className="n-meta">
                    p. {h.page_start ?? "–"}
                    {h.section && ` · ${h.section}`}
                  </span>
                  <span className="hit-snippet" dangerouslySetInnerHTML={{ __html: highlight(h.snippet) }} />
                </button>
              ))
            : docs.map((d) => <DocRow key={d.id} d={d} active={d.id === selected?.id} onOpen={() => ui.navigate("knowledge", d.id)} />)}
          {q.trim().length > 1 && hits.length === 0 && <div className="faint" style={{ padding: 14, fontSize: "0.93rem" }}>No passages match.</div>}
          {!isLoading && docs.length === 0 && !q && <div className="faint" style={{ padding: 14, fontSize: "0.93rem" }}>No documents yet.</div>}
        </div>
      </aside>
      <div className="editor-wrap">
        {selected ? (
          <DocumentReader key={selected.id} doc={selected} chunkId={chunkId} />
        ) : (
          <div className="page" style={{ maxWidth: "52rem" }}>
            <EmptyState icon={Library} title="Your private library">
              Drop PDFs, text or Markdown files anywhere here — performance reports, level frameworks, feedback, technical docs. Originals are kept untouched in your private data folder; text is extracted per page so every search result cites its page.
            </EmptyState>
            <div className="dropzone" onClick={() => fileRef.current?.click()}>
              <Upload size={22} />
              <div style={{ fontWeight: 600, marginTop: 6 }}>Drop files here or click to choose</div>
              <div className="faint" style={{ fontSize: "0.9rem", marginTop: 4 }}>
                PDF, Word (.docx), .txt, .md · up to 50 MB · processed on this machine
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function highlight(snippet: string): string {
  const esc = snippet.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return esc.replace(/\[/g, "<mark>").replace(/\]/g, "</mark>");
}

function DocRow({ d, active, onOpen }: { d: DocumentInfo; active: boolean; onOpen: () => void }) {
  const s = STATUS[d.status];
  return (
    <button className={cx("note-item", active && "active")} onClick={onOpen}>
      <span className="n-title">{d.title}</span>
      <span className="n-meta">
        <span className={`chip ${s.tone}`} style={{ height: "1.15rem" }}>
          {(d.status === "processing" || d.status === "queued") && <Loader2 className="spin" />}
          {s.label}
        </span>
        {KIND_LABEL[d.kind]} {d.pages ? `· ${d.pages} p.` : ""}
      </span>
    </button>
  );
}

function DocumentReader({ doc, chunkId }: { doc: DocumentInfo; chunkId?: string }) {
  const ui = useUi();
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["document", doc.id, doc.status, doc.processed_at], queryFn: () => api.document(doc.id) });
  const [title, setTitle] = useState(doc.title);
  const target = useRef<HTMLDivElement>(null);
  useEffect(() => {
    target.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [chunkId, data]);
  const byPage = useMemo(() => {
    const m = new Map<number, DocChunk[]>();
    for (const c of data?.chunks ?? []) m.set(c.page_start ?? 0, [...(m.get(c.page_start ?? 0) ?? []), c]);
    return [...m.entries()];
  }, [data]);
  const refresh = () => void qc.invalidateQueries({ queryKey: ["documents"] });

  return (
    <>
      <div className="editor-top">
        <div className="crumbs">
          <FileText /> {KIND_LABEL[doc.kind]}
        </div>
        <span className="save-indicator">
          <span className={`chip ${STATUS[doc.status].tone}`}>{STATUS[doc.status].label}</span>
        </span>
        <a className="btn sm ghost" href={`/api/documents/${doc.id}/file`} target="_blank" rel="noreferrer">
          <ExternalLink /> Original
        </a>
        <button
          className="btn sm ghost"
          title="Extract and index again"
          onClick={async () => {
            await api.reindexDocument(doc.id);
            refresh();
            toast("Re-indexing…");
          }}
        >
          <RefreshCw /> Re-index
        </button>
        <button
          className="btn icon sm ghost danger"
          aria-label="Delete document"
          onClick={async () => {
            if (!confirm(`Delete “${doc.title}” and its original file from your library?`)) return;
            await api.deleteDocument(doc.id);
            refresh();
            ui.navigate("knowledge");
          }}
        >
          <Trash2 />
        </button>
      </div>
      <article className="doc">
        <input
          className="doc-title"
          value={title}
          aria-label="Document title"
          onChange={(e) => setTitle(e.target.value)}
          onBlur={() => title !== doc.title && api.updateDocument(doc.id, { title }).then(refresh)}
        />
        <div className="doc-props">
          <select className="prop-select" value={doc.kind} aria-label="Document type" onChange={(e) => api.updateDocument(doc.id, { kind: e.target.value }).then(refresh)}>
            {KINDS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
          <span className="faint" style={{ fontSize: "0.86rem" }}>
            {doc.filename} · {fmtSize(doc.size_bytes)}
            {doc.pages ? ` · ${doc.pages} pages` : ""} · added {relativeTime(doc.created_at)}
          </span>
        </div>
        <div className="provenance">
          <ShieldCheck size={14} /> SHA-256 <code>{doc.sha256.slice(0, 12)}…</code> · extractor <code>{doc.extractor_version ?? "—"}</code>
          {doc.processed_at && ` · indexed ${relativeTime(doc.processed_at)}`}
        </div>
        {doc.extractor_version?.includes("+ocr(") && doc.status === "ready" && (
          <div className="ocr-note" role="note">
            <ScanText size={14} />{" "}
            {doc.extractor_version.includes("+ocr(vision-") ? "Text transcribed from the scanned pages by your local AI model" : "Text read from the scanned pages by OCR on this machine"} — check quotes against the original before relying on them.
          </div>
        )}
        {doc.error && (
          <div className="alert-strip" style={{ margin: "12px 0" }}>
            <AlertTriangle /> {doc.error}
          </div>
        )}
        {doc.status === "ready" && <FactsPanel doc={doc} />}
        {(doc.status === "queued" || doc.status === "processing") && (
          <div className="faint" style={{ display: "flex", gap: 8, alignItems: "center", margin: "18px 0" }}>
            <Loader2 className="spin" size={16} /> Extracting text and building the index…
          </div>
        )}
        {byPage.map(([page, chunks]) => (
          <section key={page} className="doc-page">
            <div className="doc-page-label">Page {page || "–"}</div>
            {chunks.map((c) => (
              <div key={c.id} ref={c.id === chunkId ? target : undefined} className={cx("doc-chunk", c.id === chunkId && "hit")} id={`chunk-${c.id}`}>
                <ChunkText text={c.text} />
              </div>
            ))}
          </section>
        ))}
      </article>
    </>
  );
}

/** Render passage text; Markdown heading lines become bold headings without the # marks. */
function ChunkText({ text }: { text: string }) {
  return (
    <>
      {text.split("\n\n").map((para, i) => {
        const m = /^#{1,6}\s+(.*)$/.exec(para.trim());
        return m ? (
          <div key={i} className="doc-section">
            {m[1]}
          </div>
        ) : (
          <p key={i}>{para}</p>
        )}
      )}
    </>
  );
}
