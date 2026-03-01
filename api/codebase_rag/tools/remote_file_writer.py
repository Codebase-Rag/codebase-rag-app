from pathlib import Path

from loguru import logger
from pydantic import BaseModel
from pydantic_ai import Tool
from sockets.server import sio


class FileCreationResult(BaseModel):
    """Data model for file creation results."""

    file_path: str
    success: bool = True
    error_message: str | None = None


class RemoteFileWriter:
    """Service to write file content to the filesystem."""

    def __init__(self, socket_id: str):
        self.socket_id = socket_id

    async def create_file(self, file_path: str, content: str) -> FileCreationResult:
        """Creates or overwrites a file with the given content."""
        logger.info(f"[FileWriter] Creating file: {file_path}")
        try:
            res = await sio.call(
                "file:write", 
                {"file_path": file_path, "content": content},
                to=self.socket_id,
            )
            if not res["ok"]:
                err_msg = f"Error creating file {file_path}: {res["error"]}"
                logger.error(err_msg)
                return FileCreationResult(
                    file_path=file_path, success=False, error_message=err_msg
                )
                
            logger.info(
                f"[FileWriter] Successfully wrote {len(content)} characters to {file_path}"
            )
            return FileCreationResult(file_path=file_path)
        except ValueError:
            err_msg = f"Security risk: Attempted to create file outside of project root: {file_path}"
            logger.error(err_msg)
            return FileCreationResult(
                file_path=file_path, success=False, error_message=err_msg
            )
        except Exception as e:
            err_msg = f"Error creating file {file_path}: {e}"
            logger.error(err_msg)
            return FileCreationResult(
                file_path=file_path, success=False, error_message=err_msg
            )


def create_file_writer_tool(file_writer: RemoteFileWriter) -> Tool:
    """Factory function to create the file writer tool."""

    async def create_new_file(file_path: str, content: str) -> FileCreationResult:
        """
        Creates a new file with the specified content.

        IMPORTANT: Before using this tool, you MUST check if the file already exists using
        the file reader or directory listing tools. If the file exists, use edit_existing_file
        instead to preserve existing content and show diffs.

        If the file already exists, it will be completely overwritten WITHOUT showing any diff.
        Use this ONLY for creating entirely new files, not for modifying existing ones.
        For modifying existing files with diff preview, use edit_existing_file instead.
        """
        return await file_writer.create_file(file_path, content)

    return Tool(
        function=create_new_file,
        description="Creates a new file with content. IMPORTANT: Check file existence first! Overwrites completely WITHOUT showing diff. Use only for new files, not existing file modifications.",
    )
