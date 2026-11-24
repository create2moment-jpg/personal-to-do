import { motion } from "framer-motion";
import { FlaskConical, Plus, Search, Zap } from "lucide-react";
import { NAV_GROUPS, SETTINGS_ITEM, type NavItem } from "../lib/nav";
import { useState } from "react";
import { type DropTarget, dropProps } from "../lib/drop";
import { useHealth, useTasks, useToday } from "../lib/queries";
import { useUi, type ViewId } from "../lib/ui-store";
import { cx, isoDay } from "../lib/util";
import { Kbd, spring } from "./primitives";

const DROP_TARGETS: Partial<Record<ViewId, DropTarget>> = { today: "today", backlog: "backlog", sprint: "sprint", book: "book" };

export function Sidebar({ view }: { view: ViewId }) {
  const ui = useUi();
  const [over, setOver] = useState<string | null>(null);
  const health = useHealth();
  const today = useToday(isoDay());
  const backlog = useTasks({ status: "backlog", top_level: true });

  const counts: Partial<Record<ViewId, number>> = {
    today: today.data?.tasks.filter((t) => t.parent_id === null && t.status !== "done").length,
    backlog: backlog.data?.length,
  };

  const item = (n: NavItem) => {
    const active = n.id === view;
    const Icon = n.icon;
    const target = DROP_TARGETS[n.id];
    return (
      <button
        key={n.id}
        {...(target ? dropProps(target, (o) => setOver(o ? n.id : null), (pageId) => pageId && ui.navigate("book", pageId)) : {})}
        className={cx("nav-item", active && "active", n.phase && "later", over === n.id && "drop-over")}
        onClick={() => ui.navigate(n.id)}
        title={n.phase ? `Coming in ${n.phase}` : n.shortcut ? `${n.label} · ${n.shortcut}` : n.label}
        aria-current={active ? "page" : undefined}
      >
        {active && <motion.span layoutId="nav-active" className="active-bg" transition={spring} />}
        <Icon />
        <span>{n.label}</span>
        {n.phase ? <span className="soon">Soon</span> : counts[n.id] ? <span className="count">{counts[n.id]}</span> : null}
      </button>
    );
  };

  return (
    <nav className="sidebar" aria-label="Primary">
      <div className="workspace">
        <div className="logo">
          <Zap strokeWidth={2.4} />
        </div>
        <div>
          <div className="workspace-name">Personal OS</div>
          <div className="workspace-sub">{health.data?.demo ? "Demo workspace" : "Local · private"}</div>
        </div>
      </div>

      <button className="search-trigger" onClick={ui.openPalette}>
        <Search />
        <span>Search or jump to…</span>
        <Kbd>⌘K</Kbd>
      </button>

      {NAV_GROUPS.map((g) => (
        <div key={g.label} className="nav-group">
          <div className="section-label">{g.label}</div>
          {g.items.map(item)}
        </div>
      ))}

      <div className="sidebar-foot">
        {health.data?.demo && (
          <div className="demo-badge" title="Synthetic data created with `ppos demo`">
            <FlaskConical /> Demo data — nothing here is real
          </div>
        )}
        {item(SETTINGS_ITEM)}
        <button className="btn primary capture-cta" onClick={() => ui.openCapture()}>
          <Plus /> New capture <Kbd>C</Kbd>
        </button>
      </div>
    </nav>
  );
}
