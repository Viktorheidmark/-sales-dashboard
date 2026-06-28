"""
AI-native analytics orchestration layer.

This package introduces the canonical multi-stage analytics pipeline behind the
``AI_ORCHESTRATED_ANALYTICS_ENABLED`` feature flag. It is additive: until the
flag is enabled, the existing ``app.services`` chat pipeline remains the source
of behavior. See ``docs/analytics-orchestration-audit.md``.

Stages (target):
    context → planner → validator → executor → verifier → responder → chart_builder

The single source of truth for intent, metric, dimensions, filters, tenant
scope, Period A / Period B, chart intent, and output sections is the
``AnalysisPlan`` produced by the planner and frozen into ``AnalysisResult``.
No downstream stage may silently change those values.
"""

from app.analytics.schemas import (
    AnalysisPlan,
    AnalysisResult,
    ComparisonSpec,
    ConversationAnalysisContext,
    DateRange,
    VerificationResult,
)

__all__ = [
    "AnalysisPlan",
    "AnalysisResult",
    "ComparisonSpec",
    "ConversationAnalysisContext",
    "DateRange",
    "VerificationResult",
]
