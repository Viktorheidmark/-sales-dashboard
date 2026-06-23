"""
Grounded AI chat orchestration.

Flow:
  POST /api/chat
    → this module
    → OpenAI tool-calling loop
    → MCP stdio transport (subprocess)
    → mcp_server/server.py
    → query_helpers (parameterised SQL)
    → Neon PostgreSQL

Supplier scope is locked here before any tool argument reaches the MCP server.
The LLM cannot choose or override supplier_id.
Competitor data remains aggregate-only (enforced inside each MCP tool).
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI, OpenAI
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.services.guardrails import classify
from app.services.chart_builder import pick_charts
from app.services.deep_dive_builder import build_deep_dive, build_follow_up_actions
from app.services.intent_router import (
    plan_forced_tools,
    default_category_for_supplier,
    prior_context_from_dict,
    is_diagram_followup_request,
)
from app.services.period_utils import apply_sales_over_time_period_policy
from app.services.currency_format import (
    build_currency_reference_block,
    currency_format_rules_block,
    sanitize_answer_currency,
)
from app.services.response_guidance import (
    executive_writing_rules,
    needs_synthesis_retry,
    sanitize_trend_wording,
    synthesis_suffix,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_BACKEND_ROOT = _PROJECT_ROOT / "backend"
_VENV_PYTHON = _BACKEND_ROOT / ".venv" / "bin" / "python"

_PYTHON = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else sys.executable

ALLOWED_TOOLS = {
    "get_supplier_kpis",
    "get_sales_over_time",
    "get_top_products",
    "get_sales_by_region",
    "get_market_share",
    "get_declining_products",
    "get_revenue_drivers",
}

_PLANNING_RE = re.compile(
    r"(jag kommer att|jag ska |jag tänker |låt mig |kommer att hämta|kommer att kontrollera)",
    re.IGNORECASE,
)

_SYNTHESIS_RETRY_NOTE = (
    "\n\n[Instruktion: Skriv om som färdigt analysresultat. Inga planeringsfraser.]"
)


def _build_system_prompt(current_date: str, supplier_name: str = "") -> str:
    default_cat = default_category_for_supplier(supplier_name) if supplier_name else "Mejeri"
    return f"""Du är en analytisk assistent för Solvigo Sales Intelligence.
Du hjälper leverantörer att förstå sin försäljningsdata baserat uteslutande på data från analytikverktygen.

APPLIKATIONSKONTEXT (injicerad av systemet):
- Dagens datum: {current_date}
- Den aktiva leverantörens kontext är redan inställd av applikationen. Fråga ALDRIG användaren om ett leverantörs-ID eller supplier_id.
- supplier_id injiceras automatiskt av systemet — du behöver inte ange det i dina verktygsanrop.
- Standardkategori för marknadsandelsfrågor utan angiven kategori: {default_cat}

DATUMREGLER — dessa är absoluta:
- Anropa alltid ett verktyg när du svarar på en fråga om försäljning, intäkter, produkter, regioner eller marknadsandel.
- Svara ALDRIG på numeriska försäljningsfrågor utan att först ha anropat ett verktyg och fått ett resultat.
- Det enda giltiga affärsdatumet är det som returneras i verktygsresultatets `date_range`-fält. Uppfinn aldrig egna kalenderperioder eller årtalsreferenser.
- När du rapporterar intäkter, trender eller produktresultat ska du alltid ange den faktiska perioden från `date_range` i svaret (t.ex. "under perioden 2026-03-23 till 2026-06-21").
- Om verktygsresultatet innehåller `analysis_note`, följ den vid trend- och jämförelsebedömningar.

