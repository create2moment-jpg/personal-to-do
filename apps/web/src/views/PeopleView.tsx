import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, ClipboardList, NotebookPen, Phone, Plus, Search, Star, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { EmptyState } from "../components/primitives";
import { api } from "../lib/api";
import { useUi } from "../lib/ui-store";
import { cx, debounce, formatMinutes, relativeTime } from "../lib/util";

/** People: a page per person — time together, meetings and calls, follow-ups, notes, 1:1 prep. */
export function PeopleView({ personId }: { personId?: string }) {
  const ui = useUi();
  const qc = useQueryClient();
  const { data: people = [] } = useQuery({ queryKey: ["people-overview"], queryFn: api.peopleOverview });
  const [q, setQ] = useState("");
  const shown = people.filter((p) => !q || `${p.name} ${p.role}`.toLowerCase().includes(q.toLowerCase()));
  const selected = personId ?? shown[0]?.id;
  return (
    <div className="people-layout">
      <aside className="people-list">
        <div className="people-head">
          <h1 className="page-title" style={{ fontSize: "1.4rem" }}>
            People
          </h1>
          <button
            className="btn sm primary"
            onClick={async () => {
              const name = prompt("Name");
              if (!name?.trim()) return;
              try {
                const p = await api.addPerson(name.trim());
                void qc.invalidateQueries({ queryKey: ["people-overview"] });
                ui.navigate("people", p.id);
              } catch (e) {
                toast.error((e as Error).message);
              }
            }}
          >
            <Plus /> Add
          </button>
        </div>
        <div className="search-input" style={{ maxWidth: "none", margin: "0 12px 8px" }}>
          <Search />
          <input className="input" placeholder="Find someone" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Find a person" />
        </div>
        <div className="people-items">
          {shown.map((p) => (
            <button key={p.id} className={cx("person-item", p.id === selected && "active")} onClick={() => ui.navigate("people", p.id)}>
              <span className="avatar" aria-hidden>
                {initials(p.name)}
              </span>
              <span className="pi-main">
                <strong>{p.name}</strong>
                <span className="faint">
                  {p.role ? `${p.role} · ` : ""}
                  {p.last_met ? `met ${relativeTime(p.last_met)}` : p.next_meeting ? "meeting soon" : "no meetings yet"}
                </span>
              </span>
              {p.follow_ups > 0 && (
                <span className="chip orange" title="Open follow-ups">
                  {p.follow_ups}
                </span>
              )}
            </button>
          ))}
          {shown.length === 0 && <div className="faint" style={{ padding: 14, fontSize: "0.9rem" }}>People appear here when you log a call or meeting with them — or add someone.</div>}
        </div>
      </aside>
      <section className="person-pane">{selected ? <PersonPage key={selected} id={selected} /> : <EmptyState icon={Users} title="No one yet">Log a call with someone, or add a person.</EmptyState>}</section>
    </div>
  );
}

const initials = (n: string) =>
  n
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");

