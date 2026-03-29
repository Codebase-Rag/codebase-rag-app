"""
Remote Graph Updater - Graph ingestion with filesystem abstraction.

This module provides graph ingestion that works with remote filesystems
by using the FilesystemInterface abstraction instead of direct pathlib calls.
"""

from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Any

from loguru import logger
from tree_sitter import Node, Parser

from core.config import IGNORE_PATTERNS

from .filesystem import (
    DirectoryTree,
    FileInfo,
    FilesystemInterface,
)
from .language_config import get_language_config, LANGUAGE_FQN_CONFIGS
from .parser_loader import load_parsers
from .parsers.factory import ProcessorFactory
from .services.graph_service import MemgraphIngestor
from .utils.dependencies import has_semantic_dependencies


class RemoteFunctionRegistryTrie:
    """Trie data structure for function qualified name lookups."""

    def __init__(self) -> None:
        self.root: dict[str, Any] = {}
        self._entries: dict[str, str] = {}

    def insert(self, qualified_name: str, func_type: str) -> None:
        """Insert a function into the trie."""
        self._entries[qualified_name] = func_type
        parts = qualified_name.split(".")
        current = self.root

        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]

        current["__type__"] = func_type
        current["__qn__"] = qualified_name

    def get(self, qualified_name: str, default: str | None = None) -> str | None:
        """Get function type by exact qualified name."""
        return self._entries.get(qualified_name, default)

    def __contains__(self, qualified_name: str) -> bool:
        return qualified_name in self._entries

    def __getitem__(self, qualified_name: str) -> str:
        return self._entries[qualified_name]

    def __setitem__(self, qualified_name: str, func_type: str) -> None:
        self.insert(qualified_name, func_type)

    def keys(self):
        return self._entries.keys()

    def items(self):
        return self._entries.items()

    def __len__(self) -> int:
        return len(self._entries)


class RemoteBoundedASTCache:
    """Memory-aware AST cache with automatic cleanup."""

    def __init__(self, max_entries: int = 1000):
        self.cache: OrderedDict[str, tuple[Node, str]] = OrderedDict()
        self.max_entries = max_entries

    def __setitem__(self, key: str, value: tuple[Node, str]) -> None:
        if key in self.cache:
            del self.cache[key]
        self.cache[key] = value
        while len(self.cache) > self.max_entries:
            self.cache.popitem(last=False)

    def __getitem__(self, key: str) -> tuple[Node, str]:
        value = self.cache[key]
        self.cache.move_to_end(key)
        return value

    def __contains__(self, key: str) -> bool:
        return key in self.cache

    def items(self):
        return self.cache.items()


