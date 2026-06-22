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
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI, OpenAI
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.services.guardrails import classify
from app.services.chart_builder import pick_chart

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_BACKEND_ROOT = _PROJECT_ROOT / "backend"
_VENV_PYTHON = _BACKEND_ROOT / ".venv" / "bin" / "python"

# Fall back to current interpreter if venv python not found (e.g. CI)
_PYTHON = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else sys.executable

# ---------------------------------------------------------------------------
# Allowed MCP tools — whitelist enforced; any tool not listed is never called
# ---------------------------------------------------------------------------
ALLOWED_TOOLS = {
    "get_supplier_kpis",
    "get_sales_over_time",
    "get_top_products",
    "get_sales_by_region",
    "get_market_share",
    "get_declining_products",
}

# ---------------------------------------------------------------------------
# System prompt — built at call time so current_date is always accurate
# ---------------------------------------------------------------------------
def _build_system_prompt(current_date: str) -> str:
    return f"""Du är en analytisk assistent för Solvigo Sales Intelligence.
Du hjälper leverantörer att förstå sin försäljningsdata baserat uteslutande på data från analytikverktygen.

APPLIKATIONSKONTEXT (injicerad av systemet):
- Dagens datum: {current_date}
- Den aktiva leverantörens kontext är redan inställd av applikationen. Fråga ALDRIG användaren om ett leverantörs-ID eller supplier_id.
- supplier_id injiceras automatiskt av systemet — du behöver inte ange det i dina verktygsanrop.

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
- Håll svar under 150 ord om inte frågan kräver mer detaljer.
"""

# ---------------------------------------------------------------------------
# Build MCP server parameters
# ---------------------------------------------------------------------------
def _server_params() -> StdioServerParameters:
    env = {**os.environ, "PYTHONPATH": str(_BACKEND_ROOT)}
    return StdioServerParameters(
        command=_PYTHON,
        args=["-m", "mcp_server.server"],
        env={k: v for k, v in env.items() if isinstance(v, str)},
        cwd=str(_PROJECT_ROOT),
    )


# ---------------------------------------------------------------------------
# Convert MCP tool schema → OpenAI function definition
# ---------------------------------------------------------------------------
def _to_openai_tool(mcp_tool) -> dict:
    import copy
    raw = mcp_tool.inputSchema or {"type": "object", "properties": {}}
    schema = copy.deepcopy(raw)
    # Strip supplier_id — the backend always injects it; the LLM must never supply it
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


# ---------------------------------------------------------------------------
# Lock supplier_id into tool arguments — the LLM cannot override this
# ---------------------------------------------------------------------------
def _inject_supplier_scope(tool_name: str, args: dict, supplier_id: str) -> dict:
    locked = dict(args)
    if "supplier_id" in locked or tool_name in ALLOWED_TOOLS:
        locked["supplier_id"] = supplier_id
    return locked



