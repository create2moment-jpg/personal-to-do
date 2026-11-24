import { Check, HardDrive, Keyboard, Monitor, Moon, Palette, ShieldCheck, Sun } from "lucide-react";
import { Keys } from "../components/primitives";
import { useHealth } from "../lib/queries";
import { ACCENTS, type Accent, useAppearance } from "../lib/theme";
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
          <span className="chip">Local AI: Phase 5</span>
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
