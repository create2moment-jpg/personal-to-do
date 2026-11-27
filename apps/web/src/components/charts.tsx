import { useEffect, useRef, useState } from "react";
import type { BurndownPoint, DayTime, Ranked } from "../lib/types";
import { formatMinutes } from "../lib/util";

/*
 * Charts follow docs/design-system.md (data-viz rules): validated categorical
 * slots (--series-1 blue = focus / remaining, --series-2 orange = meetings),
 * 2px lines, 4px rounded data ends, 2px surface gaps, legends for ≥2 series,
 * hover tooltips, recessive grid, text in text tokens.
 */

const fmtHours = (m: number) => (m >= 60 ? `${Math.round((m / 60) * 10) / 10}h` : `${m}m`);
const weekday = (iso: string) => new Date(`${iso}T12:00:00Z`).toLocaleDateString(undefined, { weekday: "short", timeZone: "UTC" });

/** Draw at the real pixel width so text stays 11px at any size. */
function useWidth(fallback = 640): [React.RefObject<HTMLDivElement>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => e && setW(Math.max(280, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

function niceMax(v: number): number {
  if (v <= 0) return 60;
  const step = v > 1200 ? 300 : v > 480 ? 120 : 60;
  return Math.ceil(v / step) * step;
}

function Legend({ items }: { items: { label: string; color: string; dashed?: boolean }[] }) {
  return (
    <div className="chart-legend">
      {items.map((i) => (
        <span key={i.label}>
          <i style={i.dashed ? { borderTop: `2px dashed ${i.color}`, background: "none", height: 0 } : { background: i.color }} />
          {i.label}
        </span>
      ))}
    </div>
  );
}

function Tooltip({ x, y, children }: { x: number; y: number; children: React.ReactNode }) {
  return (
    <div className="chart-tip" style={{ left: x, top: y }} role="status">
      {children}
    </div>
  );
}

export function BurndownChart({ points }: { points: BurndownPoint[] }) {
  const [ref, W] = useWidth();
  const H = 220;
  const pad = { l: 40, r: 56, t: 14, b: 26 };
  const [hover, setHover] = useState<number | null>(null);
  if (points.length === 0) return null;
  const max = niceMax(Math.max(...points.map((p) => Math.max(p.ideal_minutes, p.remaining_minutes, p.scope_minutes))));
  const x = (i: number) => pad.l + (i * (W - pad.l - pad.r)) / Math.max(points.length - 1, 1);
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  const actual = points.map((p, i) => ({ p, i })).filter(({ p }) => p.remaining_minutes >= 0);
  const ideal = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.ideal_minutes)}`).join(" ");
  const line = actual.map(({ p, i }, k) => `${k === 0 ? "M" : "L"}${x(i)},${y(p.remaining_minutes)}`).join(" ");
  const ticks = [0, max / 2, max];
  const last = actual[actual.length - 1];
  const hp = hover !== null ? points[hover] : undefined;

  return (
    <div className="chart" ref={ref}>
      <Legend
        items={[
          { label: "Remaining", color: "var(--series-1)" },
          { label: "Ideal", color: "var(--text-3)", dashed: true },
        ]}
      />
      <svg
        width={W}
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Burndown: ${last ? fmtHours(last.p.remaining_minutes) : "0"} remaining`}
        onMouseMove={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          const rel = ((e.clientX - r.left) / r.width) * W;
          const i = Math.round(((rel - pad.l) / (W - pad.l - pad.r)) * (points.length - 1));
          setHover(Math.max(0, Math.min(points.length - 1, i)));
        }}
        onMouseLeave={() => setHover(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} className="grid" />
            <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" className="axis">
              {fmtHours(t)}
            </text>
          </g>
        ))}
        {points.map((p, i) =>
          i % Math.ceil(points.length / Math.max(2, Math.floor(W / 90))) === 0 || i === points.length - 1 ? (
            <text key={p.day} x={x(i)} y={H - 8} textAnchor="middle" className="axis">
              {weekday(p.day)} {Number(p.day.slice(8))}
            </text>
          ) : null,
        )}
        <path d={ideal} fill="none" stroke="var(--text-3)" strokeWidth={2} strokeDasharray="4 4" />
        <path d={line} fill="none" stroke="var(--series-1)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {last && (
          <>
            <circle cx={x(last.i)} cy={y(last.p.remaining_minutes)} r={5} fill="var(--series-1)" stroke="var(--surface)" strokeWidth={2} />
            <text x={x(last.i) + 8} y={y(last.p.remaining_minutes) - 8} className="label">
              {fmtHours(last.p.remaining_minutes)} left
            </text>
          </>
        )}
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={H - pad.b} className="crosshair" />}
      </svg>
      {hp && hover !== null && (
        <Tooltip x={x(hover)} y={8}>
          <strong>{new Date(`${hp.day}T12:00:00Z`).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric", timeZone: "UTC" })}</strong>
          <span>Remaining: {hp.remaining_minutes >= 0 ? formatMinutes(hp.remaining_minutes) : "—"}</span>
          <span>Ideal: {formatMinutes(Math.round(hp.ideal_minutes))}</span>
          <span>Scope: {formatMinutes(hp.scope_minutes)}</span>
        </Tooltip>
      )}
    </div>
  );
}

