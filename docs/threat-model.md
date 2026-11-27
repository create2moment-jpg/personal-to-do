# Threat model (Phase 1)

Scope: a single user running the app on their own machine. Assets, in order of
sensitivity: performance reviews and career evidence (Phase 4+), notes and
journal, tasks and plans, AI histories, backups.

| # | Threat | Mitigation (status) |
|---|---|---|
| T1 | Private data committed to Git and pushed / mirrored to the office repo | Data dir outside repo, enforced at startup ✅; pre-commit + CI guard ✅; `.gitignore` ✅ |
| T2 | Secrets committed (API keys, tokens) | Guard scans for key/token patterns ✅; `.env` ignored, only `.env.example` tracked ✅ |
| T3 | Other local users or processes read the data dir | `0700` dirs, `0600` backups/exports and API token ✅; passphrase-encrypted backups (`ppos backup --encrypt`, AES-256-GCM + scrypt, authenticated chunks) ✅; the live database relies on OS full-disk encryption (recommended) |
| T4 | Network exposure of the API | Binds `127.0.0.1` by default ✅; Docker publishes on loopback only ✅; every `/api` call needs the per-install token (0600 file in the data folder, or `PPOS_API_TOKEN`) ✅; the app's page receives it as an HttpOnly, SameSite=Strict cookie ✅. Still: don't expose to a LAN without TLS in front |
| T5 | Malicious website calls the local API (CSRF / DNS rebinding) | CORS restricted to the dev origins ✅; Host-header allow-list (loopback + `PPOS_ALLOWED_HOSTS`) rejects rebinding with 421 ✅; state-changing calls from a foreign `Origin` refused with 403 ✅; token required (a foreign site can neither read nor send the SameSite=Strict cookie) ✅ |
| T6 | Data loss from an upgrade or bad migration | No implicit migration of existing data ✅; backup before migrate ✅; transactional migrations + tamper detection ✅ |
| T7 | Corrupt or malicious backup archive on restore | Manifest SHA-256 verification ✅; path-traversal / non-regular members rejected ✅; existing data moved aside, never deleted ✅ |
| T8 | Search query injection | User text is tokenised and quoted before FTS5 `MATCH` ✅; all SQL parameterised; dynamic SQL limited to whitelisted column names ✅ |
| T9 | Sensitive content in logs | API logs never include request bodies ✅; an LLM API key entered in Settings is held in server memory only — never stored, exported, returned by the API or written to the audit log; persistent keys come from an environment variable whose *name* is stored ✅ |
| T10 | Telemetry / cloud leakage | No telemetry; no cloud calls at all today ✅ (Phase 3 calendar sync will be the single opt-in exception, T14); cloud LLM fallback off unless explicitly enabled (Phase 5 design) |
| T11 | Malicious or prompt-injecting documents (Phase 4) | Uploads typed by content (magic bytes), size-limited, stored under a hash name (no user-controlled paths), path-escape checks on read ✅; Word files parsed with the standard library only — each XML part size-capped before decompressing (zip bombs) and any DOCTYPE/ENTITY refused (entity expansion) ✅; OCR sends page images only to the configured local model server (same loopback rule as all AI) or runs local Tesseract/Poppler when installed, via argument lists (no shell), in a private 0700 temp folder deleted afterwards, with per-page time limits and a page cap; the OCR language is validated ✅; originals served with `Content-Security-Policy: sandbox` and `nosniff` ✅; document text is rendered as text, search snippets escaped ✅. Design: documents are data, never instructions; AI output is a validated proposal requiring approval (ADR-0004); tools available to agents are allow-listed per workflow |
| T15 | Assistant answers presented as fact | Answers must cite numbered passages from your own records; missing or invalid citations are flagged on the answer ✅; plan proposals are limited to your own task ids and need approval ✅; embeddings are computed by your local model and stored in your database only ✅ |
| T12 | AI fabricates achievements / competencies | Workflows only propose allow-listed actions, each explained from your records, applied through normal services after approval and audited (ADR-0005) ✅; Extracted facts must quote their source passage verbatim or are dropped ✅; facts are proposals until the user accepts them ✅; model + template recorded per fact ✅; career evidence uses accepted facts only, every link is made or confirmed by the user, and coverage is labelled a hypothesis, never a verdict ✅. Design: provenance required on extracted facts; unsupported claims labelled as inference; evaluations measure groundedness |
| T13 | Supply chain (npm / PyPI) | Lockfile for web deps ✅; Python deps pinned with hashes (`requirements.lock`, `--require-hashes` in Docker and CI) ✅; minimal dependency set ✅ |
| T14 | Calendar data (Phase 3): leaking colleagues' data; future live sync | Implemented as **file import only** — no network access, no tokens ✅; attendee lists are not imported, only the organizer's display name ✅; size-limited, parse errors rejected ✅. For a future Graph adapter: opt-in only; read-only `Calendars.Read` scope; single allow-listed host; refresh token / ICS URL in OS keychain (else encrypted), never logged or exported; attendee data local-only, excluded from AI context by default, "forget person" deletion; the tool never writes to Outlook |

Residual risks to accept knowingly for now: the token protects against other
sites and other machines, not against other processes running as you (they
can read the token file — same as your data); no encryption at rest beyond OS
disk encryption.