class RemoteGraphUpdater:
    """
    Graph updater that works with remote filesystems.
    
    Unlike the standard GraphUpdater which uses pathlib directly, this
    implementation uses the FilesystemInterface abstraction to fetch
    files over the network.
    
    The ingestion process:
    1. Fetch directory tree from remote client
    2. Identify packages and folders from tree metadata
    3. Batch-fetch source files for parsing
    4. Parse ASTs and extract definitions
    5. Process function calls
    6. Generate embeddings (optional)
    """

    def __init__(
        self,
        ingestor: MemgraphIngestor,
        filesystem: FilesystemInterface,
        parsers: dict[str, Parser] | None = None,
        queries: dict[str, Any] | None = None,
    ):
        """
        Initialize the remote graph updater.
        
        Args:
            ingestor: Memgraph database connection
            filesystem: Filesystem interface (local or remote)
            parsers: Pre-loaded Tree-sitter parsers (loaded if not provided)
            queries: Pre-loaded queries (loaded if not provided)
        """
        self.ingestor = ingestor
        self.filesystem = filesystem
        self.project_name = filesystem.project_name
        
        # Load parsers and queries if not provided
        if parsers is None or queries is None:
            loaded_parsers, loaded_queries = load_parsers()
            self.parsers = parsers or loaded_parsers
            self.queries = queries or loaded_queries
        else:
            self.parsers = parsers
            self.queries = queries
        
        self.queries = self._prepare_queries_with_parsers(self.queries, self.parsers)
        
        # State tracking
        self.function_registry = RemoteFunctionRegistryTrie()
        self.simple_name_lookup: dict[str, set[str]] = defaultdict(set)
        self.ast_cache = RemoteBoundedASTCache(max_entries=1000)
        self.structural_elements: dict[str, str | None] = {}
        self.ignore_dirs = IGNORE_PATTERNS
        
        # Cache the directory tree
        self._tree: DirectoryTree | None = None

    def _prepare_queries_with_parsers(
        self, queries: dict[str, Any], parsers: dict[str, Parser]
    ) -> dict[str, Any]:
        """Add parser references to query objects."""
        updated_queries = {}
        for lang, query_data in queries.items():
            if lang in parsers:
                updated_queries[lang] = {**query_data, "parser": parsers[lang]}
            else:
                updated_queries[lang] = query_data
        return updated_queries

    def _should_skip(self, path: str) -> bool:
        """Check if path should be skipped based on ignore patterns."""
        parts = Path(path).parts
        return any(part in self.ignore_dirs for part in parts)

    def _is_dependency_file(self, file_name: str, extension: str) -> bool:
        """Check if a file is a dependency file."""
        dependency_files = {
            "pyproject.toml",
            "requirements.txt",
            "package.json",
            "cargo.toml",
            "go.mod",
            "gemfile",
            "composer.json",
        }
        if file_name.lower() in dependency_files:
            return True
        if extension.lower() == ".csproj":
            return True
        return False

    async def run(self) -> None:
        """Orchestrate the parsing and ingestion process."""
        logger.info(f"Starting remote graph ingestion for project: {self.project_name}")
        
        # Ensure project node exists
        self.ingestor.ensure_node_batch("Project", {"name": self.project_name})
        
        # Fetch directory tree
        logger.info("--- Fetching directory tree from remote ---")
        self._tree = await self.filesystem.list_tree()
        
        if not self._tree.ok:
            logger.error(f"Failed to fetch directory tree: {self._tree.error}")
            raise RuntimeError(f"Failed to fetch directory tree: {self._tree.error}")
        
        logger.info(f"Received {len(self._tree.files)} files/directories")
        
        # Pass 1: Identify packages and folders
        logger.info("--- Pass 1: Identifying Packages and Folders ---")
        await self._identify_structure()
        
        # Pass 2: Process files
        logger.info("--- Pass 2: Processing Files and Extracting Definitions ---")
        await self._process_files()
        
        # Pass 3: Process function calls
        logger.info(f"--- Found {len(self.function_registry)} functions/methods ---")
        logger.info("--- Pass 3: Processing Function Calls ---")
        self._process_function_calls()
        
        # Flush all data
        logger.info("--- Flushing data to database ---")
        self.ingestor.flush_all()
        
        # Pass 4: Embeddings (optional)
        await self._generate_semantic_embeddings()
        
        logger.info("--- Remote graph ingestion complete ---")

    async def _identify_structure(self) -> None:
        """Pass 1: Identify packages and folders from the directory tree."""
        if not self._tree:
            return
        
        # Collect package indicators from all language configs
        package_indicators: set[str] = set()
        for lang_name, lang_queries in self.queries.items():
            if "config" in lang_queries:
                lang_config = lang_queries["config"]
                package_indicators.update(lang_config.package_indicators)
        
        # Get all directories
        directories = {
            f.path for f in self._tree.files 
            if f.is_dir and not self._should_skip(f.path)
        }
        directories.add(".")  # Include root
        
        # Build a map of directory -> contained files for indicator checking
        dir_contents: dict[str, set[str]] = defaultdict(set)
        for f in self._tree.files:
            parent = str(Path(f.path).parent)
            dir_contents[parent].add(f.name)
        
        # Process directories in deterministic order
        for dir_path in sorted(directories):
            if self._should_skip(dir_path):
                continue
            
            relative_root = Path(dir_path)
            parent_rel_path = relative_root.parent
            parent_path_str = str(parent_rel_path) if parent_rel_path != Path(".") else "."
            parent_container_qn = self.structural_elements.get(parent_path_str)
            
            # Check for package indicators
            is_package = False
            dir_files = dir_contents.get(dir_path, set())
            for indicator in package_indicators:
                if indicator in dir_files:
                    is_package = True
                    break
            
            dir_name = relative_root.name if dir_path != "." else self.project_name
            
            if is_package:
                if dir_path == ".":
                    package_qn = self.project_name
                else:
                    package_qn = ".".join([self.project_name] + list(relative_root.parts))
                
                self.structural_elements[dir_path] = package_qn
                logger.info(f"  Identified Package: {package_qn}")
                
                self.ingestor.ensure_node_batch(
                    "Package",
                    {
                        "qualified_name": package_qn,
                        "name": dir_name,
                        "path": dir_path,
                    },
                )
                
                parent_label, parent_key, parent_val = self._get_parent_info(
                    parent_path_str, parent_container_qn
                )
                self.ingestor.ensure_relationship_batch(
                    (parent_label, parent_key, parent_val),
                    "CONTAINS_PACKAGE",
                    ("Package", "qualified_name", package_qn),
                )
            elif dir_path != ".":
                self.structural_elements[dir_path] = None
                logger.info(f"  Identified Folder: {dir_path}")
                
                self.ingestor.ensure_node_batch(
                    "Folder", {"path": dir_path, "name": dir_name}
                )
                
                parent_label, parent_key, parent_val = self._get_parent_info(
                    parent_path_str, parent_container_qn
                )
                self.ingestor.ensure_relationship_batch(
                    (parent_label, parent_key, parent_val),
                    "CONTAINS_FOLDER",
                    ("Folder", "path", dir_path),
                )

    def _get_parent_info(
        self, parent_path: str, parent_container_qn: str | None
    ) -> tuple[str, str, str]:
        """Get parent node info for relationship creation."""
        if parent_path == ".":
            return ("Project", "name", self.project_name)
        elif parent_container_qn:
            return ("Package", "qualified_name", parent_container_qn)
        else:
            return ("Folder", "path", parent_path)

    async def _process_files(self) -> None:
        """Pass 2: Process all source files."""
        if not self._tree:
            return
        
        # Collect files to process by language
        files_by_lang: dict[str, list[FileInfo]] = defaultdict(list)
        dependency_files: list[FileInfo] = []
        generic_files: list[FileInfo] = []
        
        for f in self._tree.files:
            if not f.is_file or self._should_skip(f.path):
                continue
            
            lang_config = get_language_config(f.extension)
            if lang_config and lang_config.name in self.parsers:
                files_by_lang[lang_config.name].append(f)
            elif self._is_dependency_file(f.name, f.extension):
                dependency_files.append(f)
            else:
                generic_files.append(f)
        
        # Batch fetch and process source files by language
        for lang_name, files in files_by_lang.items():
            logger.info(f"  Processing {len(files)} {lang_name} files")
            
            # Batch fetch file contents
            paths = [f.path for f in files]
            batch_result = await self.filesystem.read_files_batch(paths)
            
            for file_info in files:
                content = batch_result.files.get(file_info.path)
                if content is None:
                    error = batch_result.errors.get(file_info.path, "Unknown error")
                    logger.warning(f"Failed to read {file_info.path}: {error}")
                    continue
                
                self._process_source_file(file_info, content, lang_name)
                self._process_generic_file(file_info)
        
        # Process dependency files
        if dependency_files:
            logger.info(f"  Processing {len(dependency_files)} dependency files")
            paths = [f.path for f in dependency_files]
            batch_result = await self.filesystem.read_files_batch(paths)
            
            for file_info in dependency_files:
                content = batch_result.files.get(file_info.path)
                if content:
                    self._process_dependency_file(file_info, content)
                self._process_generic_file(file_info)
        
        # Process generic files (just create nodes)
        for file_info in generic_files:
            self._process_generic_file(file_info)

    def _process_source_file(
        self, file_info: FileInfo, content: bytes, language: str
    ) -> None:
        """Process a source file and cache its AST."""
        logger.debug(f"Parsing {language}: {file_info.path}")
        
        try:
            lang_queries = self.queries.get(language)
            if not lang_queries:
                return
            
            parser = lang_queries.get("parser")
            if not parser:
                return
            
            # Parse AST
            tree = parser.parse(content)
            root_node = tree.root_node
            
            # Create module qualified name
            relative_path = Path(file_info.path)
            module_qn = ".".join(
                [self.project_name] + list(relative_path.with_suffix("").parts)
            )
            
            if file_info.name == "__init__.py":
                module_qn = ".".join(
                    [self.project_name] + list(relative_path.parent.parts)
                )
            elif file_info.name == "mod.rs":
                module_qn = ".".join(
                    [self.project_name] + list(relative_path.parent.parts)
                )
            
            # Create module node
            self.ingestor.ensure_node_batch(
                "Module",
                {
                    "qualified_name": module_qn,
                    "name": file_info.name,
                    "path": file_info.path,
                },
            )
            
            # Link to parent
            parent_path = str(relative_path.parent)
            if parent_path == ".":
                parent_path = "."
            parent_container_qn = self.structural_elements.get(parent_path)
            parent_label, parent_key, parent_val = self._get_parent_info(
                parent_path, parent_container_qn
            )
            
            self.ingestor.ensure_relationship_batch(
                (parent_label, parent_key, parent_val),
                "CONTAINED_IN",
                ("Module", "qualified_name", module_qn),
            )
            
            # Extract definitions (functions, classes, methods)
            self._extract_definitions(
                root_node, content, module_qn, file_info.path, language, lang_queries
            )
            
            # Cache AST for call processing
            self.ast_cache[file_info.path] = (root_node, language)
            
        except Exception as e:
            logger.error(f"Error processing {file_info.path}: {e}")

    def _extract_definitions(
        self,
        root_node: Node,
        source_bytes: bytes,
        module_qn: str,
        file_path: str,
        language: str,
        lang_queries: dict[str, Any],
    ) -> None:
        """Extract function, class, and method definitions from AST."""
        # Get queries
        function_query = lang_queries.get("function")
        class_query = lang_queries.get("class")
        
        if not function_query and not class_query:
            return
        
        # Extract functions
        if function_query:
            for match in function_query.matches(root_node):
                for capture in match[1]:
                    node = capture[0]
                    func_name = self._get_node_name(node, source_bytes, language)
                    if func_name:
                        func_qn = f"{module_qn}.{func_name}"
                        self.function_registry[func_qn] = "Function"
                        self.simple_name_lookup[func_name].add(func_qn)
                        
                        self.ingestor.ensure_node_batch(
                            "Function",
                            {
                                "qualified_name": func_qn,
                                "name": func_name,
                                "start_line": node.start_point[0] + 1,
                                "end_line": node.end_point[0] + 1,
                            },
                        )
                        self.ingestor.ensure_relationship_batch(
                            ("Module", "qualified_name", module_qn),
                            "DEFINES",
                            ("Function", "qualified_name", func_qn),
                        )
        
        # Extract classes and their methods
        if class_query:
            for match in class_query.matches(root_node):
                for capture in match[1]:
                    node = capture[0]
                    class_name = self._get_node_name(node, source_bytes, language)
                    if class_name:
                        class_qn = f"{module_qn}.{class_name}"
                        self.function_registry[class_qn] = "Class"
                        self.simple_name_lookup[class_name].add(class_qn)
                        
                        self.ingestor.ensure_node_batch(
                            "Class",
                            {
                                "qualified_name": class_qn,
                                "name": class_name,
                                "start_line": node.start_point[0] + 1,
                                "end_line": node.end_point[0] + 1,
                            },
                        )
                        self.ingestor.ensure_relationship_batch(
                            ("Module", "qualified_name", module_qn),
                            "DEFINES",
                            ("Class", "qualified_name", class_qn),
                        )
                        
                        # Extract methods within the class
                        self._extract_methods(
                            node, source_bytes, class_qn, language, lang_queries
                        )

    def _extract_methods(
        self,
        class_node: Node,
        source_bytes: bytes,
        class_qn: str,
        language: str,
        lang_queries: dict[str, Any],
    ) -> None:
        """Extract methods from a class node."""
        function_query = lang_queries.get("function")
        if not function_query:
            return
        
        for match in function_query.matches(class_node):
            for capture in match[1]:
                node = capture[0]
                method_name = self._get_node_name(node, source_bytes, language)
                if method_name:
                    method_qn = f"{class_qn}.{method_name}"
                    self.function_registry[method_qn] = "Method"
                    self.simple_name_lookup[method_name].add(method_qn)
                    
                    self.ingestor.ensure_node_batch(
                        "Method",
                        {
                            "qualified_name": method_qn,
                            "name": method_name,
                            "start_line": node.start_point[0] + 1,
                            "end_line": node.end_point[0] + 1,
                        },
                    )
                    self.ingestor.ensure_relationship_batch(
                        ("Class", "qualified_name", class_qn),
                        "CONTAINS",
                        ("Method", "qualified_name", method_qn),
                    )

    def _get_node_name(self, node: Node, source_bytes: bytes, language: str) -> str | None:
        """Extract the name from an AST node."""
        # Look for name/identifier child
        for child in node.children:
            if child.type in ("identifier", "name", "property_identifier"):
                return source_bytes[child.start_byte:child.end_byte].decode("utf-8")
        return None

    def _process_dependency_file(self, file_info: FileInfo, content: bytes) -> None:
        """Process a dependency file (pyproject.toml, package.json, etc.)."""
        # TODO: Implement dependency extraction
        # For now, just log that we found it
        logger.debug(f"Found dependency file: {file_info.path}")

    def _process_generic_file(self, file_info: FileInfo) -> None:
        """Create File node and relationship for any file."""
        relative_path = Path(file_info.path)
        parent_path = str(relative_path.parent)
        if parent_path == ".":
            parent_path = "."
        
        parent_container_qn = self.structural_elements.get(parent_path)
        parent_label, parent_key, parent_val = self._get_parent_info(
            parent_path, parent_container_qn
        )
        
        self.ingestor.ensure_node_batch(
            "File",
            {
                "path": file_info.path,
                "name": file_info.name,
                "extension": file_info.extension,
            },
        )
        
        self.ingestor.ensure_relationship_batch(
            (parent_label, parent_key, parent_val),
            "CONTAINS_FILE",
            ("File", "path", file_info.path),
        )

    def _process_function_calls(self) -> None:
        """Pass 3: Process function calls from cached ASTs."""
        for file_path, (root_node, language) in list(self.ast_cache.items()):
            lang_queries = self.queries.get(language)
            if not lang_queries:
                continue
            
            call_query = lang_queries.get("call")
            if not call_query:
                continue
            
            # Note: Full call resolution requires more context
            # This is a simplified version
            logger.debug(f"Processing calls in {file_path}")

    async def _generate_semantic_embeddings(self) -> None:
        """Pass 4: Generate semantic embeddings for functions/methods."""
        if not has_semantic_dependencies():
            logger.info("Semantic dependencies not available, skipping embeddings")
            return
        
        # TODO: Implement semantic embedding generation
        # Would need to query the database and generate embeddings
        logger.info("Semantic embedding generation not yet implemented for remote")