/** Per-day stacked bars: meetings (bottom) + time left for focus. */
export function DayTimeChart({ days }: { days: DayTime[] }) {
  const [ref, W] = useWidth();
  const [hover, setHover] = useState<number | null>(null);
  const H = 200;
  const pad = { l: 40, r: 8, t: 10, b: 26 };
  const max = niceMax(Math.max(...days.map((d) => Math.max(d.work_minutes, d.meeting_minutes_total))));
  const bw = Math.min(36, ((W - pad.l - pad.r) / days.length) * 0.55);
  const cx = (i: number) => pad.l + ((i + 0.5) * (W - pad.l - pad.r)) / days.length;
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  const base = y(0);
  const hd = hover !== null ? days[hover] : undefined;

  return (
    <div className="chart" ref={ref}>
      <Legend
        items={[
          { label: "Meetings", color: "var(--series-2)" },
          { label: "Free for focus", color: "var(--series-1)" },
        ]}
      />
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Meeting and focus time per day" onMouseLeave={() => setHover(null)}>
        {[0, max / 2, max].map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} className="grid" />
            <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" className="axis">
              {fmtHours(t)}
            </text>
          </g>
        ))}
        {days.map((d, i) => {
          const meet = d.meeting_minutes_total;
          const focus = d.available_minutes;
          const meetTop = y(meet);
          const focusTop = y(meet + focus);
          const x0 = cx(i) - bw / 2;
          return (
            <g key={d.day} onMouseEnter={() => setHover(i)} className={hover === i ? "bar-hover" : undefined}>
              <rect x={cx(i) - bw / 2 - 6} y={pad.t} width={bw + 12} height={H - pad.t - pad.b} fill="transparent" />
              {meet > 0 && <path d={roundedTop(x0, meetTop, bw, base - meetTop, focus > 0 ? 0 : 4)} fill="var(--series-2)" />}
              {focus > 0 && <path d={roundedTop(x0, focusTop, bw, Math.max(meetTop - focusTop - 2, 1), 4)} fill="var(--series-1)" />}
              {(days.length <= 14 || i % Math.ceil(days.length / 10) === 0) && (
                <text x={cx(i)} y={H - 8} textAnchor="middle" className="axis">
                  {days.length <= 7 ? weekday(d.day) : `${Number(d.day.slice(8))}`}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {hd && hover !== null && (
        <Tooltip x={cx(hover)} y={8}>
          <strong>{new Date(`${hd.day}T12:00:00Z`).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric", timeZone: "UTC" })}</strong>
          <span>Meetings: {formatMinutes(hd.meeting_minutes_total)}</span>
          <span>Free for focus: {formatMinutes(hd.available_minutes)}</span>
          <span>Working hours: {formatMinutes(hd.work_minutes)}</span>
        </Tooltip>
      )}
    </div>
  );
}

function roundedTop(x: number, y: number, w: number, h: number, r: number): string {
  if (h <= 0) return "";
  const rr = Math.min(r, h, w / 2);
  return `M${x},${y + h} L${x},${y + rr} Q${x},${y} ${x + rr},${y} L${x + w - rr},${y} Q${x + w},${y} ${x + w},${y + rr} L${x + w},${y + h} Z`;
}

/** Ranked horizontal bars — one series, so no legend; values labelled directly. */
export function RankBars({ items, empty, limit = 8 }: { items: Ranked[]; empty: string; limit?: number }) {
  if (items.length === 0) return <div className="faint" style={{ fontSize: "0.9286rem", padding: "8px 0" }}>{empty}</div>;
  const shown = items.slice(0, limit);
  const max = Math.max(...shown.map((i) => i.minutes), 1);
  return (
    <ul className="rank-bars">
      {shown.map((i) => (
        <li key={i.name} title={`${i.name}: ${formatMinutes(i.minutes)} across ${i.count} meeting(s)`}>
          <span className="rb-name">{i.name}</span>
          <span className="rb-track">
            <i style={{ width: `${(i.minutes / max) * 100}%` }} />
          </span>
          <span className="rb-value">{formatMinutes(i.minutes)}</span>
        </li>
      ))}
      {items.length > limit && <li className="faint" style={{ fontSize: "0.8571rem" }}>+{items.length - limit} more</li>}
    </ul>
  );
}

// ------------------------------------------------------------------ weekly trends

export interface WeekPoint {
  week: string; // Monday, ISO
  label: string; // axis label, e.g. "Nov 23"
}

/** Show every k-th axis label so labels (~52px each) never overlap. */
const labelStep = (n: number, plotWidth: number) => Math.max(1, Math.ceil((n * 52) / Math.max(plotWidth, 1)));

const shortWeek = (iso: string) => new Date(`${iso}T12:00:00Z`).toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
export const weekLabel = (iso: string) => `Week of ${shortWeek(iso)}`;

function niceCount(v: number): number {
  if (v <= 4) return 4;
  const step = v > 40 ? 10 : v > 20 ? 5 : 2;
  return Math.ceil(v / step) * step;
}

/** Single-series weekly bars (no legend; the title names it). */
export function WeekBars({ weeks, values, format, tip, label }: { weeks: string[]; values: number[]; format: (v: number) => string; tip: (i: number) => React.ReactNode; label: string }) {
  const [ref, W] = useWidth();
  const [hover, setHover] = useState<number | null>(null);
  const H = 190;
  const pad = { l: 36, r: 8, t: 14, b: 24 };
  const max = niceCount(Math.max(...values, 0));
  const n = weeks.length;
  const bw = Math.min(30, ((W - pad.l - pad.r) / n) * 0.55);
  const cx = (i: number) => pad.l + ((i + 0.5) * (W - pad.l - pad.r)) / n;
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  const last = values.length - 1;
  return (
    <div className="chart" ref={ref}>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} onMouseLeave={() => setHover(null)}>
        {[0, max / 2, max].map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} className="grid" />
            <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" className="axis">
              {format(t)}
            </text>
          </g>
        ))}
        {values.map((v, i) => (
          <g key={weeks[i]} onMouseEnter={() => setHover(i)} className={hover === i ? "bar-hover" : undefined}>
            <rect x={cx(i) - bw / 2 - 6} y={pad.t} width={bw + 12} height={H - pad.t - pad.b} fill="transparent" />
            {v > 0 && <path d={roundedTop(cx(i) - bw / 2, y(v), bw, y(0) - y(v), 4)} fill="var(--series-1)" />}
            {i === last && v > 0 && (
              <text x={cx(i)} y={y(v) - 5} textAnchor="middle" className="value-label">
                {format(v)}
              </text>
            )}
            {i % labelStep(n, W - pad.l - pad.r) === 0 && (
              <text x={cx(i)} y={H - 7} textAnchor="middle" className="axis">
                {shortWeek(weeks[i]!)}
              </text>
            )}
          </g>
        ))}
      </svg>
      {hover !== null && (
        <Tooltip x={cx(hover)} y={8}>
          {tip(hover)}
        </Tooltip>
      )}
    </div>
  );
}

/** Meetings (bottom) and time free for focus (top) per week, in hours. */
export function WeekTimeChart({ weeks, meetings, focus }: { weeks: string[]; meetings: number[]; focus: number[] }) {
  const [ref, W] = useWidth();
  const [hover, setHover] = useState<number | null>(null);
  const H = 200;
  const pad = { l: 40, r: 8, t: 10, b: 24 };
  const n = weeks.length;
  const max = niceMax(Math.max(...weeks.map((_, i) => meetings[i]! + focus[i]!), 0));
  const bw = Math.min(30, ((W - pad.l - pad.r) / n) * 0.55);
  const cx = (i: number) => pad.l + ((i + 0.5) * (W - pad.l - pad.r)) / n;
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  const base = y(0);
  return (
    <div className="chart" ref={ref}>
      <Legend
        items={[
          { label: "Meetings", color: "var(--series-2)" },
          { label: "Free for focus", color: "var(--series-1)" },
        ]}
      />
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Meeting and focus hours per week" onMouseLeave={() => setHover(null)}>
        {[0, max / 2, max].map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} className="grid" />
            <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" className="axis">
              {fmtHours(t)}
            </text>
          </g>
        ))}
        {weeks.map((w, i) => {
          const m = meetings[i]!;
          const f = focus[i]!;
          const x0 = cx(i) - bw / 2;
          return (
            <g key={w} onMouseEnter={() => setHover(i)} className={hover === i ? "bar-hover" : undefined}>
              <rect x={x0 - 6} y={pad.t} width={bw + 12} height={H - pad.t - pad.b} fill="transparent" />
              {m > 0 && <path d={roundedTop(x0, y(m), bw, base - y(m), f > 0 ? 0 : 4)} fill="var(--series-2)" />}
              {f > 0 && <path d={roundedTop(x0, y(m + f), bw, Math.max(y(m) - y(m + f) - 2, 1), 4)} fill="var(--series-1)" />}
              {i % labelStep(n, W - pad.l - pad.r) === 0 && (
                <text x={cx(i)} y={H - 7} textAnchor="middle" className="axis">
                  {shortWeek(w)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {hover !== null && (
        <Tooltip x={cx(hover)} y={8}>
          <strong>{weekLabel(weeks[hover]!)}</strong>
          <span>Meetings: {formatMinutes(meetings[hover]!)}</span>
          <span>Free for focus: {formatMinutes(focus[hover]!)}</span>
          {meetings[hover]! + focus[hover]! > 0 && <span>Meeting share: {Math.round((meetings[hover]! / (meetings[hover]! + focus[hover]!)) * 100)}%</span>}
        </Tooltip>
      )}
    </div>
  );
}

/** Single-series weekly line of a ratio (shown as %), gaps where there is no data; optional dashed reference. */
export function WeekLine({ weeks, values, label, reference, tip }: { weeks: string[]; values: (number | null)[]; label: string; reference?: { value: number; label: string }; tip: (i: number) => React.ReactNode }) {
  const [ref, W] = useWidth();
  const [hover, setHover] = useState<number | null>(null);
  const H = 190;
  const pad = { l: 40, r: reference ? 64 : 12, t: 14, b: 24 };
  const n = weeks.length;
  const known = values.filter((v): v is number => v !== null);
  const hi = Math.max(1, reference?.value ?? 0, ...known);
  const max = Math.ceil(hi * 4) / 4; // quarter steps of 100%
  const x = (i: number) => pad.l + (n === 1 ? 0.5 : i / (n - 1)) * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  const segments: string[] = [];
  let cur = "";
  values.forEach((v, i) => {
    if (v === null) {
      if (cur) segments.push(cur);
      cur = "";
    } else cur += `${cur ? "L" : "M"}${x(i)},${y(v)}`;
  });
  if (cur) segments.push(cur);
  const pct = (v: number) => `${Math.round(v * 100)}%`;
  return (
    <div className="chart" ref={ref}>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} onMouseLeave={() => setHover(null)}>
        {[0, max / 2, max].map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} className="grid" />
            <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" className="axis">
              {pct(t)}
            </text>
          </g>
        ))}
        {reference && (
          <g>
            <line x1={pad.l} x2={W - pad.r} y1={y(reference.value)} y2={y(reference.value)} className="ref-line" />
            <text x={W - pad.r + 6} y={y(reference.value) + 4} className="axis">
              {reference.label}
            </text>
          </g>
        )}
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={H - pad.b} className="crosshair" />}
        {segments.map((d) => (
          <path key={d} d={d} fill="none" stroke="var(--series-1)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        ))}
        {values.map((v, i) =>
          v === null ? null : <circle key={weeks[i]} cx={x(i)} cy={y(v)} r={hover === i ? 5 : 4} fill="var(--series-1)" stroke="var(--surface)" strokeWidth={2} />,
        )}
        {weeks.map((w, i) => (
          <g key={w}>
            <rect x={x(i) - (W - pad.l - pad.r) / n / 2} y={pad.t} width={(W - pad.l - pad.r) / n} height={H - pad.t - pad.b} fill="transparent" onMouseEnter={() => setHover(i)} />
            {i % labelStep(n, W - pad.l - pad.r) === 0 && (
              <text x={x(i)} y={H - 7} textAnchor="middle" className="axis">
                {shortWeek(w)}
              </text>
            )}
          </g>
        ))}
      </svg>
      {hover !== null && (
        <Tooltip x={x(hover)} y={8}>
          {tip(hover)}
        </Tooltip>
      )}
    </div>
  );
}
