"""
Deterministic intent routing for analytics chat.

Resolves which MCP tool(s) must run for common Swedish question patterns
when the LLM might otherwise skip tool calls (e.g. missing category_name).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

CATEGORIES = ("Mejeri", "Dryck", "Mat och snacks")
KNOWN_REGIONS = ("Stockholm", "Göteborg", "Malmö", "Uppsala", "Online")

_MARKET_SHARE_RE = re.compile(
    r"(marknadsandel|market\s+share|"
    r"konkurrent|konkurrenter|"
    r"vårt märke|vårt varumärke|vår andel|"
    r"jämfört med konkurrenter|jämfört med konkurrenterna|"
    r"mot konkurrenter|mot konkurrenterna|"
    r"hur går det för vårt märke)",
    re.IGNORECASE,
)

_TOP_PRODUCTS_RE = re.compile(
    r"("
    r"(produkt|produkter).{0,50}(bäst|säljer|topp|störst|mest)|"
    r"(bäst|topp|störst|mest).{0,50}(produkt|produkter)"
    r")",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class ToolPlan:
    tool_name: str
    args: dict
    reason: str


def default_category_for_supplier(supplier_name: str) -> str:
    name = supplier_name.lower()
    if "coca-cola" in name or "cocacola" in name:
        return "Dryck"
    if "orkla" in name:
        return "Mat och snacks"
    return "Mejeri"


def extract_category(message: str) -> Optional[str]:
    msg = message.lower()
    if "mat och snacks" in msg:
        return "Mat och snacks"
    if "mejeri" in msg:
        return "Mejeri"
    if "dryck" in msg:
        return "Dryck"
    if re.search(r"\bsnacks\b", msg):
        return "Mat och snacks"
    return None


def extract_region(message: str) -> Optional[str]:
    for region in KNOWN_REGIONS:
        if region.lower() in message.lower():
            return region
    return None


def plan_forced_tools(
    message: str,
    supplier_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[ToolPlan]:
    """
    Return deterministic MCP tool plan(s) for well-known question shapes.
    Empty list means the LLM tool loop should decide.
    """
    msg = message.strip()
    plans: list[ToolPlan] = []

    if _TOP_PRODUCTS_RE.search(msg):
        region = extract_region(msg)
        if region:
            args: dict = {"region": region, "limit": 5}
            if start_date:
                args["start_date"] = start_date
            if end_date:
                args["end_date"] = end_date
            plans.append(ToolPlan(
                tool_name="get_top_products",
                args=args,
                reason=f"regional top products ({region})",
            ))
            return plans

    if _MARKET_SHARE_RE.search(msg):
        category = extract_category(msg) or default_category_for_supplier(supplier_name)
        args = {"category_name": category}
        if start_date:
            args["start_date"] = start_date
        if end_date:
            args["end_date"] = end_date
        plans.append(ToolPlan(
            tool_name="get_market_share",
            args=args,
            reason=f"market share ({category})",
        ))
        return plans

    return plans