function PersonPage({ id }: { id: string }) {
  const ui = useUi();
  const qc = useQueryClient();
  const { data: p } = useQuery({ queryKey: ["person", id], queryFn: () => api.person(id) });
  const [points, setPoints] = useState<string | null>(null);
  const save = useMemo(
    () =>
      debounce((changes: { role?: string; talking_points?: string }) => {
        void api.updatePerson(id, changes).then(() => qc.invalidateQueries({ queryKey: ["people-overview"] }));
      }, 600),
    [id, qc],
  );
  useEffect(() => () => save.flush(), [save]);
  useEffect(() => {
    if (p && points === null) setPoints(p.talking_points);
  }, [p, points]);
  if (!p) return <div className="faint" style={{ padding: 24 }}>Loading…</div>;
  return (
    <div className="person-page">
      <header className="person-top">
        <span className="avatar lg" aria-hidden>
          {initials(p.name)}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2>{p.name}</h2>
          <input className="person-role" defaultValue={p.role} placeholder="Role (e.g. Staff engineer, my manager)" aria-label="Role" onChange={(e) => save({ role: e.target.value })} />
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <button className="btn sm" onClick={() => ui.openLogCall({ people: [p.name] })}>
            <Phone /> Log call
          </button>
          <button
            className="btn sm primary"
            onClick={async () => {
              save.flush();
              if (points !== null) await api.updatePerson(id, { talking_points: points }); // latest text first
              const n = await api.prepNote(id);
              void qc.invalidateQueries({ queryKey: ["notes"] });
              toast.success("1:1 prep note created", { action: { label: "Open", onClick: () => ui.navigate("notes", n.id) } });
            }}
            title="A note with talking points, open follow-ups and what you noted last time"
          >
            <ClipboardList /> Prep 1:1
          </button>
        </div>
      </header>
      <div className="person-stats">
        <Stat label="Last 30 days" value={formatMinutes(p.minutes_30d)} />
        <Stat label="Last 90 days" value={`${formatMinutes(p.minutes_90d)} · ${p.meetings_90d}×`} />
        <Stat label="Last met" value={p.last_met ? relativeTime(p.last_met) : "—"} />
        <Stat label="Next" value={p.next_meeting ? new Date(p.next_meeting).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" }) : "—"} />
        {p.avg_rating !== null && <Stat label="Value" value={`${p.avg_rating} / 5`} icon={<Star size={12} />} />}
      </div>
      <div className="person-grid">
        <section className="card person-card">
          <h3>Talking points for next time</h3>
          <textarea
            className="input person-points"
            value={points ?? ""}
            placeholder={"- Feedback on the ADR\n- Ask about the reorg"}
            aria-label="Talking points"
            onChange={(e) => {
              setPoints(e.target.value);
              save({ talking_points: e.target.value });
            }}
          />
        </section>
        <section className="card person-card">
          <h3>Open follow-ups</h3>
          {p.follow_ups.length === 0 ? (
            <p className="faint">No open task mentions {p.name.split(" ")[0]}.</p>
          ) : (
            <ul className="person-list">
              {p.follow_ups.map((t) => (
                <li key={t.id}>
                  <button className="link-btn" onClick={() => ui.openTask(t.id)}>
                    {t.title}
                  </button>
                  <span className="faint"> · {t.status.replace("_", " ")}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card person-card wide">
          <h3>
            <CalendarClock size={15} /> Meetings and calls
          </h3>
          {p.meetings.length === 0 ? (
            <p className="faint">Nothing logged with {p.name.split(" ")[0]} in the last year.</p>
          ) : (
            <ul className="person-meetings">
              {p.meetings.map((m) => (
                <li key={m.id} className={cx(m.upcoming && "upcoming", m.skipped && "skipped")}>
                  <span className="mono">{m.day}</span>
                  <span>
                    {m.kind === "call" ? <Phone size={12} /> : <CalendarClock size={12} />} {m.title}
                    {m.upcoming && <span className="chip accent">upcoming</span>}
                    {m.skipped && <span className="chip">skipped</span>}
                  </span>
                  <span className="faint">{formatMinutes(m.minutes)}</span>
                  {m.note && <span className="pm-note">{m.note}</span>}
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card person-card wide">
          <h3>
            <NotebookPen size={15} /> Notes that mention {p.name.split(" ")[0]}
          </h3>
          {p.notes.length === 0 ? (
            <p className="faint">
              None yet. Write <code>[[{p.name}]]</code> in a note to link it here.
            </p>
          ) : (
            <ul className="person-list">
              {p.notes.map((n) => (
                <li key={n.id}>
                  <button className="link-btn" onClick={() => ui.navigate("notes", n.id)}>
                    {n.title}
                  </button>
                  {n.linked && <span className="chip accent">linked</span>}
                  {n.snippet && <div className="conn-snip">{n.snippet}</div>}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

function Stat({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div className="person-stat">
      <span className="faint">{label}</span>
      <strong>
        {icon} {value}
      </strong>
    </div>
  );
}


