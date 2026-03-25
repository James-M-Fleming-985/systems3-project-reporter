"""
AI Chat Router - API endpoints for AI-powered project management chat.
Supports context-aware conversations with Claude, conversation persistence,
action execution, and training data export.
"""
import os
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.ai_chat_service import AIChatService
from services.ai_context_builder import (
    build_milestone_context,
    build_risk_context,
    build_schedule_context,
    build_general_context,
)
from services.ai_action_executor import parse_actions, execute_action
from repositories.conversation_repository import ConversationRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ai-chat"])

# Initialize services
chat_service = AIChatService()
conversation_repo = ConversationRepository()


# ── Request / Response Models ────────────────────────────────────

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str
    context_type: str = "general"  # milestone, risk, schedule, general
    context_id: Optional[str] = None
    project_code: Optional[str] = None
    program_name: Optional[str] = None
    table_id: Optional[str] = None
    execute_actions: bool = False  # If True, execute proposed actions


class ActionExecuteRequest(BaseModel):
    conversation_id: str
    actions: list  # List of action dicts to execute


# ── Helpers ──────────────────────────────────────────────────────

def _get_user_id(request: Request) -> str:
    user = getattr(request.state, "user", None) if hasattr(request, "state") else None
    if user and isinstance(user, dict):
        return str(user.get("user_id", "anonymous"))
    return "anonymous"


def _build_system_prompt(data: ChatRequest) -> str:
    """Build context-appropriate system prompt."""
    if data.context_type == "milestone" and data.project_code and data.context_id:
        return build_milestone_context(data.project_code, data.context_id)
    elif data.context_type == "risk" and data.context_id:
        program = data.program_name or data.project_code or ""
        return build_risk_context(program, data.context_id, data.project_code or "")
    elif data.context_type == "schedule" and data.project_code:
        return build_schedule_context(data.project_code, data.table_id or "")
    elif data.project_code:
        return build_general_context(data.project_code)
    else:
        return build_general_context("")


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/api/ai/status")
async def ai_status():
    """Check if AI chat is configured and available."""
    return JSONResponse({
        "configured": chat_service.is_configured(),
        "model": chat_service.model,
        "context_window": chat_service.get_context_window(),
    })


