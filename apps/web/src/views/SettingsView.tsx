import { useQueryClient } from "@tanstack/react-query";
import { Check, Clock3, HardDrive, Keyboard, Monitor, Moon, Palette, ShieldCheck, Sun } from "lucide-react";
import { useMemo } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import type { WorkspaceSettings } from "../lib/types";
import { formatMinutes, setWorkspaceTimeZone } from "../lib/util";
import { AiSettings } from "../components/AiSettings";
import { DurationInput } from "../components/DurationPicker";
import { Keys } from "../components/primitives";
import { useHealth, useSettings } from "../lib/queries";
import { ACCENTS, type Accent, DARK_PALETTES, type DarkPalette, useAppearance } from "../lib/theme";
import { useUi } from "../lib/ui-store";

export function SettingsView() {
  const [appearance, set] = useAppearance();
  const { data: health } = useHealth();
  const ui = useUi();

  return (
    <div className="page" style={{ maxWidth: 820 }}>
      <header className="page-head">
        <div>
          <h1 className="page-title">Settings</h1>
          <div className="page-sub">Make it yours. Appearance preferences are stored in this browser only.</div>
        </div>
      </header>

      <section className="card settings-section">
        <h3 style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Palette size={16} /> Appearance
        </h3>
        <p>Theme, accent colour and density.</p>
        <div className="setting-row">
          <div>
            <div className="s-label">Theme</div>
            <div className="s-help">Follow the system or pick one.</div>
          </div>
          <div className="segmented" role="group" aria-label="Theme">
            {(
              [
                ["system", "System", Monitor],
                ["light", "Light", Sun],
                ["dark", "Dark", Moon],
              ] as const
            ).map(([v, label, Icon]) => (
              <button key={v} aria-pressed={appearance.theme === v} onClick={() => set({ theme: v })}>
                <Icon /> {label}
              </button>
            ))}
          </div>
        </div>
        <div className="setting-row" style={{ alignItems: "flex-start", flexDirection: "column", gap: 10 }}>
          <div>
            <div className="s-label">Dark palette</div>
            <div className="s-help">Used whenever the dark theme is active. Picking one switches to dark.</div>
          </div>
          <div className="palette-grid" role="group" aria-label="Dark palette">
            {(Object.keys(DARK_PALETTES) as DarkPalette[]).map((d) => {
              const p = DARK_PALETTES[d];
              return (
                <button
                  key={d}
                  className="palette-tile"
                  aria-pressed={appearance.dark === d}
                  aria-label={`${p.label} dark palette`}
                  onClick={() => set({ dark: d, theme: appearance.theme === "light" ? "dark" : appearance.theme })}
                >
                  <span className="palette-preview" style={{ background: p.bg }}>
                    <span style={{ background: p.surface }} />
                    <span style={{ background: p.surface, width: "60%" }} />
                    <i style={{ background: "var(--accent)" }} />
                  </span>
                  <span className="palette-name">
                    {p.label} {appearance.dark === d && <Check size={13} strokeWidth={3} />}
                  </span>
                  <span className="palette-hint">{p.hint}</span>
                </button>
              );
            })}
          </div>
        </div>
        <div className="setting-row">
          <div>
            <div className="s-label">Accent</div>
            <div className="s-help">{ACCENTS[appearance.accent].label}</div>
          </div>
          <div className="swatches" role="group" aria-label="Accent colour">
            {(Object.keys(ACCENTS) as Accent[]).map((a) => (
              <button
                key={a}
                className="swatch"
                style={{ background: ACCENTS[a].swatch, display: "grid", placeItems: "center", color: "#fff" }}
                aria-pressed={appearance.accent === a}
                aria-label={ACCENTS[a].label}
                title={ACCENTS[a].label}
                onClick={() => set({ accent: a })}
              >
                {appearance.accent === a && <Check size={12} strokeWidth={3} />}
              </button>
            ))}
          </div>
        </div>
        <div className="setting-row">
          <div>
            <div className="s-label">Display size</div>
            <div className="s-help">Auto grows text on large, high-resolution monitors (24″–32″). Browser zoom still works.</div>
          </div>
          <div className="segmented" role="group" aria-label="Display size">
            {(
              [
                ["auto", "Auto"],
                ["compact", "S"],
                ["comfortable", "M"],
                ["large", "L"],
                ["xl", "XL"],
              ] as const
            ).map(([v, label]) => (
              <button key={v} aria-pressed={appearance.display === v} onClick={() => set({ display: v })}>
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="setting-row">
          <div>
            <div className="s-label">Celebrations</div>
            <div className="s-help">A short confetti moment for big wins (top 3 done, sprint completed, week reviewed).</div>
          </div>
          <div className="segmented" role="group" aria-label="Celebrations">
            {(
              [
                ["on", "🎉 On"],
                ["subtle", "Subtle"],
                ["off", "Off"],
              ] as const
            ).map(([v, label]) => (
              <button key={v} aria-pressed={appearance.celebrations === v} onClick={() => set({ celebrations: v })}>
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="setting-row">
          <div>
            <div className="s-label">Density</div>
            <div className="s-help">Compact fits more on screen.</div>
          </div>
          <div className="segmented" role="group" aria-label="Density">
            {(["comfortable", "compact"] as const).map((d) => (
              <button key={d} aria-pressed={appearance.density === d} onClick={() => set({ density: d })}>
                {d[0]!.toUpperCase() + d.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </section>

      <WorkSettings />
      <AiSettings />

      <section className="card settings-section">
        <h3 style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <ShieldCheck size={16} /> Privacy & data
        </h3>
        <p>Everything runs on this machine. No telemetry, no cloud calls, no account.</p>
        <div className="setting-row">
          <div>
            <div className="s-label">Workspace</div>
            <div className="s-help">{health?.demo ? "Demo workspace with synthetic data" : "Your private workspace"}</div>
          </div>
          <span className={health?.demo ? "chip orange" : "chip green"}>{health?.demo ? "Demo" : "Private"}</span>
        </div>
        <div className="setting-row" style={{ alignItems: "flex-start", flexDirection: "column" }}>
          <div>
            <div className="s-label" style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <HardDrive size={14} /> Data location
            </div>
            <div className="s-help">Kept outside the source code repository; the app refuses to run otherwise.</div>
          </div>
          <div className="code-line" style={{ width: "100%" }}>{health?.data_dir ?? "…"}</div>
        </div>
        <div className="setting-row" style={{ alignItems: "flex-start", flexDirection: "column", gap: 8 }}>
          <div>
            <div className="s-label">Backup & export</div>
            <div className="s-help">Verified, checksummed archives. Restores never delete your current data.</div>
          </div>
          <div className="code-line" style={{ width: "100%" }}>ppos backup · ppos restore &lt;archive&gt; · ppos export</div>
        </div>
        <div className="setting-row">
          <div>
            <div className="s-label">Version</div>
            <div className="s-help">App {health?.version ?? "…"} · schema v{health?.schema_version ?? "…"}</div>
          </div>
        </div>
      </section>

      <section className="card settings-section">
        <h3 style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Keyboard size={16} /> Keyboard
        </h3>
        <p>Every action is reachable from the keyboard.</p>
        <div className="setting-row">
          <div className="s-label">Command menu</div>
          <Keys combo="⌘ K" />
        </div>
        <div className="setting-row">
          <div className="s-label">Quick capture</div>
          <Keys combo="C" />
        </div>
        <div className="setting-row">
          <div className="s-label">All shortcuts</div>
          <button className="btn sm" onClick={ui.openShortcuts}>
            Show <Keys combo="?" />
          </button>
        </div>
      </section>
    </div>
  );
}

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function WorkSettings() {
  const { data: s } = useSettings();
  const qc = useQueryClient();
  const zones = useMemo(() => {
    try {
      return (Intl as unknown as { supportedValuesOf: (k: string) => string[] }).supportedValuesOf("timeZone");
    } catch {
      return ["Europe/Berlin", "Europe/London", "America/New_York", "Asia/Kolkata", "UTC"];
    }
  }, []);
  if (!s) return null;
  const save = async (changes: Partial<WorkspaceSettings>) => {
    try {
      const updated = await api.updateSettings(changes);
      qc.setQueryData(["settings"], updated);
      setWorkspaceTimeZone(updated.timezone);
      void qc.invalidateQueries();
      toast.success("Settings saved");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <section className="card settings-section">
      <h3 style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <Clock3 size={16} /> Work & time
      </h3>
      <p>Used for “today”, meeting times and automatic capacity (working hours − meetings − buffer).</p>
      <div className="setting-row">
        <div>
          <div className="s-label">Time zone</div>
          <div className="s-help">Default: Central European Time (Europe/Berlin)</div>
        </div>
        <select className="select" style={{ width: 240 }} value={s.timezone} aria-label="Time zone" onChange={(e) => void save({ timezone: e.target.value })}>
          {zones.map((z) => (
            <option key={z} value={z}>
              {z.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>
      <div className="setting-row">
        <div>
          <div className="s-label">Working hours</div>
          <div className="s-help">{formatMinutes(s.work_minutes)} per workday</div>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <input className="input" type="time" style={{ width: 110 }} defaultValue={s.work_start} key={`ws-${s.work_start}`} aria-label="Work starts" onBlur={(e) => e.target.value !== s.work_start && void save({ work_start: e.target.value })} />
          <span className="faint">to</span>
          <input className="input" type="time" style={{ width: 110 }} defaultValue={s.work_end} key={`we-${s.work_end}`} aria-label="Work ends" onBlur={(e) => e.target.value !== s.work_end && void save({ work_end: e.target.value })} />
        </div>
      </div>
      <div className="setting-row">
        <div>
          <div className="s-label">Workdays</div>
          <div className="s-help">Days without working hours have no capacity.</div>
        </div>
        <div className="segmented" role="group" aria-label="Workdays">
          {DAY_NAMES.map((d, i) => (
            <button
              key={d}
              aria-pressed={s.workdays.includes(i)}
              onClick={() => {
                const next = s.workdays.includes(i) ? s.workdays.filter((x) => x !== i) : [...s.workdays, i];
                if (next.length) void save({ workdays: next });
              }}
            >
              {d}
            </button>
          ))}
        </div>
      </div>
      <div className="setting-row">
        <div>
          <div className="s-label">Focus buffer</div>
          <div className="s-help">Kept free for interruptions, email and breaks.</div>
        </div>
        <div className="segmented" role="group" aria-label="Buffer">
          {[0, 10, 15, 20, 30].map((b) => (
            <button key={b} aria-pressed={s.buffer_percent === b} onClick={() => void save({ buffer_percent: b })}>
              {b}%
            </button>
          ))}
        </div>
      </div>
      <div className="setting-row">
        <div>
          <div className="s-label">Tasks without an estimate count as</div>
          <div className="s-help">Used for capacity until you set a task’s own time (click the time on any card). 0 = don’t count them.</div>
        </div>
        <div style={{ width: "8rem" }}>
          <DurationInput
            label="Default task time"
            placeholder="0 = don't count"
            value={s.default_task_minutes || null}
            onSave={(m) => void save({ default_task_minutes: m ?? 0 })}
          />
        </div>
      </div>
      <div className="setting-row">
        <div>
          <div className="s-label">Sprint length</div>
          <div className="s-help">Default for new sprints.</div>
        </div>
        <div className="segmented" role="group" aria-label="Sprint length">
          {[7, 14, 21].map((d) => (
            <button key={d} aria-pressed={s.sprint_length_days === d} onClick={() => void save({ sprint_length_days: d })}>
              {d / 7} week{d > 7 ? "s" : ""}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

