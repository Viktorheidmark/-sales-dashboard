"""Feature flags for the AI-native analytics orchestration layer.

These flags gate the new pipeline so it can be enabled incrementally and rolled
back instantly. Defaults are conservative: the orchestrator is OFF until the
migration is complete and validated.
"""

from __future__ import annotations

from app.config import settings


def ai_orchestrated_analytics_enabled() -> bool:
    """Master switch for the canonical orchestration pipeline.

    When True, supported capabilities (initially: explicit period comparison)
    are routed through the new planner → validator → executor → verifier →
    responder pipeline. Everything else falls back to the legacy chat path.
    """
    return settings.ai_orchestrated_analytics_enabled


def analytics_debug_trace_enabled() -> bool:
    """Developer-only switch to surface safe operational trace metadata.

    Never expose this in the normal user experience. It only adds resolved
    intent, exact periods, chosen capability, validation status, and verifier
    approval to the response ``analysis_meta`` block.
    """
    return settings.analytics_debug_trace


def analytics_shadow_eval_enabled() -> bool:
    """Run the new planner alongside the legacy path for comparison/logging only.

    Shadow mode never changes the user-facing response; it only logs plan
    differences for evaluation during development.
    """
    return settings.analytics_shadow_eval
