from fastapi import APIRouter, status
from pydantic import BaseModel
from fastapi.responses import JSONResponse, StreamingResponse
from services.remote_repo_service import query, query_stream, discard_changes, ingest_uploaded
from typing import Optional
import base64

class QueryRequest(BaseModel):
    question: str
    socket_id: str
    mode: str
    session_id: Optional[str] = None


class FileUpload(BaseModel):
    """A single file or directory in the upload."""
    path: str  # Relative path from project root
    name: str  # File/directory name
    is_dir: bool = False
    is_file: bool = True
    content: Optional[str] = None  # Base64 encoded content (None for directories)
    extension: str = ""
    size: int = 0


class IngestRequest(BaseModel):
    """Request to ingest a project with all files included."""
    project_name: str
    socket_id: str
    files: list[FileUpload]


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


@router.post("/remote/repo/ingest", status_code=status.HTTP_200_OK)
async def ingest_repo(request: IngestRequest):
    """
    Ingest a project into the knowledge graph.
    
    The frontend sends all project files directly in the request body.
    File contents should be base64 encoded.
    """
    try:
        files_data = []
        for f in request.files:
            file_dict = {
                "path": f.path,
                "name": f.name,
                "is_dir": f.is_dir,
                "is_file": f.is_file,
                "extension": f.extension,
                "size": f.size,
                "content": base64.b64decode(f.content) if f.content else None,
            }
            files_data.append(file_dict)
        
        await ingest_uploaded(
            project_name=request.project_name, 
            socket_id=request.socket_id,
            files=files_data
        )
        return JSONResponse(
            content={
                "status": "success",
                "message": f"Successfully ingested project: {request.project_name}",
                "files_processed": len(files_data),
            },
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
