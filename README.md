# Codebase RAG

A terminal-based AI coding assistant that uses Retrieval-Augmented Generation (RAG) and Abstract Syntax Tree (AST) analysis to provide context-aware code review and modification. It parses your codebase into a knowledge graph, then gives an LLM precise, structural context when answering questions or making edits.

## Design

### How It Works

```
┌──────────────┐       Socket.IO / REST        ┌──────────────────┐
│   React Ink   │  ◄──────────────────────────►  │   FastAPI + SIO  │
│   Frontend    │                                │   Backend        │
└──────────────┘                                └────────┬─────────┘
                                                         │
                                       ┌─────────────────┼─────────────────┐
                                       │                 │                 │
                                  ┌────▼────┐     ┌──────▼──────┐   ┌─────▼─────┐
                                  │Memgraph │     │   Redis     │   │ Postgres  │
                                  │ (Graph) │     │  (Cache)    │   │(Sessions) │
                                  └─────────┘     └─────────────┘   └───────────┘
```

**Backend** — The core of the system lives in `api/`. It uses [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) to parse source code into ASTs, extracting structural entities (modules, classes, functions, methods, imports, call relationships) across multiple languages (Python, TypeScript, JavaScript, Java, C++, Rust, Go, Lua, Scala). These entities and their relationships are ingested into a **Memgraph** knowledge graph.

When you ask a question, a RAG orchestrator:

1. Translates your natural-language query into a Cypher graph query to retrieve structurally relevant code (call chains, inheritance, imports).
2. Optionally performs semantic vector search for intent-based discovery.
3. Feeds the retrieved context to the LLM, which can then answer questions, review code, or propose edits — grounded in your actual codebase structure.

The backend also supports an **agent mode** with tools for file reading/writing, shell commands, directory listing, and document analysis, allowing the LLM to autonomously explore and modify code.

**Frontend** — A terminal UI built with [React Ink](https://github.com/vadimdemedes/ink). It connects to the backend over Socket.IO (for real-time file operations the backend delegates to the client) and REST (for queries). The TUI supports two modes — **Chat** for Q&A and **Agent** for autonomous code modifications with accept/reject review.

### Supported Languages

Python, JavaScript, TypeScript, Java, C++, Rust, Go, Lua, Scala.

## Prerequisites

- **Linux** environment (required)
- **Node.js** >= 16 and [**pnpm**](https://pnpm.io/)
- **Python** >= 3.12 and [**uv**](https://github.com/astral-sh/uv)
- **make**
- **Docker** and **Docker Compose** (for Memgraph, Redis, and Postgres)
- An LLM provider API key (Google, OpenAI, Vertex AI, or a local Ollama endpoint)

## Setup

### 1. Environment Variables

```bash
cp .env.example .env
```

Fill in your LLM provider API keys and any other settings in the `.env` file.

### 2. Start the Backend

Start the infrastructure services:

```bash
cd api
docker compose up -d     # starts Memgraph, Redis, and Postgres
```

Then start the API server:

```bash
cd api
uv sync                  # install Python dependencies
make                     # starts the FastAPI server on port 8000
```

You can also access the **Memgraph Lab** UI at `http://localhost:3000` to visually explore the knowledge graph.

### 3. Start the Frontend

```bash
# From the project root
pnpm install
pnpm run build
node dist/cli.js
```

## Usage

1. Launch the TUI with `node dist/cli.js`.
2. Select a mode — **Chat** or **Agent**.
3. Enter the path to your repository when prompted.
4. Start asking questions about your codebase or request code modifications.

### TUI Commands

| Command  | Description                              |
| -------- | ---------------------------------------- |
| `/help`  | Show available commands                  |
| `/clear` | Clear the conversation                   |
| `/quit`  | Leave the current session and reset      |
| `/exit`  | Exit the application                     |

In **Agent** mode, when the assistant proposes code edits, you'll be prompted to **accept** or **reject** the changes before they are applied.

## License

MIT
