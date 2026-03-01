from sockets.server import sio

async def emit_read_file_event(repo_path: str):
    await sio.emit('read_file', repo_path)