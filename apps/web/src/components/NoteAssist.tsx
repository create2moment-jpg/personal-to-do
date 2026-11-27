import type { Editor } from "@tiptap/react";
import { AlertTriangle, Loader2, Wand2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { wordDiff } from "../lib/util";
import { Dialog } from "./primitives";

const STYLES: [string, string][] = [
  ["clearer", "Clearer"],
  ["shorter", "Shorter"],
  ["structure", "Add structure"],
  ["grammar", "Fix grammar"],
  ["professional", "More professional"],
];

interface Result {
  original: string;
  text: string;
  style: string;
  model: string;
  new_numbers: string[];
  range: { from: number; to: number } | null; // null = whole note
}

const markdownOf = (editor: Editor) => (editor.storage as { markdown: { getMarkdown: () => string } }).markdown.getMarkdown();

/**
 * Writing assistant for a note: rewrites the selection (or the whole note) with the
 * local model, shows a word-level diff, and applies it only when you accept.
 * Accepting first saves a version, so the previous text is always in History.
 */
export function NoteAssist({ editor, enabled, saveVersion }: { editor: Editor; enabled: boolean; saveVersion: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);

  const run = async (style: string) => {
    setOpen(false);
    const { from, to, empty } = editor.state.selection;
    const range = empty ? null : { from, to };
    const text = range ? editor.state.doc.textBetween(from, to, "\n\n") : markdownOf(editor);
    if (!text.trim()) return toast("Write something first, or select a passage");
    setBusy(style);
    try {
      const r = await api.rewriteNote(text, style);
      if (r.text.trim() === text.trim()) toast("Nothing to change — it already reads well");
      else setResult({ ...r, range });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const accept = async () => {
    if (!result) return;
    await saveVersion(); // the current text stays restorable from History
    const chain = editor.chain().focus();
    if (result.range) chain.insertContentAt(result.range, result.text).run();
    else editor.commands.setContent(result.text, true);
    toast.success("Applied — the previous text is in History");
    setResult(null);
  };

  return (
    <div className="note-assist">
      <button className="btn sm ghost" disabled={!enabled || !!busy} title={enabled ? "Improve the selection, or the whole note" : "Turn on Local AI in Settings"} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {busy ? <Loader2 className="spin" /> : <Wand2 />} Improve
      </button>
      {open && (
        <div className="note-assist-menu" role="menu" aria-label="Improve with AI">
          <div className="section-label">{editor.state.selection.empty ? "Whole note" : "Selected text"}</div>
          {STYLES.map(([k, l]) => (
            <button key={k} role="menuitem" className="menu-item" onClick={() => void run(k)}>
              {l}
            </button>
          ))}
        </div>
      )}
      <Dialog open={!!result} onClose={() => setResult(null)} label="Review the rewrite" width={900}>
        {result && (
          <div className="rewrite-review">
            <h3>Review the rewrite · {STYLES.find(([k]) => k === result.style)?.[1]}</h3>
            {result.new_numbers.length > 0 && (
              <div className="alert-strip" style={{ margin: "0 0 10px" }}>
                <AlertTriangle /> The rewrite contains numbers that weren’t in your text ({result.new_numbers.join(", ")}). Check before accepting.
              </div>
            )}
            <div className="compare">
              <section>
                <div className="section-label">Your text</div>
                <pre>{result.original}</pre>
              </section>
              <section>
                <div className="section-label">Suggestion · changes highlighted</div>
                <pre>
                  {wordDiff(result.original, result.text).map((p, i) =>
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
                {result.model} · accepting saves a version first
              </span>
              <button className="btn ghost" onClick={() => setResult(null)}>
                Discard
              </button>
              <button className="btn primary" onClick={() => void accept()}>
                Accept
              </button>
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
}