# ---------------------------------------------------------------------------
# Main chat function
# ---------------------------------------------------------------------------
async def run_chat(
    message: str,
    supplier_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """
    Run the full grounded chat flow:
    1. Connect to MCP server via stdio transport
    2. Fetch tool list and convert to OpenAI format (whitelist filtered)
    3. Run OpenAI tool-calling loop with supplier scope locked
    4. Collect tool results and MCP source metadata
    5. Return structured response
    """
    # --- Guardrail check (deterministic, no LLM/MCP) ---
    guard = classify(message)
    if not guard.should_call_llm:
        return {
            "answer": guard.answer,
            "tool_calls": [],
            "sources": [],
            "chart": None,
            "limitations": guard.limitations,
            "supplier_id": supplier_id,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        }

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model = os.environ.get("OPENAI_MODEL", "gpt-4o")

    current_date = datetime.now(tz=timezone.utc).date().isoformat()  # e.g. "2026-06-21"

    # Append a date context hint to the user message so the model
    # knows the filter window before it decides which tool to call.
    if start_date or end_date:
        date_hint = f"\n[Datumfilter aktivt: {start_date or 'äldsta data'} → {end_date or current_date}]"
    else:
        date_hint = f"\n[Inget datumfilter — verktyget använder sitt standardfönster. Rapportera den faktiska perioden från date_range i svaret.]"

    user_message = f"{message}{date_hint}"

    tools_used: list[str] = []
    sources: list[dict] = []
    limitations: list[str] = []
    raw_tool_results: list[tuple[str, dict]] = []  # (tool_name, parsed_result) for chart builder

    params = _server_params()

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Get available tools, filter to whitelist only
            tools_result = await session.list_tools()
            openai_tools = [
                _to_openai_tool(t)
                for t in tools_result.tools
                if t.name in ALLOWED_TOOLS
            ]

            messages: list[dict] = [
                {"role": "system", "content": _build_system_prompt(current_date)},
                {"role": "user", "content": user_message},
            ]

            # Agentic tool-calling loop (max 5 rounds to prevent runaway)
            for _ in range(5):
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

                # Append assistant turn
                messages.append(msg.model_dump(exclude_none=True))

                # No more tool calls → done
                if choice.finish_reason == "stop" or not msg.tool_calls:
                    break

                # Process each tool call
                tool_results_messages = []
                for tc in msg.tool_calls:
                    tool_name = tc.function.name

                    # Reject any tool not on the whitelist (belt-and-suspenders)
                    if tool_name not in ALLOWED_TOOLS:
                        tool_results_messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps({"error": f"Tool '{tool_name}' is not permitted."}),
                        })
                        continue

                    # Parse LLM-supplied arguments
                    try:
                        raw_args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        raw_args = {}

                    # Lock supplier scope — LLM cannot override
                    args = _inject_supplier_scope(tool_name, raw_args, supplier_id)

                    # Inject date range if the LLM didn't supply dates and
                    # the user provided a date filter
                    if start_date and "start_date" not in args:
                        args["start_date"] = start_date
                    if end_date and "end_date" not in args:
                        args["end_date"] = end_date

                    # Call MCP tool via transport
                    try:
                        result = await session.call_tool(tool_name, args)
                    except Exception as exc:
                        tool_results_messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps({"error": str(exc)}),
                        })
                        continue

                    # Parse result content
                    if result.content and hasattr(result.content[0], "text"):
                        raw_text = result.content[0].text
                        try:
                            parsed = json.loads(raw_text)
                        except json.JSONDecodeError:
                            parsed = {"raw": raw_text}
                    else:
                        parsed = {}

                    # Collect metadata
                    tools_used.append(tool_name)
                    if isinstance(parsed, dict):
                        raw_source = parsed.get("source", "")
                        source_meta = {
                            "tool": tool_name,
                            "source": raw_source if raw_source.startswith("MCP:") else f"MCP:{tool_name}",
                            "supplier_id": supplier_id,
                            "generated_at": parsed.get("generated_at", datetime.now(tz=timezone.utc).isoformat()),
                            "row_count": parsed.get("row_count"),
                            "date_range": parsed.get("date_range"),
                            "limitations": parsed.get("limitations", []),
                        }
                        sources.append(source_meta)
                        if parsed.get("limitations"):
                            limitations.extend(parsed["limitations"])
                        # Collect raw result for deterministic chart building
                        raw_tool_results.append((tool_name, parsed))

                    tool_results_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(parsed, ensure_ascii=False),
                    })

                messages.extend(tool_results_messages)

            # Extract final answer
            final_msg = next(
                (m for m in reversed(messages) if m.get("role") == "assistant"),
                None,
            )
            if final_msg:
                # Handle both dict (model_dump) and object forms
                content = final_msg.get("content") if isinstance(final_msg, dict) else getattr(final_msg, "content", "")
                raw_answer = content or ""
            else:
                raw_answer = "Jag kunde inte generera ett svar. Försök igen."

            # Build chart deterministically from MCP tool results (never from LLM text)
            chart = pick_chart(raw_tool_results)

    return {
        "answer": raw_answer,
        "tool_calls": list(dict.fromkeys(tools_used)),  # deduplicated, ordered
        "sources": sources,
        "chart": chart,
        "limitations": list(set(limitations)),
        "supplier_id": supplier_id,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Streaming chat — Server-Sent Events
# ---------------------------------------------------------------------------
async def stream_chat(
    message: str,
    supplier_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    Async generator that yields SSE-formatted strings.

    Event types:
      status   {"text": "…"}           — truthful progress stage label
      delta    {"text": "…"}           — answer text chunk (real-time from OpenAI)
      complete {answer, chart, sources, tool_calls, limitations, supplier_id, generated_at}
      error    {"message": "…"}        — safe user-facing error; no internals exposed

    Guardrail-blocked questions emit a single `complete` event immediately
    (no MCP subprocess, no status/delta events).
    """

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    # --- Guardrail check (deterministic, no LLM / MCP) ---
    guard = classify(message)
    if not guard.should_call_llm:
        yield sse("complete", {
            "answer": guard.answer,
            "tool_calls": [],
            "sources": [],
            "chart": None,
            "limitations": guard.limitations,
            "supplier_id": supplier_id,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        })
        return

    try:
        yield sse("status", {"text": "Tolkar frågan…"})

        # Use AsyncOpenAI so all completions calls are awaitable and the
        # streaming iteration is async — this prevents blocking the event loop
        # inside FastAPI's StreamingResponse.
        async_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        current_date = datetime.now(tz=timezone.utc).date().isoformat()

        if start_date or end_date:
            date_hint = (
                f"\n[Datumfilter aktivt: {start_date or 'äldsta data'} → {end_date or current_date}]"
            )
        else:
            date_hint = (
                "\n[Inget datumfilter — verktyget använder sitt standardfönster. "
                "Rapportera den faktiska perioden från date_range i svaret.]"
            )

        user_message = f"{message}{date_hint}"

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
                    _to_openai_tool(t)
                    for t in tools_result.tools
                    if t.name in ALLOWED_TOOLS
                ]

                messages: list[dict] = [
                    {"role": "system", "content": _build_system_prompt(current_date)},
                    {"role": "user", "content": user_message},
                ]

                # --- Tool-calling rounds (non-streaming; up to 4 rounds) ---
                # The final text synthesis is always a separate streaming call below.
                for _ in range(4):
                    # await: AsyncOpenAI.chat.completions.create returns a coroutine
                    response = await async_client.chat.completions.create(
                        model=model,
                        messages=messages,
                        tools=openai_tools,
                        tool_choice="auto",
                        temperature=0.2,
                        max_tokens=1024,
                    )

                    choice = response.choices[0]
                    msg = choice.message

                    # No tool calls → LLM wants to give final text answer.
                    # Do NOT add this message — the streaming call below re-generates it.
                    if choice.finish_reason == "stop" or not msg.tool_calls:
                        break

                    # Tool-calling round: add assistant message + process each tool
                    messages.append(msg.model_dump(exclude_none=True))

                    tool_results_messages = []
                    for tc in msg.tool_calls:
                        tool_name = tc.function.name

                        if tool_name not in ALLOWED_TOOLS:
                            tool_results_messages.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": json.dumps({"error": f"Tool '{tool_name}' is not permitted."}),
                            })
                            continue

                        try:
                            raw_args = json.loads(tc.function.arguments or "{}")
                        except json.JSONDecodeError:
                            raw_args = {}

                        args = _inject_supplier_scope(tool_name, raw_args, supplier_id)
                        if start_date and "start_date" not in args:
                            args["start_date"] = start_date
                        if end_date and "end_date" not in args:
                            args["end_date"] = end_date

                        try:
                            result = await session.call_tool(tool_name, args)
                        except Exception as exc:
                            tool_results_messages.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": json.dumps({"error": str(exc)}),
                            })
                            continue

                        if result.content and hasattr(result.content[0], "text"):
                            raw_text = result.content[0].text
                            try:
                                parsed = json.loads(raw_text)
                            except json.JSONDecodeError:
                                parsed = {"raw": raw_text}
                        else:
                            parsed = {}

                        tools_used.append(tool_name)
                        if isinstance(parsed, dict):
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

                        tool_results_messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(parsed, ensure_ascii=False),
                        })

                    messages.extend(tool_results_messages)

                # --- Final synthesis (truly async streaming) ---
                yield sse("status", {"text": "Sammanställer svaret…"})

                # Build chart deterministically from MCP results — never from LLM text
                chart = pick_chart(raw_tool_results)

                full_answer_parts: list[str] = []
                # stream=True with AsyncOpenAI returns an AsyncStream; iterate with async for
                final_stream = await async_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=1024,
                    stream=True,
                    # No `tools` param — synthesis only; tool results already in context
                )

                async for chunk in final_stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta.content:
                        full_answer_parts.append(delta.content)
                        yield sse("delta", {"text": delta.content})

                full_answer = "".join(full_answer_parts) or "Jag kunde inte generera ett svar. Försök igen."

                yield sse("complete", {
                    "answer": full_answer,
                    "tool_calls": list(dict.fromkeys(tools_used)),
                    "sources": sources,
                    "chart": chart,
                    "limitations": list(set(limitations)),
                    "supplier_id": supplier_id,
                    "generated_at": datetime.now(tz=timezone.utc).isoformat(),
                })

    except Exception:
        # Emit a safe error message — never expose internals, stack traces, or secrets
        yield sse("error", {"message": "Analyssystemet stötte på ett fel. Försök igen om en stund."})
