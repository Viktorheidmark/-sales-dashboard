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
from app.services.chart_builder import pick_chart
from app.services.intent_router import plan_forced_tools, default_category_for_supplier

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
}

_PLANNING_RE = re.compile(
    r"(jag kommer att|jag ska |jag tänker |låt mig |kommer att hämta|kommer att kontrollera)",
    re.IGNORECASE,
)

_SYNTHESIS_SUFFIX = (
    "\n\n[Instruktion: Verktygsdata är redan hämtad. Skriv slutgiltigt svar direkt på svenska "
    "med siffrorna från verktygsresultaten. Nämn kategorin och perioden från date_range. "
    "Beskriv inte planer, kommande steg eller att du ska hämta eller kontrollera data.]"
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
- Om verktygsresultatet visar positiva intäkter, rapportera dem exakt. Påstå aldrig att det saknas data om verktyget returnerat värden.

Regler du alltid måste följa:
- Svara alltid på svenska, kortfattat och affärsinriktat.
- Hitta aldrig på siffror. Gör endast påståenden som stöds av verktygsresultat.
- Om data saknas eller frågan inte kan besvaras med tillgängliga verktyg, säg det tydligt.
- Avslöja aldrig konkurrentdata på produkt-, kund- eller ordernivå. Konkurrentdata är alltid aggregerad.
- Förklara osäkerhet eller begränsningar när det är relevant.
- Föreslå praktiska nästa steg när datan stöder det.
- Skriv slutsvaret direkt. Beskriv ALDRIG vad du kommer att göra, hämta eller kontrollera.
- Håll svar under 150 ord om inte frågan kräver mer detaljer.
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
    args = _inject_supplier_scope(tool_name, raw_args, supplier_id)
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
        _record_tool_result(
            plan.tool_name, parsed, supplier_id,
            tools_used, sources, limitations, raw_tool_results,
        )


def _tool_context_message(question: str, raw_tool_results: list[tuple[str, dict]]) -> dict:
    payload = {name: result for name, result in raw_tool_results}
    return {
        "role": "user",
        "content": (
            "Följande verktygsresultat är hämtade och ska användas för slutsvar. "
            "Svara direkt på frågan på svenska med dessa siffror.\n\n"
            f"Fråga: {question}\n\n"
            f"Verktygsresultat:\n{json.dumps(payload, ensure_ascii=False)}"
            f"{_SYNTHESIS_SUFFIX}"
        ),
    }


def _looks_like_planning(answer: str) -> bool:
    return bool(answer) and bool(_PLANNING_RE.search(answer))


def _guardrail_response(guard, supplier_id: str) -> dict:
    return {
        "answer": guard.answer,
        "tool_calls": [],
        "sources": [],
        "chart": None,
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
) -> dict:
    return {
        "answer": answer,
        "tool_calls": list(dict.fromkeys(tools_used)),
        "sources": sources,
        "chart": pick_chart(raw_tool_results),
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
) -> dict:
    guard = classify(message)
    if not guard.should_call_llm:
        return _guardrail_response(guard, supplier_id)

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

            forced = plan_forced_tools(message, supplier_name, start_date, end_date)
            if forced:
                await _execute_planned_tools(
                    session, forced, supplier_id, start_date, end_date,
                    tools_used, sources, limitations, raw_tool_results,
                )
                messages.append(_tool_context_message(message, raw_tool_results))
            else:
                await _llm_tool_round(
                    session, client, async_client=None, model=model,
                    messages=messages, openai_tools=openai_tools,
                    supplier_id=supplier_id, start_date=start_date, end_date=end_date,
                    tools_used=tools_used, sources=sources, limitations=limitations,
                    raw_tool_results=raw_tool_results, max_rounds=5,
                )

            if not tools_used:
                fallback = plan_forced_tools(message, supplier_name, start_date, end_date)
                if fallback:
                    await _execute_planned_tools(
                        session, fallback, supplier_id, start_date, end_date,
                        tools_used, sources, limitations, raw_tool_results,
                    )
                    messages.append(_tool_context_message(message, raw_tool_results))

            if tools_used and (not messages[-1].get("content") or messages[-1]["role"] != "assistant"):
                if messages[-1].get("role") != "user" or "Verktygsresultat" not in messages[-1].get("content", ""):
                    messages.append(_tool_context_message(message, raw_tool_results))

            answer = await _synthesize_sync(client, model, messages)
            if _looks_like_planning(answer) and tools_used:
                messages.append({
                    "role": "user",
                    "content": (
                        "Skriv om svaret som ett färdigt analysresultat baserat på verktygsdata. "
                        "Inga planeringsfraser." + _SYNTHESIS_SUFFIX
                    ),
                })
                answer = await _synthesize_sync(client, model, messages)

            if not answer.strip():
                answer = "Jag kunde inte generera ett svar. Försök igen."

    return _final_payload(answer, tools_used, sources, raw_tool_results, limitations, supplier_id)


async def stream_chat(
    message: str,
    supplier_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    supplier_name: str = "",
):
    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    guard = classify(message)
    if not guard.should_call_llm:
        yield sse("complete", _guardrail_response(guard, supplier_id))
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

                forced = plan_forced_tools(message, supplier_name, start_date, end_date)
                if forced:
                    await _execute_planned_tools(
                        session, forced, supplier_id, start_date, end_date,
                        tools_used, sources, limitations, raw_tool_results,
                    )
                    messages.append(_tool_context_message(message, raw_tool_results))
                else:
                    await _llm_tool_round(
                        session, None, async_client=async_client, model=model,
                        messages=messages, openai_tools=openai_tools,
                        supplier_id=supplier_id, start_date=start_date, end_date=end_date,
                        tools_used=tools_used, sources=sources, limitations=limitations,
                        raw_tool_results=raw_tool_results, max_rounds=4,
                    )

                if not tools_used:
                    fallback = plan_forced_tools(message, supplier_name, start_date, end_date)
                    if fallback:
                        await _execute_planned_tools(
                            session, fallback, supplier_id, start_date, end_date,
                            tools_used, sources, limitations, raw_tool_results,
                        )
                        messages.append(_tool_context_message(message, raw_tool_results))

                if tools_used:
                    last = messages[-1]
                    if last.get("role") != "user" or "Verktygsresultat" not in last.get("content", ""):
                        messages.append(_tool_context_message(message, raw_tool_results))

                yield sse("status", {"text": "Sammanställer svaret…"})
                chart = pick_chart(raw_tool_results)

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

                if _looks_like_planning(full_answer) and tools_used:
                    retry_messages = messages + [{
                        "role": "user",
                        "content": (
                            "Skriv om svaret som ett färdigt analysresultat baserat på verktygsdata. "
                            "Inga planeringsfraser." + _SYNTHESIS_SUFFIX
                        ),
                    }]
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
                    **_final_payload(full_answer, tools_used, sources, raw_tool_results, limitations, supplier_id),
                    "chart": chart,
                })

    except Exception:
        yield sse("error", {"message": "Analyssystemet stötte på ett fel. Försök igen om en stund."})
