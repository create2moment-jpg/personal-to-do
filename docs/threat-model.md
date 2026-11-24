# Threat model (Phase 1)

Scope: a single user running the app on their own machine. Assets, in order of
sensitivity: performance reviews and career evidence (Phase 4+), notes and
journal, tasks and plans, AI histories, backups.

| # | Threat | Mitigation (status) |
|---|---|---|
| T1 | Private data committed to Git and pushed / mirrored to the office repo | Data dir outside repo, enforced at startup ✅; pre-commit + CI guard ✅; `.gitignore` ✅ |
| T2 | Secrets committed (API keys, tokens) | Guard scans for key/token patterns ✅; `.env` ignored, only `.env.example` tracked ✅ |
| T3 | Other local users or processes read the data dir | `0700` dirs, `0600` backups/exports ✅; encryption at rest ⏳ Phase 9 (recommend full-disk encryption meanwhile) |
| T4 | Network exposure of the API | Binds `127.0.0.1` by default ✅; Docker publishes on loopback only ✅; no auth yet ⇒ **do not expose to a LAN** until Phase 9 adds a local token |
| T5 | Malicious website calls the local API (CSRF / DNS rebinding) | CORS restricted to the dev origins ✅; ⏳ Phase 9: Host-header allow-list + per-install token for state-changing calls |
| T6 | Data loss from an upgrade or bad migration | No implicit migration of existing data ✅; backup before migrate ✅; transactional migrations + tamper detection ✅ |
| T7 | Corrupt or malicious backup archive on restore | Manifest SHA-256 verification ✅; path-traversal / non-regular members rejected ✅; existing data moved aside, never deleted ✅ |
| T8 | Search query injection | User text is tokenised and quoted before FTS5 `MATCH` ✅; all SQL parameterised; dynamic SQL limited to whitelisted column names ✅ |
| T9 | Sensitive content in logs | API logs never include request bodies ✅ |
| T10 | Telemetry / cloud leakage | No telemetry; no cloud calls at all today ✅ (Phase 3 calendar sync will be the single opt-in exception, T14); cloud LLM fallback off unless explicitly enabled (Phase 5 design) |
| T11 | Malicious or prompt-injecting documents (Phase 4) | Uploads typed by content (magic bytes), size-limited, stored under a hash name (no user-controlled paths), path-escape checks on read ✅; originals served with `Content-Security-Policy: sandbox` and `nosniff` ✅; document text is rendered as text, search snippets escaped ✅. Design: documents are data, never instructions; AI output is a validated proposal requiring approval (ADR-0004); tools available to agents are allow-listed per workflow |
| T12 | AI fabricates achievements / competencies | Design: provenance required on extracted facts; unsupported claims labelled as inference; evaluations measure groundedness |
| T13 | Supply chain (npm / PyPI) | Lockfile for web deps ✅; minimal dependency set ✅; ⏳ pin Python deps with a lock (uv/pip-tools) in Phase 9 |
| T14 | Calendar data (Phase 3): leaking colleagues' data; future live sync | Implemented as **file import only** — no network access, no tokens ✅; attendee lists are not imported, only the organizer's display name ✅; size-limited, parse errors rejected ✅. For a future Graph adapter: opt-in only; read-only `Calendars.Read` scope; single allow-listed host; refresh token / ICS URL in OS keychain (else encrypted), never logged or exported; attendee data local-only, excluded from AI context by default, "forget person" deletion; the tool never writes to Outlook |

Residual risks to accept knowingly for now: no app-level authentication
(loopback only), no encryption at rest beyond OS disk encryption.
