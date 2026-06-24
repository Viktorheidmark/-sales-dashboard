"""AI analysis planner — structured JSON intent extraction via OpenAI."""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any, Optional

from openai import OpenAI

from app.schemas.analysis_plan import AnalysisPlan
from app.services.intent_router import PriorTurnContext

_PLANNER_SYSTEM = """Du är en analysplanerare för Solvigo Sales Intelligence (svensk B2B försäljningsanalys).

Returnera ENDAST giltig JSON enligt AnalysisPlan-schemat. Inga förklaringar utanför JSON.

Regler:
- Tolk svenska tidsuttryck: "i år"/"detta år" = year_to_date, "förra året" = previous_year,
  "senaste 30 dagarna" = rolling_days med days=30, "senaste kvartalet" = rolling_months med days=3,
  "senaste året" = rolling_months med days=12, "över hela perioden" = full_history,
  "senaste veckan" = previous_completed_week.
- Välj intent utifrån affärsfrågan: sales_overview, sales_trend, product_ranking, market_share,
  product_decline, region_ranking, portfolio_change, eller unknown om osäker.
- visualization.primary: line/area för trend, bar_ranked för ranking, bar_compare för periodjämförelse,
  donut för marknadsandel, kpi för ren KPI-översikt.
- Sätt needs_deep_dive=true endast när frågan uttryckligen ber om drivare/förklaringar.
- confidence: 0.0–1.0. clarification_needed=true endast om frågan är omöjlig att tolka.
- Inkludera ALDRIG SQL, verktygsnamn, supplier_id, konkurrentdetaljer eller fri resonemangstext.
"""


def _compact_prior_context(prior: Optional[PriorTurnContext]) -> dict[str, Any]:
    if not prior:
        return {}
    date_range = None
    for source in prior.sources:
        if isinstance(source, dict) and source.get("date_range"):
            date_range = source["date_range"]
            break
    return {
        "prior_question": prior.question,
        "prior_tool_calls": list(prior.tool_calls),
        "prior_has_chart": prior.has_chart,
        "prior_date_range": date_range,
    }


def _planner_user_payload(
    message: str,
    supplier_name: str,
    current_date: str,
    prior: Optional[PriorTurnContext],
) -> str:
    payload = {
        "question": message,
        "supplier_context_name": supplier_name,
        "current_date": current_date,
        "prior_context": _compact_prior_context(prior),
    }
    return json.dumps(payload, ensure_ascii=False)


def call_planner(
    message: str,
    supplier_name: str,
    *,
    current_date: Optional[str] = None,
    prior: Optional[PriorTurnContext] = None,
    client: Optional[OpenAI] = None,
    model: Optional[str] = None,
) -> AnalysisPlan:
    """Call OpenAI planner and return a validated AnalysisPlan."""
    ref_date = current_date or date.today().isoformat()
    api_client = client or OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model_name = model or os.environ.get("OPENAI_MODEL", "gpt-4o")

    schema = AnalysisPlan.model_json_schema()
    response = api_client.chat.completions.create(
        model=model_name,
        temperature=0.0,
        max_tokens=800,
        messages=[
            {"role": "system", "content": _PLANNER_SYSTEM},
            {
                "role": "user",
                "content": _planner_user_payload(message, supplier_name, ref_date, prior),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "analysis_plan",
                "strict": True,
                "schema": schema,
            },
        },
    )
    raw = response.choices[0].message.content or "{}"
    data = json.loads(raw)
    return AnalysisPlan.model_validate(data)
