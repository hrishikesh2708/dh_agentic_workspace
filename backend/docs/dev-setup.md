# Dev Setup

How to get the local dev loop running, including **LangGraph Studio** for
visualising and stepping through the agent graph.

## Prerequisites

- Python 3.13
- [`uv`](https://docs.astral.sh/uv/) (`pip install uv`)
- Docker (for Postgres + Valkey + observability stack — optional for Studio,
  required for the full FastAPI app)
- A LangSmith account (free tier is fine) — needed to view traces.

## 1. Install dependencies

```bash
make install         # uv sync + pre-commit
```

## 2. Configure `.env.development`

Copy from `.env.example` if needed:

```bash
cp .env.example .env.development
```

Required keys for Studio + LangSmith tracing:

```env
LANGSMITH_TRACING_ENABLED=true
LANGSMITH_API_KEY="<your-langsmith-api-key>"  # from smith.langchain.com → Settings
LANGSMITH_PROJECT=dh_agent                # any project name; auto-created
LANGSMITH_ENDPOINT=https://api.smith.langchain.com

OPENAI_API_KEY="<your-openai-api-key>"    # for LLM calls
DEFAULT_LLM_MODEL=gpt-4o-mini
```

Postgres values are **only needed for `make dev`** (the FastAPI app). Studio
runs the graph against an in-memory checkpointer and does **not** require
Postgres to be up.

## 3. Run LangGraph Studio

```bash
make studio                      # defaults to port 2024
# or override:
make studio STUDIO_PORT=3024
```

Behind the scenes this runs:

```bash
uv run langgraph dev --port 2024
```

Once it starts you'll see a URL like:

```
🚀 API: http://127.0.0.1:2024
🎨 Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

Open the Studio URL in your browser. You should see the `agent` graph (the
current toy chat agent — replaced with the real mapping agent in Stage 1).

## 4. Verify LangSmith tracing

1. Open Studio, hit the graph with a sample input (e.g. "hello").
2. Open <https://smith.langchain.com> → your project (`dh_agent` by default).
3. You should see one new trace per Studio invocation, with full message
   history, tool calls, and timing.

If traces don't appear, check:

- `LANGSMITH_API_KEY` is set and not the placeholder
- `LANGSMITH_TRACING_ENABLED=true` in `.env.development`
- No corporate firewall blocking `api.smith.langchain.com`

## How it wires together

- `backend/langgraph.json` — Studio config; points at
  `app/core/langgraph/graph.py:make_studio_graph`.
- `make_studio_graph()` — a top-level async factory in `graph.py` that:
  1. Calls `langsmith_init()` to set `LANGSMITH_TRACING=true` env var.
  2. Builds the same `StateGraph` the production app uses.
  3. Compiles it **without** a checkpointer so the dev CLI can inject its
     in-memory one.

The same module also exposes a `agent: LangGraphAgent` singleton, which
later stages (CopilotKit middleware mount in Stage 3) will reuse.

## Other dev commands

```bash
make dev                # FastAPI server on :8000 (needs Postgres)
make lint               # ruff check
make typecheck          # pyright
make check              # lint + typecheck
make docker-up          # bring up Postgres + app via docker-compose
```
