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
from typing import Any, Optional

from openai import OpenAI
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.services.guardrails import classify

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
- Returnera ett diagram (chart_payload) endast när det tydligt tillför värde:
    - Tidsserie → line_chart
    - Ranking/jämförelse → bar_chart
    - Marknadsandel → pie_chart
- chart_payload-formatet: {{"type": "line_chart"|"bar_chart"|"pie_chart", "title": "...", "data": [...], "x_key": "...", "y_key": "..."}}
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
# Extract chart payload from tool result if the LLM embedded one
# ---------------------------------------------------------------------------
def _extract_chart(text_content: str) -> Optional[dict]:
    """
    The LLM may embed a JSON chart_payload block inside its final answer.
    We parse it out so the frontend can render it natively.
    """
    import re
    match = re.search(r'```json\s*(\{.*?"type"\s*:\s*"(?:line|bar|pie)_chart".*?\})\s*```', text_content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def _strip_chart_block(text: str) -> str:
    import re
    return re.sub(r'```json\s*\{.*?"type"\s*:\s*"(?:line|bar|pie)_chart".*?\}\s*```', '', text, flags=re.DOTALL).strip()


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
    chart: Optional[dict] = None
    limitations: list[str] = []

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

            # Extract any embedded chart payload from the answer text
            chart = _extract_chart(raw_answer)
            if chart:
                raw_answer = _strip_chart_block(raw_answer)

    return {
        "answer": raw_answer,
        "tool_calls": list(dict.fromkeys(tools_used)),  # deduplicated, ordered
        "sources": sources,
        "chart": chart,
        "limitations": list(set(limitations)),
        "supplier_id": supplier_id,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
