import { Extension } from "@tiptap/react";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import type { Node as PMNode } from "@tiptap/pm/model";

/** Obsidian-style [[wikilinks]] in the note editor: highlighted, clickable, ghost if missing. */
export const WIKILINK = /\[\[([^[\]\n]+?)\]\]/g;

export const titleKey = (t: string) => t.split(/\s+/).filter(Boolean).join(" ").toLowerCase();

export function splitTarget(inner: string): { target: string; heading: string | null; alias: string | null } {
  const [left, alias] = inner.split("|", 2) as [string, string | undefined];
  const [target, heading] = left.split("#", 2) as [string, string | undefined];
  return { target: target.trim(), heading: heading?.trim() || null, alias: alias?.trim() || null };
}

export interface WikiLinkStorage {
  known: Set<string>; // title keys of existing notes
  onOpen: (title: string, heading: string | null) => void;
}

const key = new PluginKey("wikilink");

function build(doc: PMNode, known: Set<string>): DecorationSet {
  const decos: Decoration[] = [];
  doc.descendants((node, pos) => {
    if (!node.isText || !node.text) return;
    if (node.marks.some((m) => m.type.name === "code")) return;
    for (const m of node.text.matchAll(WIKILINK)) {
      const { target } = splitTarget(m[1]!);
      if (!target) continue;
      const from = pos + m.index!;
      decos.push(
        Decoration.inline(from, from + m[0].length, {
          class: known.has(titleKey(target)) ? "wikilink" : "wikilink ghost",
          "data-target": target,
          title: known.has(titleKey(target)) ? `Open “${target}”` : `“${target}” doesn't exist yet — click to create it`,
        }),
      );
    }
  });
  return DecorationSet.create(doc, decos);
}

export const WikiLink = Extension.create<Record<string, never>, WikiLinkStorage>({
  name: "wikiLink",
  addStorage() {
    return { known: new Set<string>(), onOpen: () => undefined };
  },
  addProseMirrorPlugins() {
    const storage = this.storage;
    return [
      new Plugin({
        key,
        state: {
          init: (_, state) => build(state.doc, storage.known),
          apply: (tr, old) => (tr.docChanged || tr.getMeta(key) ? build(tr.doc, storage.known) : old),
        },
        props: {
          decorations: (state) => key.getState(state) as DecorationSet,
          handleClick: (view, pos, event) => {
            if (event.altKey) return false; // Alt+click: place the cursor to edit the link text
            const found = (key.getState(view.state) as DecorationSet).find(pos, pos);
            const d = found[0];
            if (!d) return false;
            const text = view.state.doc.textBetween(d.from, d.to);
            const inner = text.slice(2, -2);
            const { target, heading } = splitTarget(inner);
            storage.onOpen(target, heading);
            return true;
          },
        },
      }),
    ];
  },
});

/** Re-colour links after the set of existing notes changed. */
export function refreshWikiLinks(editor: { view: { state: { tr: { setMeta: (k: PluginKey, v: boolean) => unknown } }; dispatch: (tr: never) => void } }) {
  const tr = editor.view.state.tr.setMeta(key, true);
  editor.view.dispatch(tr as never);
}
