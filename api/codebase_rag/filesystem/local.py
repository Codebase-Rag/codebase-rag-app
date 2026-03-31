"""Local filesystem implementation using pathlib."""

from pathlib import Path

from core.config import IGNORE_PATTERNS

from .protocol import (
    BatchFileContent,
    DirectoryTree,
    ExistsResult,
    FileContent,
    FileInfo,
    FilesystemInterface,
)


class LocalFilesystem(FilesystemInterface):
    """
    Local filesystem implementation using pathlib.
    
    This wraps standard pathlib operations to conform to the FilesystemInterface
    protocol, allowing the same code to work with both local and remote filesystems.
    """

    def __init__(self, root: Path | str):
        """
        Initialize the local filesystem.
        
        Args:
            root: Root directory path
        """
        self._root = Path(root).resolve()
        self._ignore_patterns = IGNORE_PATTERNS

    @property
    def root_path(self) -> str:
        return str(self._root)

    @property
    def project_name(self) -> str:
        return self._root.name

    def _should_skip(self, path: Path) -> bool:
        """Check if path should be skipped based on ignore patterns."""
        try:
            relative = path.relative_to(self._root)
            return any(part in self._ignore_patterns for part in relative.parts)
        except ValueError:
            return True

    async def list_tree(self, root: str = ".") -> DirectoryTree:
        """List all files and directories recursively."""
        try:
            root_path = self._root / root if root != "." else self._root
            if not root_path.exists():
                return DirectoryTree(
                    root=root,
                    error=f"Directory does not exist: {root}"
                )

            files: list[FileInfo] = []
            for path in root_path.rglob("*"):
                if not self._should_skip(path):
                    try:
                        files.append(FileInfo.from_path(path, self._root))
                    except (OSError, PermissionError) as e:
                        # Skip files we can't access
                        continue

            return DirectoryTree(root=root, files=files)
        except Exception as e:
            return DirectoryTree(root=root, error=str(e))

    async def read_file(self, path: str) -> FileContent:
        """Read a single file's content."""
        try:
            file_path = self._root / path
            if not file_path.exists():
                return FileContent(path=path, error=f"File not found: {path}")
            if not file_path.is_file():
                return FileContent(path=path, error=f"Not a file: {path}")
            
            content = file_path.read_bytes()
            return FileContent(path=path, content=content)
        except Exception as e:
            return FileContent(path=path, error=str(e))

    async def read_files_batch(self, paths: list[str]) -> BatchFileContent:
        """Read multiple files at once."""
        result = BatchFileContent()
        
        for path in paths:
            file_result = await self.read_file(path)
            if file_result.ok:
                result.files[path] = file_result.content  # type: ignore
            else:
                result.errors[path] = file_result.error or "Unknown error"
        
        return result

    async def check_exists(self, paths: list[str]) -> ExistsResult:
        """Check if multiple paths exist."""
        try:
            results = {}
            for path in paths:
                full_path = self._root / path
                results[path] = full_path.exists()
            return ExistsResult(results=results)
        except Exception as e:
            return ExistsResult(error=str(e))

    async def get_file_info(self, path: str) -> FileInfo | None:
        """Get information about a file or directory."""
        try:
            full_path = self._root / path
            if not full_path.exists():
                return None
            return FileInfo.from_path(full_path, self._root)
        except Exception:
            return None
