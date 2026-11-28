import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, Link2, ListTree, Network, Unlink } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { cx } from "../lib/util";
import { NoteGraph } from "./NoteGraph";

type Tab = "backlinks" | "unlinked" | "outgoing" | "outline" | "graph";

/** Obsidian-style panel under a note: backlinks, unlinked mentions, outgoing links, outline, local graph. */
export function NoteConnections({ noteId, onOpenNote, onOpenTitle, onJumpHeading }: { noteId: string; onOpenNote: (id: string) => void; onOpenTitle: (title: string) => void; onJumpHeading: (index: number) => void }) {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["note-connections", noteId], queryFn: () => api.noteConnections(noteId) });
  const [tab, setTab] = useState<Tab>("backlinks");
  if (!data) return null;
  const tabs: { id: Tab; label: string; icon: typeof Link2; n?: number }[] = [
    { id: "backlinks", label: "Backlinks", icon: Link2, n: data.backlinks.length },
    { id: "unlinked", label: "Unlinked mentions", icon: Unlink, n: data.unlinked.length },
    { id: "outgoing", label: "Outgoing", icon: ArrowUpRight, n: data.outgoing.length },
    { id: "outline", label: "Outline", icon: ListTree, n: data.outline.length },
    { id: "graph", label: "Local graph", icon: Network },
  ];
  return (
    <section className="connections" aria-label="Linked notes">
      <div className="conn-tabs" role="tablist">
        {tabs.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} className={cx("conn-tab", tab === t.id && "on")} onClick={() => setTab(t.id)}>
            <t.icon size={13} /> {t.label}
            {t.n !== undefined && <span className="conn-n">{t.n}</span>}
          </button>
        ))}
      </div>
      {tab === "backlinks" &&
        (data.backlinks.length === 0 ? (
          <p className="faint">No other note links here yet. Type <code>[[</code> in a note to link to this one.</p>
        ) : (
          <ul className="conn-list">
            {data.backlinks.map((b) => (
              <li key={b.note_id}>
                <button className="link-btn" onClick={() => onOpenNote(b.note_id)}>
                  {b.title}
                </button>
                {b.snippets.map((s, i) => (
                  <div key={i} className="conn-snip">
                    {s}
                  </div>
                ))}
              </li>
            ))}
          </ul>
        ))}
      {tab === "unlinked" &&
        (data.unlinked.length === 0 ? (
          <p className="faint">No plain-text mentions of this note’s title elsewhere.</p>
        ) : (
          <ul className="conn-list">
            {data.unlinked.map((u) => (
              <li key={u.note_id}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <button className="link-btn" onClick={() => onOpenNote(u.note_id)}>
                    {u.title}
                  </button>
                  <span className="faint">{u.count}×</span>
                  <button
                    className="btn sm"
                    style={{ marginLeft: "auto" }}
                    onClick={async () => {
                      try {
                        await api.linkMention(noteId, u.note_id);
                        toast.success(`Linked the mention in “${u.title}”`, { description: "Saved as a new version of that note." });
                        void qc.invalidateQueries({ queryKey: ["note-connections"] });
                        void qc.invalidateQueries({ queryKey: ["note-graph"] });
                      } catch (e) {
                        toast.error((e as Error).message);
                      }
                    }}
                  >
                    <Link2 /> Link
                  </button>
                </div>
                {u.snippets.map((s, i) => (
                  <div key={i} className="conn-snip">
                    {s}
                  </div>
                ))}
              </li>
            ))}
          </ul>
        ))}
      {tab === "outgoing" &&
        (data.outgoing.length === 0 ? (
          <p className="faint">This note doesn’t link anywhere yet.</p>
        ) : (
          <ul className="conn-list">
            {data.outgoing.map((o, i) => (
              <li key={`${o.title}-${i}`}>
                <button className={cx("link-btn", !o.note_id && "ghost-link")} onClick={() => (o.note_id ? onOpenNote(o.note_id) : onOpenTitle(o.title))} title={o.note_id ? "Open" : "Not created yet — click to create it"}>
                  {o.title}
                  {o.heading ? ` › ${o.heading}` : ""}
                </button>
                {!o.note_id && <span className="faint"> · not created yet</span>}
              </li>
            ))}
          </ul>
        ))}
      {tab === "outline" &&
        (data.outline.length === 0 ? (
          <p className="faint">No headings. Start a line with # to add one.</p>
        ) : (
          <ul className="conn-outline">
            {data.outline.map((h, i) => (
              <li key={i} style={{ paddingLeft: (h.level - 1) * 14 }}>
                <button className="link-btn" onClick={() => onJumpHeading(i)}>
                  {h.text}
                </button>
              </li>
            ))}
          </ul>
        ))}
      {tab === "graph" && <NoteGraph focusId={noteId} compact height={300} onOpen={(id, ghost) => (id ? onOpenNote(id) : ghost && onOpenTitle(ghost))} />}
    </section>
  );
}