Regler du alltid måste följa:
- Svara alltid på svenska, kortfattat och affärsinriktat.
- Hitta aldrig på siffror. Gör endast påståenden som stöds av verktygsresultat.
- Om data saknas eller frågan inte kan besvaras med tillgängliga verktyg, säg det tydligt.
- Avslöja aldrig konkurrentdata på produkt-, kund- eller ordernivå. Konkurrentdata är alltid aggregerad.
- Föreslå endast nästa steg som direkt stöds av verktygsdata — inga generiska marknadsförings- eller prisråd utan datastöd.
- Skriv slutsvaret direkt. Beskriv ALDRIG vad du kommer att göra, hämta eller kontrollera.
- Håll svar under 90 ord om inte användaren uttryckligen ber om mer detaljer.
{executive_writing_rules(supplier_name)}
"""


def _server_params() -> StdioServerParameters:
    env = {**os.environ, "PYTHONPATH": str(_BACKEND_ROOT)}
    return StdioServerParameters(
        command=_PYTHON,
        args=["-m", "mcp_server.server"],
        env={k: v for k, v in env.items() if isinstance(v, str)},
        cwd=str(_PROJECT_ROOT),
    )


def _to_openai_tool(mcp_tool) -> dict:
    import copy
    raw = mcp_tool.inputSchema or {"type": "object", "properties": {}}
    schema = copy.deepcopy(raw)
    schema.setdefault("properties", {}).pop("supplier_id", None)
    if isinstance(schema.get("required"), list):
        schema["required"] = [f for f in schema["required"] if f != "supplier_id"]
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description or "",
            "parameters": schema,
        },
    }


def _inject_supplier_scope(tool_name: str, args: dict, supplier_id: str) -> dict:
    locked = dict(args)
    if "supplier_id" in locked or tool_name in ALLOWED_TOOLS:
        locked["supplier_id"] = supplier_id
    return locked


def _date_hint(start_date: Optional[str], end_date: Optional[str], current_date: str) -> str:
    if start_date or end_date:
        return f"\n[Datumfilter aktivt: {start_date or 'äldsta data'} → {end_date or current_date}]"
    return (
        "\n[Inget datumfilter — verktyget använder sitt standardfönster. "
        "Rapportera den faktiska perioden från date_range i svaret.]"
    )


def _parse_mcp_result(result) -> dict:
    if result.content and hasattr(result.content[0], "text"):
        raw_text = result.content[0].text
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            return {"raw": raw_text}
    return {}


def _record_tool_result(
    tool_name: str,
    parsed: dict,
    supplier_id: str,
    tools_used: list[str],
    sources: list[dict],
    limitations: list[str],
    raw_tool_results: list[tuple[str, dict]],
) -> None:
    tools_used.append(tool_name)
    if not isinstance(parsed, dict):
        return
    if tool_name == "get_sales_over_time":
        parsed = apply_sales_over_time_period_policy(parsed)
    raw_source = parsed.get("source", "")
    sources.append({
        "tool": tool_name,
        "source": raw_source if raw_source.startswith("MCP:") else f"MCP:{tool_name}",
        "supplier_id": supplier_id,
        "generated_at": parsed.get("generated_at", datetime.now(tz=timezone.utc).isoformat()),
        "row_count": parsed.get("row_count"),
        "date_range": parsed.get("date_range"),
        "limitations": parsed.get("limitations", []),
    })
    if parsed.get("limitations"):
        limitations.extend(parsed["limitations"])
    raw_tool_results.append((tool_name, parsed))


def _strip_internal_tool_args(args: dict) -> dict:
    return {k: v for k, v in args.items() if not str(k).startswith("_")}


def _enrich_planned_tool_result(tool_name: str, parsed: dict, plan_args: dict) -> dict:
    if not isinstance(parsed, dict):
        return parsed
    for key in ("_deep_dive_focus", "_chart_intent", "_force_time_series"):
        if plan_args.get(key) is not None:
            parsed[key] = plan_args[key]
    if tool_name == "get_sales_over_time":
        parsed = _enrich_sales_over_time_result(parsed, plan_args)
    return parsed


def _enrich_sales_over_time_result(parsed: dict, plan_args: dict) -> dict:
    if not isinstance(parsed, dict):
        return parsed
    mcp_start = plan_args.get("start_date")
    mcp_end = plan_args.get("end_date")
    if mcp_start and mcp_end:
        qdr: dict = {"start": mcp_start, "end": mcp_end}
        if plan_args.get("_requested_start_date"):
            qdr["requested_start"] = plan_args["_requested_start_date"]
        parsed["query_date_range"] = qdr
        parsed["analysis_reference_date"] = plan_args.get("_analysis_reference_end") or mcp_end
    if plan_args.get("_chart_context_widened"):
        parsed["chart_context"] = {
            "widened": True,
            "lookback_weeks": plan_args.get("_chart_lookback_weeks", 8),
            "original_date_range": plan_args.get("_original_date_range") or {},
        }
    if plan_args.get("_suppress_chart"):
        parsed["suppress_chart"] = True
    return parsed


async def _invoke_mcp_tool(
    session: ClientSession,
    tool_name: str,
    raw_args: dict,
    supplier_id: str,
    start_date: Optional[str],
    end_date: Optional[str],
) -> dict:
    if tool_name not in ALLOWED_TOOLS:
        return {"error": f"Tool '{tool_name}' is not permitted."}
    args = _inject_supplier_scope(tool_name, _strip_internal_tool_args(raw_args), supplier_id)
    if start_date and "start_date" not in args:
        args["start_date"] = start_date
    if end_date and "end_date" not in args:
        args["end_date"] = end_date
    result = await session.call_tool(tool_name, args)
    return _parse_mcp_result(result)


async def _execute_planned_tools(
    session: ClientSession,
    plans,
    supplier_id: str,
    start_date: Optional[str],
    end_date: Optional[str],
    tools_used: list[str],
    sources: list[dict],
    limitations: list[str],
    raw_tool_results: list[tuple[str, dict]],
) -> None:
    for plan in plans:
        if plan.tool_name in tools_used:
            continue
        parsed = await _invoke_mcp_tool(
            session, plan.tool_name, plan.args, supplier_id, start_date, end_date,
        )
        parsed = _enrich_planned_tool_result(plan.tool_name, parsed, plan.args)
        _record_tool_result(
            plan.tool_name, parsed, supplier_id,
            tools_used, sources, limitations, raw_tool_results,
        )


def _diagram_clarification_response(supplier_id: str) -> dict:
    return {
        "answer": (
            "Vad vill du se i diagrammet? Till exempel marknadsandel, topprodukter i en region, "
            "produkter i nedgång eller försäljningstrend — så kan jag visa rätt visualisering."
        ),
        "tool_calls": [],
        "sources": [],
        "chart": None,
        "charts": [],
        "deep_dive": None,
        "follow_up_actions": [],
        "limitations": [],
        "supplier_id": supplier_id,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def _diagram_already_shown_response(supplier_id: str) -> dict:
    return {
        "answer": "Diagrammet visas redan ovan.",
        "tool_calls": [],
        "sources": [],
        "chart": None,
        "charts": [],
        "deep_dive": None,
        "follow_up_actions": [],
        "limitations": [],
        "supplier_id": supplier_id,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def _tool_context_message(
    question: str,
    raw_tool_results: list[tuple[str, dict]],
    supplier_name: str = "",
    tools_used: list[str] | None = None,
) -> dict:
    payload = {name: result for name, result in raw_tool_results}
    tool_list = tools_used or [name for name, _ in raw_tool_results]
    return {
        "role": "user",
        "content": (
            "Följande verktygsresultat är hämtade och ska användas för slutsvar. "
            "Svara direkt på frågan på svenska med dessa siffror.\n\n"
            f"Fråga: {question}\n\n"
            f"Verktygsresultat:\n{json.dumps(payload, ensure_ascii=False)}"
            f"{build_currency_reference_block(raw_tool_results)}"
            f"{currency_format_rules_block()}"
            f"{synthesis_suffix(supplier_name, question, tool_list)}"
        ),
    }


def _looks_like_planning(answer: str) -> bool:
    return bool(answer) and bool(_PLANNING_RE.search(answer))


def _synthesis_retry_message(supplier_name: str, question: str, tools_used: list[str]) -> dict:
    return {
        "role": "user",
        "content": (
            "Skriv om svaret som ett färdigt analysresultat baserat på verktygsdata. "
            "Inga planeringsfraser, inga generiska rekommendationer och inga felaktiga produktnamn "
            "(sätt aldrig leverantörsnamnet framför product_name). "
            "Använd korrekt valutaenhet: under 1 mkr SEK som tkr, inte mkr."
            + synthesis_suffix(supplier_name, question, tools_used)
            + _SYNTHESIS_RETRY_NOTE
        ),
    }


async def _finalize_answer(
    client: OpenAI,
    model: str,
    messages: list[dict],
    *,
    supplier_name: str,
    question: str,
    tools_used: list[str],
    raw_tool_results: list[tuple[str, dict]],
) -> str:
    answer = await _synthesize_sync(client, model, messages)
    if tools_used and (
        _looks_like_planning(answer)
        or needs_synthesis_retry(answer, supplier_name, tools_used, raw_tool_results)
    ):
        messages.append(_synthesis_retry_message(supplier_name, question, tools_used))
        answer = await _synthesize_sync(client, model, messages)
    if not answer.strip():
        answer = "Jag kunde inte generera ett svar. Försök igen."
    return answer


def _guardrail_response(guard, supplier_id: str) -> dict:
    return {
        "answer": guard.answer,
        "tool_calls": [],
        "sources": [],
        "chart": None,
        "charts": [],
        "deep_dive": None,
        "follow_up_actions": [],
        "limitations": guard.limitations,
        "supplier_id": supplier_id,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def _final_payload(
    answer: str,
    tools_used: list[str],
    sources: list[dict],
    raw_tool_results: list[tuple[str, dict]],
    limitations: list[str],
    supplier_id: str,
    question: str = "",
) -> dict:
    cleaned_answer = sanitize_answer_currency(answer, raw_tool_results)
    cleaned_answer = sanitize_trend_wording(cleaned_answer, raw_tool_results)
    all_charts = pick_charts(raw_tool_results, question)
    deep_dive = build_deep_dive(raw_tool_results)
    follow_ups = build_follow_up_actions(deep_dive, "")
    return {
        "answer": cleaned_answer,
        "tool_calls": list(dict.fromkeys(tools_used)),
        "sources": sources,
        "chart": all_charts[0] if all_charts else None,
        "charts": all_charts[1:] if len(all_charts) > 1 else [],
        "deep_dive": deep_dive,
        "follow_up_actions": follow_ups,
        "limitations": list(set(limitations)),
        "supplier_id": supplier_id,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


async def _llm_tool_round(
    session: ClientSession,
    client,
    *,
    async_client: Optional[AsyncOpenAI],
    model: str,
    messages: list[dict],
    openai_tools: list[dict],
    supplier_id: str,
    start_date: Optional[str],
    end_date: Optional[str],
    tools_used: list[str],
    sources: list[dict],
    limitations: list[str],
    raw_tool_results: list[tuple[str, dict]],
    max_rounds: int,
) -> None:
    for _ in range(max_rounds):
        if async_client is not None:
            response = await async_client.chat.completions.create(
                model=model,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=1024,
            )
        else:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=1024,
            )

        choice = response.choices[0]
        msg = choice.message

        if choice.finish_reason == "stop" or not msg.tool_calls:
            if msg.content and not tools_used:
                messages.append({"role": "assistant", "content": msg.content})
            break

        messages.append(msg.model_dump(exclude_none=True))
        tool_results_messages = []

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            try:
                raw_args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                raw_args = {}

            try:
                parsed = await _invoke_mcp_tool(
                    session, tool_name, raw_args, supplier_id, start_date, end_date,
                )
            except Exception as exc:
                parsed = {"error": str(exc)}

            if "error" not in parsed:
                _record_tool_result(
                    tool_name, parsed, supplier_id,
                    tools_used, sources, limitations, raw_tool_results,
                )

            tool_results_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(parsed, ensure_ascii=False),
            })

        messages.extend(tool_results_messages)


async def _synthesize_sync(client: OpenAI, model: str, messages: list[dict]) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
        max_tokens=1024,
    )
    return response.choices[0].message.content or ""


async def run_chat(
    message: str,
    supplier_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    supplier_name: str = "",
    prior_context: Optional[dict] = None,
) -> dict:
    guard = classify(message)
    if not guard.should_call_llm:
        return _guardrail_response(guard, supplier_id)

    prior = prior_context_from_dict(prior_context)
    if is_diagram_followup_request(message) and not prior:
        return _diagram_clarification_response(supplier_id)
    if prior and is_diagram_followup_request(message) and prior.has_chart:
        return _diagram_already_shown_response(supplier_id)

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    current_date = datetime.now(tz=timezone.utc).date().isoformat()
    user_message = f"{message}{_date_hint(start_date, end_date, current_date)}"

    tools_used: list[str] = []
    sources: list[dict] = []
    limitations: list[str] = []
    raw_tool_results: list[tuple[str, dict]] = []

    params = _server_params()

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            openai_tools = [
                _to_openai_tool(t) for t in tools_result.tools if t.name in ALLOWED_TOOLS
            ]

            messages: list[dict] = [
                {"role": "system", "content": _build_system_prompt(current_date, supplier_name)},
                {"role": "user", "content": user_message},
            ]

            forced = plan_forced_tools(
                message, supplier_name, start_date, end_date, prior_context=prior,
            )
            if forced:
                await _execute_planned_tools(
                    session, forced, supplier_id, start_date, end_date,
                    tools_used, sources, limitations, raw_tool_results,
                )
                messages.append(_tool_context_message(message, raw_tool_results, supplier_name, tools_used))
            else:
                await _llm_tool_round(
                    session, client, async_client=None, model=model,
                    messages=messages, openai_tools=openai_tools,
                    supplier_id=supplier_id, start_date=start_date, end_date=end_date,
                    tools_used=tools_used, sources=sources, limitations=limitations,
                    raw_tool_results=raw_tool_results, max_rounds=5,
                )

            if not tools_used:
                fallback = plan_forced_tools(
                    message, supplier_name, start_date, end_date, prior_context=prior,
                )
                if fallback:
                    await _execute_planned_tools(
                        session, fallback, supplier_id, start_date, end_date,
                        tools_used, sources, limitations, raw_tool_results,
                    )
                    messages.append(_tool_context_message(message, raw_tool_results, supplier_name, tools_used))

            if tools_used and (not messages[-1].get("content") or messages[-1]["role"] != "assistant"):
                if messages[-1].get("role") != "user" or "Verktygsresultat" not in messages[-1].get("content", ""):
                    messages.append(_tool_context_message(message, raw_tool_results, supplier_name, tools_used))

            answer = await _finalize_answer(
                client, model, messages,
                supplier_name=supplier_name, question=message, tools_used=tools_used,
                raw_tool_results=raw_tool_results,
            )

    return _final_payload(answer, tools_used, sources, raw_tool_results, limitations, supplier_id, message)


async def stream_chat(
    message: str,
    supplier_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    supplier_name: str = "",
    prior_context: Optional[dict] = None,
):
    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    guard = classify(message)
    if not guard.should_call_llm:
        yield sse("complete", _guardrail_response(guard, supplier_id))
        return

    prior = prior_context_from_dict(prior_context)
    if is_diagram_followup_request(message) and not prior:
        yield sse("complete", _diagram_clarification_response(supplier_id))
        return
    if prior and is_diagram_followup_request(message) and prior.has_chart:
        yield sse("complete", _diagram_already_shown_response(supplier_id))
        return

    try:
        yield sse("status", {"text": "Tolkar frågan…"})

        async_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        current_date = datetime.now(tz=timezone.utc).date().isoformat()
        user_message = f"{message}{_date_hint(start_date, end_date, current_date)}"

        tools_used: list[str] = []
        sources: list[dict] = []
        limitations: list[str] = []
        raw_tool_results: list[tuple[str, dict]] = []

        params = _server_params()

        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                yield sse("status", {"text": "Hämtar relevanta analysdata…"})

                tools_result = await session.list_tools()
                openai_tools = [
                    _to_openai_tool(t) for t in tools_result.tools if t.name in ALLOWED_TOOLS
                ]

                messages: list[dict] = [
                    {"role": "system", "content": _build_system_prompt(current_date, supplier_name)},
                    {"role": "user", "content": user_message},
                ]

                forced = plan_forced_tools(
                    message, supplier_name, start_date, end_date, prior_context=prior,
                )
                if forced:
                    await _execute_planned_tools(
                        session, forced, supplier_id, start_date, end_date,
                        tools_used, sources, limitations, raw_tool_results,
                    )
                    messages.append(_tool_context_message(message, raw_tool_results, supplier_name, tools_used))
                else:
                    await _llm_tool_round(
                        session, None, async_client=async_client, model=model,
                        messages=messages, openai_tools=openai_tools,
                        supplier_id=supplier_id, start_date=start_date, end_date=end_date,
                        tools_used=tools_used, sources=sources, limitations=limitations,
                        raw_tool_results=raw_tool_results, max_rounds=4,
                    )

                if not tools_used:
                    fallback = plan_forced_tools(
                        message, supplier_name, start_date, end_date, prior_context=prior,
                    )
                    if fallback:
                        await _execute_planned_tools(
                            session, fallback, supplier_id, start_date, end_date,
                            tools_used, sources, limitations, raw_tool_results,
                        )
                        messages.append(_tool_context_message(message, raw_tool_results, supplier_name, tools_used))

                if tools_used:
                    last = messages[-1]
                    if last.get("role") != "user" or "Verktygsresultat" not in last.get("content", ""):
                        messages.append(_tool_context_message(message, raw_tool_results, supplier_name, tools_used))

                yield sse("status", {"text": "Sammanställer svaret…"})

                full_answer_parts: list[str] = []
                final_stream = await async_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=1024,
                    stream=True,
                )

                async for chunk in final_stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta.content:
                        full_answer_parts.append(delta.content)
                        yield sse("delta", {"text": delta.content})

                full_answer = "".join(full_answer_parts)

                if tools_used and (
                    _looks_like_planning(full_answer)
                    or needs_synthesis_retry(
                        full_answer, supplier_name, tools_used, raw_tool_results,
                    )
                ):
                    retry_messages = messages + [
                        _synthesis_retry_message(supplier_name, message, tools_used),
                    ]
                    retry_parts: list[str] = []
                    retry_stream = await async_client.chat.completions.create(
                        model=model,
                        messages=retry_messages,
                        temperature=0.0,
                        max_tokens=1024,
                        stream=True,
                    )
                    async for chunk in retry_stream:
                        if chunk.choices and chunk.choices[0].delta.content:
                            retry_parts.append(chunk.choices[0].delta.content)
                    if retry_parts:
                        full_answer = "".join(retry_parts)

                if not full_answer.strip():
                    full_answer = "Jag kunde inte generera ett svar. Försök igen."

                yield sse("complete", {
                    **_final_payload(
                        full_answer, tools_used, sources, raw_tool_results,
                        limitations, supplier_id, message,
                    ),
                })

    except Exception:
        yield sse("error", {"message": "Analyssystemet stötte på ett fel. Försök igen om en stund."})
