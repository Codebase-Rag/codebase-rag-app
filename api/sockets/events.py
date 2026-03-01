from .server import sio

@sio.on("connect")
async def connect(sid, environ):
    print("Client connected: ", sid)

@sio.on("disconnect")
async def disconnect(sid, environ): 
    print("Client disconnected: ", sid)

@sio.on("read_file")
async def read_file(sid, data: str):
    print(data)