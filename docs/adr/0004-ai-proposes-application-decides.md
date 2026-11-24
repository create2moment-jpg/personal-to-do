# ADR-0004: The LLM proposes; deterministic application logic owns state

- Status: accepted (design; implementation from Phase 5)

## Decision

No AI component writes canonical state directly. Every AI capability returns a
schema-validated proposal. Applying a proposal goes through the same
application services as a user action, is recorded in the audit log with
`actor="ai"` plus model/prompt versions, and requires explicit approval unless
that capability is configured as safe automation (for example: tagging a newly
captured idea).

Agents are explicit workflows with a bounded number of steps and declared
inputs/outputs — not open-ended tool loops.

## Why

- A small local model will make mistakes; the cost of a wrong suggestion must
  be one click to reject, not a corrupted history.
- Career evidence and reviews must be trustworthy: fabricated achievements are
  worse than missing ones. Proposals carry source ids, and anything without a
  source is labelled as inference or recommendation.
- Core features must keep working when the model is unavailable or slow.

## Consequences

- Every capability needs: a versioned prompt, input and output JSON schemas,
  regression fixtures and an evaluation (see `prompts/README.md`).
- The UI needs a review surface for proposals (diff view, accept / edit /
  reject); acceptance/edit/rejection rates become an evaluation metric.
