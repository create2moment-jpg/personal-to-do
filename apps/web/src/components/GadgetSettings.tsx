import { ArrowDown, ArrowUp, LayoutPanelLeft } from "lucide-react";
import { useEffect, useRef } from "react";
import { DEFAULT_ORDER, GADGETS, type GadgetId, useGadgetPrefs } from "../lib/gadgets";

/** Settings → Gadgets: which gadgets the dock shows, and in what order (this device). */
export function GadgetSettings({ focus }: { focus?: boolean }) {
  const { prefs, save } = useGadgetPrefs();
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    if (focus) ref.current?.scrollIntoView({ block: "start" });
  }, [focus]);
  const move = (g: GadgetId, by: number) => {
    const order = [...prefs.order];
    const i = order.indexOf(g);
    const j = i + by;
    if (j < 0 || j >= order.length) return;
    [order[i], order[j]] = [order[j]!, order[i]!];
    save({ ...prefs, order });
  };
  const toggle = (g: GadgetId) => save({ ...prefs, hidden: prefs.hidden.includes(g) ? prefs.hidden.filter((x) => x !== g) : [...prefs.hidden, g] });
  return (
    <section ref={ref} id="gadgets" className="card settings-section" aria-label="Gadgets">
      <h3 style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <LayoutPanelLeft size={16} /> Gadgets
      </h3>
      <p>The dock on the right of every page. Collapse it to a slim strip with the » button; each page remembers. Stored in this browser only.</p>
      <ul className="gadget-prefs">
        {prefs.order.map((g, i) => {
          const G = GADGETS[g];
          const on = !prefs.hidden.includes(g);
          return (
            <li key={g} className={on ? "" : "off"}>
              <label>
                <input type="checkbox" className="check" checked={on} onChange={() => toggle(g)} aria-label={`Show ${G.label}`} />
                <G.icon size={15} />
                <span>
                  <strong>{G.label}</strong>
                  <span className="faint"> — {G.hint}</span>
                </span>
              </label>
              <button className="btn icon sm ghost" aria-label={`Move ${G.label} up`} disabled={i === 0} onClick={() => move(g, -1)}>
                <ArrowUp />
              </button>
              <button className="btn icon sm ghost" aria-label={`Move ${G.label} down`} disabled={i === prefs.order.length - 1} onClick={() => move(g, 1)}>
                <ArrowDown />
              </button>
            </li>
          );
        })}
      </ul>
      <button className="btn sm ghost" onClick={() => save({ order: DEFAULT_ORDER, hidden: [], collapsed: {} })}>
        Reset to defaults
      </button>
    </section>
  );
}
