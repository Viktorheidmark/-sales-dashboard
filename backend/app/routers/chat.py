import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.dependencies import get_current_user
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import run_chat, stream_chat

router = APIRouter(prefix="/api/chat", tags=["chat"])

_TIMEOUT_SECONDS = 60


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
) -> ChatResponse:
    supplier_id = user["supplier_id"]
    """
    Grounded AI analytics chat (non-streaming).

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
                supplier_name=user.get("supplier_name", ""),
                prior_context=req.prior_context.model_dump() if req.prior_context else None,
                follow_up_action=req.follow_up_action.model_dump() if req.follow_up_action else None,
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


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
) -> StreamingResponse:
    supplier_id = user["supplier_id"]
    """
    Grounded AI analytics chat — Server-Sent Events streaming.

    Emits SSE events:
      event: status   — truthful progress stage (no invented data)
      event: delta    — answer text chunk streamed from OpenAI after MCP data is ready
      event: complete — final JSON payload with chart, sources, tool_calls, limitations
      event: error    — safe error message (no internals exposed)

    Guardrail-blocked questions return a single `complete` event immediately
    without opening an MCP subprocess.
    """
    async def generator():
        try:
            async for chunk in stream_chat(
                message=req.message,
                supplier_id=supplier_id,
                start_date=req.start_date,
                end_date=req.end_date,
                supplier_name=user.get("supplier_name", ""),
                prior_context=req.prior_context.model_dump() if req.prior_context else None,
                follow_up_action=req.follow_up_action.model_dump() if req.follow_up_action else None,
            ):
                yield chunk
        except asyncio.CancelledError:
            # Client disconnected — stop silently
            pass

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
