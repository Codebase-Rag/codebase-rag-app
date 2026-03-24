from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse, StreamingResponse
from services.remote_repo_service import query, query_stream, discard_changes
from typing import Optional
from typing import Any

class QueryRequest(BaseModel):
    question: str
    socket_id: str
    mode: str
    session_id: Optional[str] = None

    

router = APIRouter()

@router.post("/remote/repo/query", status_code=status.HTTP_200_OK)
async def query_repo(request: QueryRequest):
    session_id, response, edit = await query(question=request.question, mode=request.mode, socket_id=request.socket_id, session_id=request.session_id)
    return JSONResponse(content={"session_id": session_id, "response": response, "edit": edit}, status_code=status.HTTP_200_OK)

@router.post("/remote/repo/query/stream", status_code=status.HTTP_200_OK)
async def query_repo_stream(request: QueryRequest):
    """Streaming endpoint for query response."""
    return StreamingResponse(
        query_stream(question=request.question, mode=request.mode, socket_id=request.socket_id, session_id=request.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@router.delete("/remote/repo/reject/sessions/{session_id}", status_code=status.HTTP_200_OK)
async def reject(socket_id: str, session_id: str):
    await discard_changes(socket_id, session_id)
    return JSONResponse(content={"response": 'Changes have been discarded!!!'}, status_code=status.HTTP_200_OK) 
