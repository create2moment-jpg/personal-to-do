# ADR-0005: Agentic workflows are bounded, propose-only checklists

- Status: accepted (Phase 10, first slice)

## Decision

A workflow is a fixed sequence of steps in application code (not an open-ended
tool loop). It **reads** the user's records and returns a stored *run*: a
checklist of actions drawn from a closed allow-list (`ACTION_KINDS`:
schedule a task, set weekly objectives, fill the weekly review, link career
evidence, create a gap task, write the evidence-pack note). Nothing changes
until the user ticks the actions to keep and applies them.

Applying runs each kept action through the normal application services, so the
same validation, dependency rules and audit entries apply as for a manual
change. Each action records its own outcome (`applied`, `skipped`,
`failed: reason`); a run can be applied or dismissed once. Proposal and
approval are both written to the audit log.

The local model is used only through existing grounded helpers (the cited
weekly-review draft). Every workflow produces a useful result with AI off.
Workflows run on demand; no scheduler, and no automatic application.

## Why

- Follows ADR-0004: the model may be wrong, so the cost of a bad step is one
  unticked box. A closed action list keeps the blast radius known and testable.
- Planning and career evidence must be explainable: every action says which
  record it comes from (overdue since…, due…, shares words…, similar in meaning…).
- Storing runs makes "what did the assistant suggest, and what did I accept?"
  answerable later.

## Consequences

- New capabilities need a new action kind, an executor that calls an existing
  service, and tests — no generic "call any endpoint" action.
- Scheduled runs or low-risk auto-apply would be a separate, explicit opt-in
  decision (not taken).
