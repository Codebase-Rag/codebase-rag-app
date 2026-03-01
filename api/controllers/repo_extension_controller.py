from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
# from services.repo_service import optimize, discard_changes
from services.repo_extension_service import query
from typing import Optional
from typing import Any


router = APIRouter()

@router.get("/repo/extension/query", status_code=status.HTTP_200_OK)
async def query_repo(question: str, sid: str):
    response = await query(question, sid)
    return JSONResponse(content={"response": response}, status_code=status.HTTP_200_OK)

# @router.post("/repo/extension/optimize", status_code=status.HTTP_200_OK)
# async def optimize_repo(repo_path: str, session_id: str, language: Optional[str] = None, ref: Optional[str] = None, question: Optional[str] = None):
#     response, edit = await optimize(repo_path=repo_path, session_id=session_id, language=language, question=question, ref=ref)
#     return JSONResponse(content={"response": response, "edit": edit}, status_code=status.HTTP_200_OK)    


# @router.post("/repo/extension/reject", status_code=status.HTTP_200_OK)
# async def reject(repo_path: str, session_id: str):
#     await discard_changes(repo_path, session_id)
#     return JSONResponse(content={"response": 'Changes have been discarded!!!'}, status_code=status.HTTP_200_OK) 