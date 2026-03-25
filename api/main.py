from fastapi import FastAPI
from controllers.graph_controller import router as graph_router
from controllers.repo_controller import router as repo_router
from controllers.repo_extension_controller import router as repo_extension_router
from controllers.remote_repo_controller import router as remote_repo_router
from controllers.session_controller import router as session_router
from fastapi.middleware.cors import CORSMiddleware
from sockets.server import sio
import socketio
import uvicorn
import logging

from sockets.server import sio
from core.database import init_db
from services.session_sync_worker import get_worker

logger = logging.getLogger(__name__)

app = FastAPI()

@app.on_event("startup")
async def on_startup():
	"""Initialize database and start background sync worker."""
	init_db()
	
	# Start background session sync worker
	# Syncs Redis sessions to PostgreSQL every 300 seconds (5 minutes)
	# Adjust the sync_interval parameter as needed for your use case
	worker = get_worker(sync_interval=300)
	await worker.start()
	
	logger.info("Application startup complete - sync worker started")

@app.on_event("shutdown")
async def on_shutdown():
	"""Stop background sync worker and perform final sync."""
	worker = get_worker()
	if worker.is_running():
		await worker.stop()
	logger.info("Application shutdown complete")

@app.get("/")
async def root():
	return {"message": "Server is alive and active!"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],          # Allow all HTTP methods
    allow_headers=["*"],          # Allow all headers
)
app.include_router(graph_router)
app.include_router(repo_router)
app.include_router(repo_extension_router)
app.include_router(remote_repo_router)
app.include_router(session_router)

socket_app = socketio.ASGIApp(
	sio,
	other_asgi_app=app,
)

if __name__ == "__main__":
	uvicorn.run("main:socket_app", host="0.0.0.0", port=8000)

# if __name__ == "__main__":
#     from codebase_rag.main import app

#     app()

