"""In-memory filesystem implementation for uploaded file data."""

from .protocol import (
    BatchFileContent,
    DirectoryTree,
    ExistsResult,
    FileContent,
    FileInfo,
    FilesystemInterface,
)


class UploadedFilesystem(FilesystemInterface):
    """
    Filesystem implementation that works with pre-uploaded file data.
    
    This is used when the frontend sends all files upfront via HTTP POST,
    rather than fetching them on-demand via socket callbacks.
    """

    def __init__(self, project_name: str, files: list[dict]):
        """
        Initialize with uploaded file data.
        
        Args:
            project_name: Name of the project
            files: List of file info dicts with keys:
                - path: str (relative path)
                - name: str (file/dir name)
                - is_dir: bool
                - is_file: bool
                - content: bytes | None (file content, None for directories)
                - extension: str (optional)
                - size: int (optional)
        """
        self._project_name = project_name
        self._root_path = "."
        
        # Build lookup structures
        self._files: dict[str, FileInfo] = {}
        self._contents: dict[str, bytes] = {}
        
        for f in files:
            path = f["path"]
            info = FileInfo(
                path=path,
                name=f["name"],
                is_dir=f.get("is_dir", False),
                is_file=f.get("is_file", True),
                extension=f.get("extension", ""),
                size=f.get("size", 0),
            )
            self._files[path] = info
            
            if f.get("content") is not None:
                self._contents[path] = f["content"]

    @property
    def root_path(self) -> str:
        return self._root_path

    @property
    def project_name(self) -> str:
        return self._project_name

    async def list_tree(self, root: str = ".") -> DirectoryTree:
        """Return all files (already have them in memory)."""
        files = list(self._files.values())
        return DirectoryTree(root=root, files=files)

    async def read_file(self, path: str) -> FileContent:
        """Read file from memory."""
        if path not in self._contents:
            if path in self._files and self._files[path].is_dir:
                return FileContent(path=path, error=f"'{path}' is a directory")
            return FileContent(path=path, error=f"File not found: {path}")
        
        return FileContent(path=path, content=self._contents[path])

    async def read_files_batch(self, paths: list[str]) -> BatchFileContent:
        """Read multiple files from memory."""
        files = {}
        errors = {}
        
        for path in paths:
            if path in self._contents:
                files[path] = self._contents[path]
            elif path in self._files and self._files[path].is_dir:
                errors[path] = f"'{path}' is a directory"
            else:
                errors[path] = f"File not found: {path}"
        
        return BatchFileContent(files=files, errors=errors)

    async def check_exists(self, paths: list[str]) -> ExistsResult:
        """Check if paths exist in memory."""
        results = {path: path in self._files for path in paths}
        return ExistsResult(results=results)

    async def get_file_info(self, path: str) -> FileInfo | None:
        """Get file info from memory."""
        return self._files.get(path)
