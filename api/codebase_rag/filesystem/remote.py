"""Remote filesystem implementation using socket.io."""

import base64
from loguru import logger

from sockets.server import sio

from .protocol import (
    BatchFileContent,
    DirectoryTree,
    ExistsResult,
    FileContent,
    FileInfo,
    FilesystemInterface,
)


class RemoteFilesystem(FilesystemInterface):
    """
    Remote filesystem implementation using socket.io.
    
    Proxies filesystem operations to a connected client over WebSocket.
    The client must implement handlers for the following events:
    - fs:list_tree
    - fs:read_file
    - fs:read_batch
    - fs:check_exists
    
    All binary data is base64 encoded for transport.
    """

    def __init__(self, socket_id: str, project_name: str = "remote_project"):
        """
        Initialize the remote filesystem.
        
        Args:
            socket_id: Socket.io session ID of the connected client
            project_name: Name to use for the project (since we don't know
                         the actual directory name on the client)
        """
        self._socket_id = socket_id
        self._project_name = project_name
        self._root_path = "."  # Remote root is always relative

    @property
    def root_path(self) -> str:
        return self._root_path

    @property
    def project_name(self) -> str:
        return self._project_name

    async def list_tree(self, root: str = ".") -> DirectoryTree:
        """
        List all files and directories recursively via socket.
        
        Expected client response:
        {
            "ok": true,
            "files": [
                {"path": "src/main.py", "name": "main.py", "is_dir": false, 
                 "is_file": true, "extension": ".py", "size": 1234},
                ...
            ]
        }
        or
        {
            "ok": false,
            "error": "Error message"
        }
        """
        try:
            result = await sio.call(
                "fs:list_tree",
                {"root": root},
                to=self._socket_id,
            )

            if not result.get("ok", False):
                return DirectoryTree(
                    root=root,
                    error=result.get("error", "Unknown error from client")
                )

            files = [
                FileInfo(
                    path=f["path"],
                    name=f["name"],
                    is_dir=f["is_dir"],
                    is_file=f["is_file"],
                    extension=f.get("extension", ""),
                    size=f.get("size", 0),
                )
                for f in result.get("files", [])
            ]

            return DirectoryTree(root=root, files=files)

        except Exception as e:
            logger.error(f"[RemoteFilesystem] list_tree failed: {e}")
            return DirectoryTree(root=root, error=f"Socket error: {e}")

    async def read_file(self, path: str) -> FileContent:
        """
        Read a single file's content via socket.
        
        Expected client response:
        {
            "ok": true,
            "content": "<base64 encoded content>"
        }
        """
        try:
            result = await sio.call(
                "fs:read_file",
                {"path": path},
                to=self._socket_id,
            )

            if not result.get("ok", False):
                return FileContent(
                    path=path,
                    error=result.get("error", "Unknown error from client")
                )

            content_b64 = result.get("content", "")
            content = base64.b64decode(content_b64)

            return FileContent(path=path, content=content)

        except Exception as e:
            logger.error(f"[RemoteFilesystem] read_file failed for {path}: {e}")
            return FileContent(path=path, error=f"Socket error: {e}")

    async def read_files_batch(self, paths: list[str]) -> BatchFileContent:
        """
        Read multiple files in a single socket call.
        
        Expected client response:
        {
            "ok": true,
            "files": {
                "path/to/file1.py": "<base64 content>",
                "path/to/file2.py": "<base64 content>"
            },
            "errors": {
                "path/to/missing.py": "File not found"
            }
        }
        """
        try:
            result = await sio.call(
                "fs:read_batch",
                {"paths": paths},
                to=self._socket_id,
            )

            if not result.get("ok", False):
                # Complete failure - mark all paths as errored
                return BatchFileContent(
                    errors={p: result.get("error", "Unknown error") for p in paths}
                )

            files = {}
            for path, content_b64 in result.get("files", {}).items():
                try:
                    files[path] = base64.b64decode(content_b64)
                except Exception as e:
                    result.setdefault("errors", {})[path] = f"Decode error: {e}"

            return BatchFileContent(
                files=files,
                errors=result.get("errors", {})
            )

        except Exception as e:
            logger.error(f"[RemoteFilesystem] read_files_batch failed: {e}")
            return BatchFileContent(
                errors={p: f"Socket error: {e}" for p in paths}
            )

    async def check_exists(self, paths: list[str]) -> ExistsResult:
        """
        Check if multiple paths exist via socket.
        
        Expected client response:
        {
            "ok": true,
            "results": {
                "path/to/file.py": true,
                "path/to/missing.py": false
            }
        }
        """
        try:
            result = await sio.call(
                "fs:check_exists",
                {"paths": paths},
                to=self._socket_id,
            )

            if not result.get("ok", False):
                return ExistsResult(
                    error=result.get("error", "Unknown error from client")
                )

            return ExistsResult(results=result.get("results", {}))

        except Exception as e:
            logger.error(f"[RemoteFilesystem] check_exists failed: {e}")
            return ExistsResult(error=f"Socket error: {e}")

    async def get_file_info(self, path: str) -> FileInfo | None:
        """
        Get information about a single file.
        
        This is implemented by listing the tree and finding the file.
        For efficiency, clients could implement fs:get_info event.
        """
        try:
            # Try direct info call first (optional client implementation)
            result = await sio.call(
                "fs:get_info",
                {"path": path},
                to=self._socket_id,
            )

            if result.get("ok", False) and result.get("info"):
                info = result["info"]
                return FileInfo(
                    path=info["path"],
                    name=info["name"],
                    is_dir=info["is_dir"],
                    is_file=info["is_file"],
                    extension=info.get("extension", ""),
                    size=info.get("size", 0),
                )

            return None

        except Exception as e:
            # fs:get_info not implemented by client, return None
            logger.debug(f"[RemoteFilesystem] get_file_info not available: {e}")
            return None
