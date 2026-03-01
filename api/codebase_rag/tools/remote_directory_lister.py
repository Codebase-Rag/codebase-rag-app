import os
from pathlib import Path

from loguru import logger
from pydantic_ai import Tool
from sockets.server import sio


class RemoteDirectoryLister:
    def __init__(self, socket_id: str):
        self.socket_id = socket_id

    async def list_directory_contents(self, directory_path: str) -> str:
        """
        Lists the contents of a specified directory.
        """
        print(f"list_directory_contents: {directory_path}")
        try:
            res = await sio.call('dir:list', {'dir_path': directory_path}, to=self.socket_id)
            
            if not res["ok"]:
                return res["error"]
            
            return res["content"]

        except Exception as e:
            logger.error(f"Error listing directory {directory_path}: {e}")
            return f"Error: Could not list contents of '{directory_path}'."




def create_directory_lister_tool(directory_lister: RemoteDirectoryLister) -> Tool:
    return Tool(
        function=directory_lister.list_directory_contents,
        description="Lists the contents of a directory to explore the codebase.",
    )
