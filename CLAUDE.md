# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MiroFish is a multi-agent AI prediction engine that creates digital simulations to forecast trends. It maps real-world data into parallel digital worlds where autonomous agents interact and evolve on simulated social platforms (Twitter/Reddit). Built on the CAMEL-AI/OASIS framework with Zep Cloud for agent memory.

## Development Commands

```bash
# Install all dependencies (frontend + backend)
npm run setup:all

# Start both frontend & backend concurrently
npm run dev

# Start individually
npm run backend    # Flask server on :5001
npm run frontend   # Vite dev server on :3000 (proxies /api/* to :5001)

# Build frontend for production
npm run build
```

Backend uses **uv** for Python dependency management:
```bash
cd backend && uv sync           # Install Python deps
cd backend && uv run python run.py  # Run backend directly
```

Tests (pytest is installed but no test suite exists yet):
```bash
cd backend && uv run pytest
```

## Architecture

**Frontend**: Vue 3 + Vite + D3.js for graph visualization. Dev server on port 3000.
**Backend**: Flask (Python 3.11+) with blueprints. Runs on port 5001.

### Backend Structure

- `backend/app/__init__.py` — Flask app factory (`create_app`), registers blueprints, enables CORS
- `backend/app/config.py` — All configuration from `.env`. Auto-detects LLM provider (OpenAI, Anthropic, Qwen-compatible)
- `backend/app/api/` — Three Flask blueprints:
  - `graph.py` (`/api/graph`) — Ontology extraction, graph building, graph data retrieval
  - `simulation.py` (`/api/simulation`) — Setup, execution, progress tracking
  - `report.py` (`/api/report`) — Report generation and interactive Q&A
- `backend/app/services/` — Core business logic:
  - `ontology_generator.py` — Extracts entities/relationships from documents via LLM
  - `graph_builder.py` — Builds knowledge graphs (GraphRAG) in Zep Cloud
  - `oasis_profile_generator.py` — Generates AI agent profiles from entities
  - `simulation_config_generator.py` — Creates platform-specific simulation configs
  - `simulation_runner.py` — Executes simulations with IPC for parallelization
  - `simulation_manager.py` — Manages simulation lifecycle & state
  - `report_agent.py` — AI agent for analysis report generation
  - `zep_*.py` — Zep Cloud integration (memory graphs, entity reading, tools)
  - `text_processor.py` — Text chunking with configurable size/overlap
- `backend/app/utils/` — Shared utilities:
  - `llm_client.py` — LLM provider abstraction (OpenAI/Anthropic/compatible APIs)
  - `file_parser.py` — PDF/TXT/MD parsing with encoding detection
  - `retry.py` — Retry decorator for resilient API calls
- `backend/scripts/` — Standalone simulation runners (Twitter, Reddit, parallel)

### Frontend Structure

- `frontend/src/views/` — Route views following the 5-step workflow (Home → Process → Simulation → Report → Interaction)
- `frontend/src/components/` — Step components (Step1GraphBuild through Step5Interaction), GraphPanel (D3 visualization), HistoryDatabase
- `frontend/src/api/` — Axios clients for graph, simulation, and report APIs
- `frontend/src/store/pendingUpload.js` — File upload state management

### 5-Step Workflow

1. **Graph Build** — Upload documents → extract ontology → build knowledge graph
2. **Environment Setup** — Generate agent profiles and simulation config
3. **Simulation** — Run agents on simulated social platforms with memory
4. **Report** — Generate analysis reports from simulation results
5. **Interaction** — Deep Q&A with the report agent

## Key Technical Details

- LLM provider is auto-detected from `LLM_BASE_URL`/`LLM_MODEL_NAME` in config — supports OpenAI, Anthropic Claude, Alibaba Qwen, and any OpenAI-compatible API
- Reasoning model output (e.g., `<think>` tags, markdown code fences) is stripped from content fields to prevent parse errors
- Zep Cloud is used for persistent graph-based agent memory with pagination support
- Simulations run in separate processes via IPC; data stored in `backend/uploads/simulations/`
- File uploads limited to 50MB; supports PDF, MD, TXT
- All JSON responses use UTF-8 encoding (Chinese language support)

## Environment Setup

Copy `.env.example` to `.env` and configure:
- `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_NAME` — Required for LLM calls
- `ZEP_API_KEY` — Required for Zep Cloud memory management
- Optional `LLM_BOOST_*` — Secondary LLM for acceleration
