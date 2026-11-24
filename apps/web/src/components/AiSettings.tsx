import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, KeyRound, Loader2, PlugZap, ShieldCheck, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import type { AiTestReport, LlmConfig, LlmPreset } from "../lib/types";
import { cx } from "../lib/util";

const PRESET_LABEL: Record<LlmPreset, string> = {
  llamacpp: "llama.cpp server",
  vllm: "vLLM",
  ollama: "Ollama",
  lmstudio: "LM Studio",
  custom: "Other OpenAI-compatible",
};

/** Settings → Local AI: configure any OpenAI-compatible local server, apply live, test it. */
export function AiSettings() {
  const qc = useQueryClient();
  const { data: state } = useQuery({ queryKey: ["ai-config"], queryFn: api.aiConfig });
  const [form, setForm] = useState<LlmConfig | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState<"apply" | "test" | null>(null);
  const [report, setReport] = useState<AiTestReport | null>(null);

  useEffect(() => {
    if (state && !form) setForm(state.config);
  }, [state, form]);
  if (!state || !form) return null;

  const set = <K extends keyof LlmConfig>(k: K, v: LlmConfig[K]) => setForm({ ...form, [k]: v });
  const dirty = JSON.stringify(form) !== JSON.stringify(state.config) || apiKey !== "";
  const pickPreset = (p: LlmPreset) => setForm({ ...form, preset: p, base_url: state.presets[p] || form.base_url });

  const apply = async (extra: { clear_key?: boolean } = {}) => {
    setBusy("apply");
    try {
      const next = await api.applyAiConfig({ ...form, api_key: apiKey || null, ...extra });
      qc.setQueryData(["ai-config"], next);
      setForm(next.config);
      setApiKey("");
      void qc.invalidateQueries({ queryKey: ["ai-status"] });
      toast.success(next.config.enabled ? "Local AI settings applied" : "Local AI turned off", {
        description: next.config.enabled ? `${next.active.model || "model detected on first use"} · ${next.config.base_url}` : undefined,
      });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(null);
    }
  };
  const test = async () => {
    setBusy("test");
    setReport(null);
    try {
      setReport(await api.testAiConfig({ ...form, api_key: apiKey || null }));
    } catch (e) {
      setReport({ ok: false, model: "", latency_ms: 0, reply: "", error: (e as Error).message, models: [], checks: [] });
    } finally {
      setBusy(null);
    }
  };

  const keyChip = { session: "session key", env: `from $${form.api_key_env}`, none: "no key" }[state.key_source];

  return (
    <section className="card settings-section ai-settings" aria-label="Local AI">
      <div className="ai-head">
        <h3 style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <PlugZap size={16} /> Local AI — LLM provider
        </h3>
        <label className="switch">
          <span>{form.enabled ? "Enabled" : "Off"}</span>
          <input type="checkbox" role="switch" checked={form.enabled} onChange={(e) => set("enabled", e.target.checked)} aria-label="Enable local AI" />
          <i aria-hidden />
        </label>
      </div>
      <p>
        Any OpenAI-compatible server on this machine: the Prompt Book, fact extraction and future assistants use it. Changes apply immediately — no restart.
      </p>

      <div className="preset-row" role="group" aria-label="Server preset">
        {(Object.keys(PRESET_LABEL) as LlmPreset[]).map((p) => (
          <button key={p} className="filter-chip" aria-pressed={form.preset === p} onClick={() => pickPreset(p)}>
            {PRESET_LABEL[p]}
          </button>
        ))}
      </div>

      <div className="ai-grid">
        <label className="ai-field wide">
          <span className="ai-label">Endpoint (base URL)</span>
          <input className="input mono" value={form.base_url} onChange={(e) => set("base_url", e.target.value)} placeholder="http://127.0.0.1:8080/v1" spellCheck={false} />
          <span className="ai-help">…/v1 — requests go to /chat/completions{state.local_only ? " · this machine only" : ""}</span>
        </label>
        <label className="ai-field">
          <span className="ai-label">Model</span>
          <input className="input mono" list="ai-models" value={form.model} onChange={(e) => set("model", e.target.value)} placeholder="empty = the model the server serves" spellCheck={false} />
          <datalist id="ai-models">
            {report?.models.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
          <span className="ai-help">Test connection lists what the server offers.</span>
        </label>

        <label className="ai-field">
          <span className="ai-label">
            API key <span className={cx("chip", state.key_source !== "none" && "green")}>{keyChip}</span>
          </span>
          <div className="input-icon">
            <KeyRound />
            <input className="input" type="password" autoComplete="off" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={state.key_source === "session" ? "•••••••• (set — type to replace)" : "sk-… (leave empty for keyless local servers)"} />
          </div>
          <span className="ai-help">
            Held in server memory for this session only — never written to disk, never returned by the API.
            {state.key_source === "session" && (
              <>
                {" "}
                <button className="link-btn" onClick={() => void apply({ clear_key: true })}>
                  Forget key
                </button>
              </>
            )}
          </span>
        </label>
        <label className="ai-field">
          <span className="ai-label">API key environment variable</span>
          <input className="input mono" value={form.api_key_env} onChange={(e) => set("api_key_env", e.target.value.toUpperCase())} placeholder="e.g. LLAMA_API_KEY" spellCheck={false} />
          <span className="ai-help">Used when no session key is set — persists across restarts.</span>
        </label>

        <label className="ai-field">
          <span className="ai-label">Reasoning effort</span>
          <select className="select" value={form.reasoning_effort} onChange={(e) => set("reasoning_effort", e.target.value as LlmConfig["reasoning_effort"])}>
            <option value="">(not sent)</option>
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
          <span className="ai-help">Only for servers and models that support it.</span>
        </label>
        <label className="ai-field">
          <span className="ai-label">
            Temperature <span className="mono faint">{form.temperature.toFixed(2)}</span>
          </span>
          <input type="range" min={0} max={2} step={0.05} value={form.temperature} onChange={(e) => set("temperature", Number(e.target.value))} aria-label="Temperature" />
          <span className="ai-help">Lower is more predictable; 0.1–0.3 suits rewriting and extraction.</span>
        </label>

        <div className="ai-numbers wide">
          <NumberField label="Max output tokens" value={form.max_tokens} onChange={(v) => set("max_tokens", v)} help="Reasoning models need room to think." />
          <NumberField label="Context limit (tokens)" value={form.context_limit} onChange={(v) => set("context_limit", v)} help="As configured on your server." />
          <NumberField label="Timeout (s)" value={form.timeout_seconds} onChange={(v) => set("timeout_seconds", v)} help="Per request." />
        </div>
      </div>

      <div className="ai-actions">
        <button className="btn primary" disabled={!dirty || busy !== null} onClick={() => void apply()}>
          {busy === "apply" ? <Loader2 className="spin" /> : null} Apply
        </button>
        <button className="btn" disabled={busy !== null} onClick={() => void test()}>
          {busy === "test" ? <Loader2 className="spin" /> : <PlugZap />} Test connection
        </button>
        <span className="ai-active">
          Active: {state.active.provider === "none" ? "off" : <code>{state.active.model || "model detected on first use"}</code>}
          <span className="faint"> · {state.source === "app" ? "saved in the app" : "from .env"}</span>
        </span>
      </div>

      {report && (
        <div className={cx("ai-report", report.ok ? "ok" : "fail")} role="status">
          <div className="ai-report-main">
            {report.ok ? <CheckCircle2 /> : <XCircle />}
            {report.ok ? (
              <span>
                Connected to <code>{report.model}</code> in {report.latency_ms} ms — replied “{report.reply || "…"}”.
              </span>
            ) : (
              <span>{report.error}</span>
            )}
          </div>
          {report.checks.map((c) => (
            <div key={c.name} className="ai-check">
              {c.ok ? <CheckCircle2 /> : <XCircle />} <b>{c.name}</b> <span className="mono">{c.ms} ms</span>
              {c.detail && <span className="faint">{c.detail}</span>}
            </div>
          ))}
          {report.ok && !dirty && <div className="ai-help">These settings are already active.</div>}
          {report.ok && dirty && <div className="ai-help">Looks good — press Apply to use it.</div>}
        </div>
      )}

      <div className="ai-note">
        <ShieldCheck /> Endpoints outside this machine are refused unless <code>PPOS_LLM_ALLOW_REMOTE=true</code> is set for a host you control. There is no cloud fallback.
      </div>
    </section>
  );
}

function NumberField({ label, value, onChange, help }: { label: string; value: number; onChange: (v: number) => void; help: string }) {
  return (
    <label className="ai-field">
      <span className="ai-label">{label}</span>
      <input className="input mono" type="number" min={1} step={1} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <span className="ai-help">{help}</span>
    </label>
  );
}
