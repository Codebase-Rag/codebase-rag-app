"""Filesystem abstraction for local and remote file operations."""

from .protocol import (
    BatchFileContent,
    DirectoryTree,
    ExistsResult,
    FileContent,
    FileInfo,
    FilesystemInterface,
)
from .local import LocalFilesystem
from .remote import RemoteFilesystem
from .uploaded import UploadedFilesystem

__all__ = [
    # Protocol and data classes
    "FilesystemInterface",
    "FileInfo",
    "DirectoryTree",
    "FileContent",
    "BatchFileContent",
    "ExistsResult",
    # Implementations
    "LocalFilesystem",
    "RemoteFilesystem",
    "UploadedFilesystem",
]
