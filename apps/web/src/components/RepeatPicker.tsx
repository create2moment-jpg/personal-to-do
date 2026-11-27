import { useState } from "react";
import { describeRepeat, parseRepeat, type Repeat, toRule, WEEKDAY_SHORT } from "../lib/repeat";
import { cx } from "../lib/util";

type Preset = "none" | "daily" | "weekdays" | "weekly" | "biweekly" | "monthly" | "custom";

function presetOf(r: Repeat | null): Preset {
  if (!r) return "none";
  if (r.freq === "daily" && r.interval === 1) return "daily";
  if (r.freq === "monthly" && r.interval === 1) return "monthly";
  if (r.freq === "weekly" && r.interval === 1 && r.days.join() === "0,1,2,3,4") return "weekdays";
  if (r.freq === "weekly" && r.days.length <= 1 && r.interval === 1) return "weekly";
  if (r.freq === "weekly" && r.days.length <= 1 && r.interval === 2) return "biweekly";
  return "custom";
}

/** Repeat picker for a task. `anchorDay` (0 = Mon) is the day weekly repeats start from. */
export function RepeatPicker({ value, anchorDay, onChange }: { value: string | null; anchorDay: number | null; onChange: (rule: string | null) => void }) {
  const current = parseRepeat(value);
  const [preset, setPreset] = useState<Preset>(presetOf(current));
  const [custom, setCustom] = useState<Repeat>(current ?? { freq: "weekly", interval: 1, days: anchorDay !== null ? [anchorDay] : [] });

  const pick = (p: Preset) => {
    setPreset(p);
    const day = anchorDay !== null ? [anchorDay] : [];
    const rules: Record<Exclude<Preset, "custom">, Repeat | null> = {
      none: null,
      daily: { freq: "daily", interval: 1, days: [] },
      weekdays: { freq: "weekly", interval: 1, days: [0, 1, 2, 3, 4] },
      weekly: { freq: "weekly", interval: 1, days: day },
      biweekly: { freq: "weekly", interval: 2, days: day },
      monthly: { freq: "monthly", interval: 1, days: [] },
    };
    if (p !== "custom") onChange(toRule(rules[p]));
    else onChange(toRule(custom));
  };
  const setC = (next: Repeat) => {
    setCustom(next);
    onChange(toRule(next));
  };

  return (
    <div className="repeat-picker">
      <select className="select" value={preset} onChange={(e) => pick(e.target.value as Preset)} aria-label="Repeats">
        <option value="none">Doesn’t repeat</option>
        <option value="daily">Every day</option>
        <option value="weekdays">Every weekday</option>
        <option value="weekly">Every week{anchorDay !== null ? ` on ${WEEKDAY_SHORT[anchorDay]}` : ""}</option>
        <option value="biweekly">Every 2 weeks</option>
        <option value="monthly">Every month</option>
        <option value="custom">Custom…</option>
      </select>
      {preset === "custom" && (
        <div className="repeat-custom">
          <label className="inline-field">
            Every
            <input className="input" type="number" min={1} max={52} value={custom.interval} aria-label="Repeat every" onChange={(e) => setC({ ...custom, interval: Math.max(1, Number(e.target.value) || 1) })} />
            <select className="select" value={custom.freq} aria-label="Repeat unit" onChange={(e) => setC({ ...custom, freq: e.target.value as Repeat["freq"], days: e.target.value === "weekly" ? custom.days : [] })}>
              <option value="daily">day(s)</option>
              <option value="weekly">week(s)</option>
              <option value="monthly">month(s)</option>
            </select>
          </label>
          {custom.freq === "weekly" && (
            <div className="weekday-picker" role="group" aria-label="Repeat on">
              {WEEKDAY_SHORT.map((d, i) => (
                <button type="button" key={d} aria-pressed={custom.days.includes(i)} className={cx(custom.days.includes(i) && "on")} onClick={() => setC({ ...custom, days: custom.days.includes(i) ? custom.days.filter((x) => x !== i) : [...custom.days, i] })}>
                  {d.slice(0, 2)}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      {value && <span className="faint repeat-help">{describeRepeat(value)} · completing it creates the next one</span>}
    </div>
  );
}
