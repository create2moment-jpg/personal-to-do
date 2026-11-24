"""AI layer (Phase 5+): providers (Ollama/vLLM), versioned prompts, context
compilation, retrieval, output validation and bounded workflows.

Contract: this layer only *proposes*. Canonical state changes go through the
application services with ``actor="ai"`` in the audit log and, unless
configured as safe automation, require explicit user approval.
"""
