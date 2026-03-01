from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from services.graph_service import update_graph, clean

router = APIRouter()

@router.post("/graph/create", status_code=status.HTTP_200_OK)
async def create_graph(repo_path: str):
    try:
        await create_graph(str)
        return JSONResponse(content={"result": 'Graph created'}, status_code=status.HTTP_200_OK)
    except Exception as e:
        return JSONResponse(content={"result": 'Graph create failed'}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@router.patch("/graph/update", status_code=status.HTTP_200_OK)
def update_graph(repo_path: str):
    return JSONResponse(content={"response": 'update_graph() called!'}, status_code=status.HTTP_200_OK)

@router.delete("/graph/deleteAll", status_code=status.HTTP_200_OK)
def delete_all_graph():
    try:
        clean()
        return JSONResponse(content={"result": 'All graphs are removed'}, status_code=status.HTTP_200_OK)
    except Exception as e:
        return JSONResponse(content={"result": 'Graphs removed failed'}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
 

@router.get("/graph/export", status_code=status.HTTP_200_OK)
def export_graph(repo_path: str, file_name: str):
    return JSONResponse(content={"response": 'export_graph() called!'}, status_code=status.HTTP_200_OK)