@router.post("/api/ai/chat")
async def ai_chat(request: Request, data: ChatRequest):
    """
    Main AI chat endpoint. Sends a message to Claude with project context.
    Creates or resumes a conversation automatically.
    """
    if not chat_service.is_configured():
        raise HTTPException(
            status_code=503,
            detail="AI chat not configured. Set ANTHROPIC_API_KEY environment variable.",
        )

    try:
        user_id = _get_user_id(request)

        # Resolve or create conversation
        conversation = None
        if data.conversation_id:
            conversation = conversation_repo.get(data.conversation_id)

        if conversation is None:
            # Check for existing conversation for this entity
            if data.context_id:
                existing = conversation_repo.find_by_context(
                    data.context_type, data.context_id, user_id
                )
                # Migration: find conversations saved under "anonymous" before user_id fix
                if not existing and user_id != "anonymous":
                    existing = conversation_repo.find_by_context(
                        data.context_type, data.context_id, "anonymous"
                    )
                if existing:
                    conversation = existing[0]

        if conversation is None:
            conversation = conversation_repo.create(
                context_type=data.context_type,
                context_id=data.context_id or "",
                project_code=data.project_code or "",
                user_id=user_id,
            )

        # Append user message
        user_tokens = chat_service.estimate_tokens(data.message)
        conversation_repo.append_message(
            conversation["id"], "user", data.message, user_tokens
        )

        # Build message history for Claude
        conv_data = conversation_repo.get(conversation["id"])
        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in conv_data.get("messages", [])
        ]

        # Build system prompt (graceful fallback on errors)
        try:
            system_prompt = _build_system_prompt(data)
        except Exception as ctx_err:
            logger.warning(f"Context builder error, using fallback: {ctx_err}", exc_info=True)
            system_prompt = "You are a helpful AI assistant embedded in a project management tool. Answer any question the user asks — including project risks, timelines, milestones, scheduling, and any related business, legal, financial, or operational topics that arise from their projects."

        # Send to Claude
        try:
            result = chat_service.send_message(system_prompt, messages)
        except Exception as e:
            logger.error(f"Claude API call failed: {e}", exc_info=True)
            raise HTTPException(status_code=502, detail=f"AI service error: {str(e)}")

        reply = result["reply"]
        output_tokens = result["output_tokens"]
        input_tokens = result["input_tokens"]

        # Append assistant reply
        conversation_repo.append_message(
            conversation["id"], "assistant", reply, output_tokens
        )

        # Parse any proposed actions
        proposed_actions = parse_actions(reply)

        # If execute_actions is True and there are actions, execute them
        action_results = []
        if data.execute_actions and proposed_actions:
            for action in proposed_actions:
                action_result = execute_action(action)
                action_results.append(action_result)
                conversation_repo.record_action(
                    conversation["id"],
                    action.get("action", "unknown"),
                    action_result,
                )

        # Get updated token totals and staleness
        updated_conv = conversation_repo.get(conversation["id"])
        total_tokens = updated_conv.get("total_tokens", 0)
        staleness = chat_service.check_staleness(total_tokens)

        return JSONResponse({
            "conversation_id": conversation["id"],
            "reply": reply,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens_used": total_tokens,
            "staleness": staleness,
            "proposed_actions": proposed_actions,
            "action_results": action_results,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI chat endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/api/ai/actions/execute")
async def execute_actions_endpoint(request: Request, data: ActionExecuteRequest):
    """Execute previously proposed actions after user confirmation."""
    conversation = conversation_repo.get(data.conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    results = []
    for action in data.actions:
        result = execute_action(action)
        results.append(result)
        conversation_repo.record_action(
            data.conversation_id,
            action.get("action", "unknown"),
            result,
        )

    # Build summary message
    successes = sum(1 for r in results if r.get("success"))
    summary = f"Executed {successes}/{len(results)} actions successfully."
    conversation_repo.append_message(
        data.conversation_id, "assistant",
        f"✅ {summary}\n\n" + "\n".join(
            f"- {'✓' if r['success'] else '✗'} {r['message']}" for r in results
        ),
        0,
    )

    return JSONResponse({
        "results": results,
        "summary": summary,
    })


# ── Conversation Management ─────────────────────────────────────

@router.get("/api/ai/conversations")
async def list_conversations(
    request: Request,
    project_code: str = None,
    context_type: str = None,
    context_id: str = None,
    limit: int = 50,
):
    """List conversations with optional filters."""
    user_id = _get_user_id(request)

    if context_id and context_type:
        convs = conversation_repo.find_by_context(context_type, context_id, user_id)
        # Migration: also find conversations saved under "anonymous" before user_id fix
        if not convs and user_id != "anonymous":
            convs = conversation_repo.find_by_context(context_type, context_id, "anonymous")
        return JSONResponse({"conversations": convs})

    convs = conversation_repo.list_all(project_code, context_type, limit)
    return JSONResponse({"conversations": convs})


@router.get("/api/ai/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a full conversation with all messages."""
    conv = conversation_repo.get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return JSONResponse(conv)


@router.delete("/api/ai/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    success = conversation_repo.delete(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return JSONResponse({"success": True})


@router.post("/api/ai/conversations/new")
async def start_new_conversation(request: Request, data: ChatRequest):
    """Force-start a new conversation (ignoring existing ones for this entity)."""
    user_id = _get_user_id(request)
    conversation = conversation_repo.create(
        context_type=data.context_type,
        context_id=data.context_id or "",
        project_code=data.project_code or "",
        user_id=user_id,
    )
    return JSONResponse({"conversation": conversation})


@router.get("/api/ai/conversations/export/all")
async def export_conversations(request: Request):
    """Export all conversations for training/analysis. Admin only."""
    user = getattr(request.state, "user", None) if hasattr(request, "state") else None
    if not user or not isinstance(user, dict) or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    conversations = conversation_repo.export_all()
    return JSONResponse({"conversations": conversations, "count": len(conversations)})


@router.get("/api/ai/token-status/{conversation_id}")
async def token_status(conversation_id: str):
    """Get token usage and staleness for a conversation."""
    conv = conversation_repo.get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    total_tokens = conv.get("total_tokens", 0)
    staleness = chat_service.check_staleness(total_tokens)
    return JSONResponse(staleness)
