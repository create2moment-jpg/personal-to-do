import { useQuery } from "@tanstack/react-query";
import { BarChart3, Table2 } from "lucide-react";
import { useState } from "react";
import { RankBars, WeekBars, WeekLine, WeekTimeChart, weekLabel } from "../components/charts";
import { EmptyState } from "../components/primitives";
import { api } from "../lib/api";
import type { WeekStat } from "../lib/types";
import { formatMinutes } from "../lib/util";
import { Kpi } from "./WeekView";

const RANGES = [8, 12, 26];

const avg = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
const pct = (v: number | null) => (v === null ? "—" : `${Math.round(v * 100)}%`);

/** Week-by-week trends from your own records. No AI, no external benchmarks. */
export function InsightsView() {
  const [weeks, setWeeks] = useState(12);
  const { data, isLoading } = useQuery({ queryKey: ["trends", weeks], queryFn: () => api.trends(weeks) });
  const ws = data?.weeks ?? [];
  const labels = ws.map((w) => w.week_start);
  const recent = ws.slice(-4);
  const before = ws.slice(-8, -4);
  const perWeek = avg(recent.map((w) => w.tasks_done));
  const perWeekBefore = avg(before.map((w) => w.tasks_done));
  const meet = ws.reduce((a, w) => a + w.meeting_minutes, 0);
  const work = ws.reduce((a, w) => a + w.work_minutes, 0);
  const planned = ws.reduce((a, w) => a + w.planned, 0);
  const plannedDone = ws.reduce((a, w) => a + w.planned_done, 0);
  const withAcc = ws.filter((w) => w.accuracy !== null);
  const accuracy = avg(withAcc.map((w) => w.accuracy!));
  const empty = ws.every((w) => w.tasks_done === 0 && w.meeting_minutes === 0 && w.planned === 0);

  return (
    <div className="page insights-page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Insights</h1>
          <div className="page-sub">Trends from your own tasks and meetings, week by week. Nothing here is compared with anyone else.</div>
        </div>
        <div className="segmented" role="group" aria-label="Range">
          {RANGES.map((r) => (
            <button key={r} aria-pressed={weeks === r} onClick={() => setWeeks(r)}>
              {r} weeks
            </button>
          ))}
        </div>
      </header>

      {!isLoading && empty && (
        <EmptyState icon={BarChart3} title="Not enough history yet">
          Complete tasks, plan your days and log meetings — trends appear here after a week or two.
        </EmptyState>
      )}

      {data && !empty && (
        <>
          <div className="kpis">
            <Kpi
              label="Tasks per week"
              value={perWeek === null ? "—" : String(Math.round(perWeek * 10) / 10)}
              sub={perWeekBefore !== null && perWeek !== null ? `last 4 weeks · ${perWeek >= perWeekBefore ? "up" : "down"} from ${Math.round(perWeekBefore * 10) / 10}` : "last 4 weeks"}
            />
            <Kpi label="Time in meetings" value={work ? `${Math.round((meet / work) * 100)}%` : "—"} sub={`${formatMinutes(meet)} of ${formatMinutes(work)} working time`} warn={work > 0 && meet / work > 0.4} />
            <Kpi label="Planned work done" value={planned ? `${Math.round((plannedDone / planned) * 100)}%` : "—"} sub={`${plannedDone} of ${planned} tasks planned for a day`} />
            <Kpi label="Estimate accuracy" value={pct(accuracy)} sub={withAcc.length ? "time logged ÷ estimate (100% = spot on)" : "log time on tasks to see this"} warn={accuracy !== null && accuracy > 1.3} />
          </div>

          <div className="insights-grid">
            <section className="card panel">
              <h3>Tasks completed per week</h3>
              <div className="chart-sub">Top-level tasks marked done</div>
              <WeekBars
                weeks={labels}
                values={ws.map((w) => w.tasks_done)}
                format={(v) => String(Math.round(v))}
                label="Tasks completed per week"
                tip={(i) => <Tip w={ws[i]!} lines={[`${ws[i]!.tasks_done} tasks done`, `${formatMinutes(ws[i]!.actual_minutes)} logged · ${formatMinutes(ws[i]!.done_estimate)} estimated`]} />}
              />
            </section>
            <section className="card panel">
              <h3>Meetings vs time free for focus</h3>
              <div className="chart-sub">Working hours minus meetings, per week</div>
              <WeekTimeChart weeks={labels} meetings={ws.map((w) => w.meeting_minutes)} focus={ws.map((w) => w.available_minutes)} />
            </section>
            <section className="card panel">
              <h3>Planned work done</h3>
              <div className="chart-sub">Share of tasks scheduled for a day in that week that got done</div>
              <WeekLine
                weeks={labels}
                values={ws.map((w) => w.reliability)}
                label="Share of planned tasks done per week"
                tip={(i) => <Tip w={ws[i]!} lines={ws[i]!.planned ? [`${ws[i]!.planned_done} of ${ws[i]!.planned} planned tasks done`, pct(ws[i]!.reliability)] : ["Nothing planned"]} />}
              />
            </section>
            <section className="card panel">
              <h3>Estimate accuracy</h3>
              <div className="chart-sub">Time logged ÷ estimate, on tasks with both. Above 100% = took longer.</div>
              <WeekLine
                weeks={labels}
                values={ws.map((w) => w.accuracy)}
                label="Estimate accuracy per week"
                reference={{ value: 1, label: "estimate" }}
                tip={(i) => <Tip w={ws[i]!} lines={ws[i]!.accuracy === null ? ["No tasks with both an estimate and logged time"] : [pct(ws[i]!.accuracy)]} />}
              />
            </section>
            <section className="card panel">
              <h3>Work by project</h3>
              <div className="chart-sub">Completed tasks, time logged (or estimated)</div>
              <RankBars items={data.by_project.map(([name, minutes, count]) => ({ name, minutes, count }))} empty="No completed tasks in this range." />
            </section>
            <section className="card panel">
              <h3>Meeting time by topic</h3>
              <div className="chart-sub">Set topics on meetings and calls to see where time goes</div>
              <RankBars items={data.by_topic.map(([name, minutes, count]) => ({ name, minutes, count }))} empty="No meeting topics yet." />
            </section>
          </div>

          <details className="card panel">
            <summary style={{ cursor: "pointer", display: "flex", gap: 6, alignItems: "center" }}>
              <Table2 size={15} /> All numbers as a table
            </summary>
            <table className="insights-table">
              <thead>
                <tr>
                  <th>Week</th>
                  <th>Done</th>
                  <th>Logged</th>
                  <th>Estimated</th>
                  <th>Accuracy</th>
                  <th>Planned done</th>
                  <th>Meetings</th>
                  <th>Free for focus</th>
                </tr>
              </thead>
              <tbody>
                {ws.map((w) => (
                  <tr key={w.week_start}>
                    <td>{weekLabel(w.week_start)}</td>
                    <td>{w.tasks_done}</td>
                    <td>{formatMinutes(w.actual_minutes)}</td>
                    <td>{formatMinutes(w.done_estimate)}</td>
                    <td>{pct(w.accuracy)}</td>
                    <td>{w.planned ? `${w.planned_done}/${w.planned}` : "—"}</td>
                    <td>{formatMinutes(w.meeting_minutes)}</td>
                    <td>{formatMinutes(w.available_minutes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </>
      )}
    </div>
  );
}

function Tip({ w, lines }: { w: WeekStat; lines: string[] }) {
  return (
    <>
      <strong>{weekLabel(w.week_start)}</strong>
      {lines.map((l) => (
        <span key={l}>{l}</span>
      ))}
    </>
  );
}
