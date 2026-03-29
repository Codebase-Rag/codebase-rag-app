"""Filesystem abstraction protocol for local and remote file operations."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class FileInfo:
    """Information about a file or directory in the filesystem."""

    path: str  # Relative path from root
    name: str  # File/directory name
    is_dir: bool
    is_file: bool
    extension: str = ""  # File extension (e.g., ".py")
    size: int = 0  # File size in bytes (0 for directories)

    @classmethod
    def from_path(cls, path: Path, root: Path) -> "FileInfo":
        """Create FileInfo from a pathlib.Path object."""
        relative = path.relative_to(root)
        return cls(
            path=str(relative),
            name=path.name,
            is_dir=path.is_dir(),
            is_file=path.is_file(),
            extension=path.suffix if path.is_file() else "",
            size=path.stat().st_size if path.is_file() else 0,
        )


@dataclass
class DirectoryTree:
    """Result of listing a directory tree."""

    root: str
    files: list[FileInfo] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class FileContent:
    """Result of reading a file."""

    path: str
    content: bytes | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.content is not None


@dataclass
class BatchFileContent:
    """Result of reading multiple files."""

    files: dict[str, bytes] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


@dataclass
class ExistsResult:
    """Result of checking if paths exist."""

    results: dict[str, bool] = field(default_factory=dict)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@runtime_checkable
class FilesystemInterface(Protocol):
    """
    Protocol defining the filesystem operations needed for graph ingestion.
    
    Implementations can work with local filesystem (pathlib) or remote
    filesystem (socket.io proxy to client).
    """

    async def list_tree(self, root: str = ".") -> DirectoryTree:
        """
        List all files and directories under root recursively.
        
        This is equivalent to Path.rglob("*") but returns structured data
        suitable for network transport.
        
        Args:
            root: Root directory to start listing from (default: ".")
            
        Returns:
            DirectoryTree containing all files and directories
        """
        ...

    async def read_file(self, path: str) -> FileContent:
        """
        Read the content of a single file.
        
        Args:
            path: Path to the file (relative to root)
            
        Returns:
            FileContent with binary content or error
        """
        ...

    async def read_files_batch(self, paths: list[str]) -> BatchFileContent:
        """
        Read multiple files in a single operation.
        
        This is the primary method for efficient network transport.
        Implementations should batch these into a single round-trip.
        
        Args:
            paths: List of file paths to read
            
        Returns:
            BatchFileContent with file contents and any errors
        """
        ...

    async def check_exists(self, paths: list[str]) -> ExistsResult:
        """
        Check if multiple paths exist.
        
        Used for package indicator detection (e.g., checking if __init__.py exists).
        
        Args:
            paths: List of paths to check
            
        Returns:
            ExistsResult with boolean for each path
        """
        ...

    async def get_file_info(self, path: str) -> FileInfo | None:
        """
        Get information about a single file or directory.
        
        Args:
            path: Path to get info for
            
        Returns:
            FileInfo or None if path doesn't exist
        """
        ...

    @property
    def root_path(self) -> str:
        """Return the root path this filesystem is operating on."""
        ...

    @property
    def project_name(self) -> str:
        """Return the project name (typically the root directory name)."""
        ...
