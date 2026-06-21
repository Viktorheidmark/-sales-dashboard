import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_supplier_id
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import run_chat

router = APIRouter(prefix="/api/chat", tags=["chat"])

_TIMEOUT_SECONDS = 60


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    supplier_id: str = Depends(get_current_supplier_id),
) -> ChatResponse:
    """
    Grounded AI analytics chat.

    The LLM answers using only MCP tool results — no direct database access,
    no free-form SQL. Supplier scope is derived from the authenticated session;
    the frontend cannot influence it.
    """
    try:
        result = await asyncio.wait_for(
            run_chat(
                message=req.message,
                supplier_id=supplier_id,
                start_date=req.start_date,
                end_date=req.end_date,
            ),
            timeout=_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Chat request timed out after {_TIMEOUT_SECONDS}s.",
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Missing environment variable: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Chat error: {exc}",
        )

    return ChatResponse(**result)
