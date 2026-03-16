# Proposal: Replace Zep Cloud with Local Graph Database

## Problem

MiroFish depends on Zep Cloud (`zep-cloud==3.13.0`) for knowledge graph storage, entity extraction, semantic search, and real-time graph updates during simulation. This means:

- Every deployment needs a Zep Cloud API key
- Graph data lives on a third-party cloud service
- Rate limits and latency from cloud API calls (the codebase has extensive 429-handling and retry logic)
- No offline or air-gapped usage possible

## Goal

Replace Zep Cloud with a self-hosted, local solution that can run alongside MiroFish in Docker Compose. The replacement should cover the same functional surface with minimal architectural changes.

---

## Recommended: Graphiti + Neo4j

**[Graphiti](https://github.com/getzep/graphiti)** is the open-source temporal knowledge graph library built by the Zep team. It uses Neo4j as its graph backend and provides the same conceptual model MiroFish already uses: episodes in → entities and edges extracted → graph queryable.

This is the closest replacement because MiroFish does not just need “memory.” It needs a first-class, queryable graph that can be:

- fully enumerated for D3 visualization
- filtered by entity type for agent/profile generation
- searched semantically for report generation
- updated incrementally during simulation
- isolated per `graph_id` so multiple projects do not bleed into each other

---

## Non-Negotiable Design Constraints

Any replacement needs to preserve these application-level guarantees, because the existing code relies on them heavily:

1. **`graph_id` isolation must remain explicit**
    MiroFish treats each graph as an isolated project artifact. Reads, searches, updates, and deletes must stay scoped to one graph. A replacement cannot use global `MATCH (n) DETACH DELETE n` style operations except in one-off development resets.

2. **Typed ontology parity must be preserved**
    The current pipeline does not just ingest text and accept whatever labels emerge. It generates a specific ontology, sets that ontology in the graph backend, and then downstream services assume those labels exist and are stable. The migration must preserve that contract, either through Graphiti prescribed types or a normalization layer after ingestion.

3. **Current JSON/API response shapes should stay stable**
    The frontend graph visualization, simulation prep, and report tooling already expect specific node/edge fields and temporal attributes. The migration should preserve those response shapes and swap the backend implementation underneath them.

4. **The system remains self-hosted, but not dependency-free**
    Neo4j removes the managed graph service dependency, but Graphiti still requires LLM, embedding, and reranking components. The proposal must account for that runtime explicitly.

### Why Graphiti is the closest fit

| Capability | Zep Cloud (current) | Graphiti + Neo4j |
|---|---|---|
| Graph creation | `client.graph.create()` | Neo4j + Graphiti, with explicit `graph_id` namespacing/filtering at the app layer |
| Ontology / schema | `client.graph.set_ontology()` with dynamic Pydantic models | Graphiti prescribed ontology via Pydantic models, or learned extraction plus post-normalization |
| Ingest text → extract entities | `client.graph.add_batch(episodes)` | `graphiti.add_episode(name, content, source)` |
| Check processing status | `client.graph.episode.get(uuid_)` polling | App-controlled ingestion flow; no separate cloud episode polling loop required |
| Semantic search | `client.graph.search(query, scope, reranker)` | `graphiti.search(query, num_results)` — hybrid BM25 + semantic |
| Get all nodes | `client.graph.node.get_by_graph_id()` paginated | Direct Cypher filtered by `graph_id` namespace |
| Get all edges | `client.graph.edge.get_by_graph_id()` paginated | Direct Cypher filtered by `graph_id` namespace |
| Get node by UUID | `client.graph.node.get(uuid_)` | Cypher lookup scoped by `graph_id` |
| Get node edges | `client.graph.node.get_entity_edges(node_uuid)` | Cypher traversal scoped by `graph_id` |
| Real-time updates | `client.graph.add(graph_id, type="text", data=text)` | `graphiti.add_episode(...)` |
| Temporal edges | `valid_at`, `invalid_at`, `expired_at` on edges | Built-in: edges have `created_at`, `valid_at`, `invalid_at`, `expired_at` |
| Delete graph | `client.graph.delete(graph_id)` | Cypher delete scoped by `graph_id` namespace |
| Self-hosted | No | Yes — Neo4j Community Edition (free, Docker) |

### Key advantages over Zep Cloud

1. **Full graph access** — Neo4j Cypher gives direct node/edge enumeration, the frontend graph visualization keeps working
2. **Same team, same model** — Graphiti was extracted from Zep's codebase; the entity/edge extraction and temporal model are the same
3. **No graph-service API throttling** — local Neo4j removes Zep Cloud rate limits, pagination utilities, and the cloud polling loop
4. **Temporal model continuity** — Graphiti edges preserve the same temporal concepts (`valid_at`, `invalid_at`, `expired_at`)
5. **Better control over deployment** — works in local Docker Compose and air-gapped environments

### Trade-offs

- **Adds Neo4j** as an infrastructure dependency (Docker container, ~500MB)
- **You still own the LLM runtime** — Graphiti ingestion/search still depends on LLM, embeddings, and reranking; removing Zep Cloud does not remove LLM provider rate limits
- **Graph isolation is now your responsibility** — the app must preserve `graph_id` boundaries explicitly in Cypher queries and delete operations
- **Migration effort is larger than a simple SDK swap** — this touches graph build/read/search/update, config validation, report tooling, simulation APIs, and service exports

---

## Required Design Decisions Before Implementation

### 1. Graph isolation strategy

This must be decided up front.

**Recommended approach:** store `graph_id` as an explicit namespace marker on every node/edge/episode written by the backend, and require every Cypher query to filter by that namespace.

Why this matters:

- MiroFish supports multiple projects and keeps `graph_id` in project state
- the current app assumes delete/read/search operations affect one graph, not the whole database
- Neo4j Community Edition is a poor fit for “one database per project,” so app-level namespacing is the safer default

This means the proposal should avoid examples like:

```cypher
MATCH (n) DETACH DELETE n
```

and use graph-scoped forms instead, for example:

```cypher
MATCH (n {graph_id: $graph_id})
DETACH DELETE n
```

### 2. Ontology preservation strategy

The current system generates a constrained ontology in `ontology_generator.py` and downstream code expects those types to exist as stable labels. The replacement should not treat `set_ontology()` as a no-op.

**Recommended approach:** keep the ontology generation stage and add an adapter that converts the ontology dict into Graphiti-compatible prescribed types or a deterministic post-ingestion label normalization step.

This preserves behavior relied on by:

- entity filtering for simulation prep
- persona/profile generation
- graph visualization legends
- report tools that group entities by type

### 3. Backend abstraction boundary

Do not scatter raw `Graphiti(...)`, Neo4j driver setup, and `asyncio.run(...)` calls across routes and services.

**Recommended approach:** add a small internal backend/factory layer such as `graph_backend.py` or `graphiti_factory.py` that is responsible for:

- creating the Neo4j driver
- configuring Graphiti clients from existing LLM settings
- exposing sync-friendly methods for Flask services
- centralizing graph namespace rules

This keeps the migration contained and makes it possible to test the replacement backend in isolation.

---

## File-by-file Migration Plan

### Infrastructure

**docker-compose.yml** — Add Neo4j service:

```yaml
neo4j:
  image: neo4j:5-community
  ports:
    - "7474:7474"   # Browser UI
    - "7687:7687"   # Bolt protocol
  environment:
    - NEO4J_AUTH=neo4j/mirofish_dev
    - NEO4J_PLUGINS=["apoc"]
  volumes:
    - neo4j_data:/data
    healthcheck:
        test: ["CMD", "wget", "-qO-", "http://localhost:7474"]
        interval: 10s
        timeout: 5s
        retries: 10
  restart: unless-stopped
```

**.env.example** — Replace Zep config:

```env
# Before
ZEP_API_KEY=

# After
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=mirofish_dev
NEO4J_DATABASE=neo4j
GRAPHITI_TELEMETRY_ENABLED=false
```

**backend/pyproject.toml** — Swap dependencies in the actual backend source of truth used by `uv sync`:

```diff
- zep-cloud==3.13.0
+ graphiti-core>=0.28
+ neo4j>=5.0
```

`requirements.txt` can be updated afterwards if you want it to remain as documentation or an alternate install path, but the active dev workflow is driven by `pyproject.toml` and `uv sync`.

**New file: `backend/app/services/graphiti_factory.py`**

Add a small service/factory responsible for creating:

- the Neo4j driver
- the Graphiti client
- the embedder/reranker/LLM clients derived from existing config
- sync wrappers around async Graphiti calls

### File: `backend/app/config.py`

Replace `ZEP_API_KEY` with Neo4j connection config and update validation:

```python
# Before
ZEP_API_KEY = os.getenv('ZEP_API_KEY', '')

# After
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', '')
NEO4J_DATABASE = os.getenv('NEO4J_DATABASE', 'neo4j')
```

Also update `Config.validate()` and all API-layer configuration checks so the app does not keep returning stale `ZEP_API_KEY is not configured` errors.

### File: `backend/app/utils/zep_paging.py` → DELETE

This file exists only for Zep Cloud cursor pagination and retry logic. Once all call sites have been migrated to Cypher/Graphiti, it can be deleted.

### File: `backend/app/services/graph_builder.py`

This is the most complex migration. Current flow:

1. `create_graph()` → `client.graph.create(graph_id, name)`
2. `set_ontology()` → Dynamic Pydantic `EntityModel`/`EdgeModel` classes → `client.graph.set_ontology()`
3. `add_text_batches()` → `EpisodeData` → `client.graph.add_batch()`
4. `_wait_for_episodes()` → Poll `client.graph.episode.get()` until `processed=True`
5. `_get_graph_info()` → `fetch_all_nodes()` / `fetch_all_edges()` counts
6. `get_graph_data()` → Full node/edge dump with temporal fields
7. `delete_graph()` → `client.graph.delete()`

**New flow with Graphiti:**

```python
from graphiti_core import Graphiti
from neo4j import GraphDatabase

class GraphBuilderService:
    def __init__(self):
        self.backend = GraphitiFactory.from_config()

    def create_graph(self, name: str) -> str:
        graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"
        self.backend.ensure_initialized()
        self.backend.create_graph_namespace(graph_id, name=name)
        return graph_id

    def set_ontology(self, graph_id, ontology):
        # Convert ontology dict into Graphiti-compatible prescribed types
        # or store a deterministic normalization contract used after ingestion.
        self.backend.register_ontology(graph_id, ontology)

    def add_text_batches(self, graph_id, chunks, ...):
        for i, chunk in enumerate(chunks):
            self.backend.add_episode(
                graph_id=graph_id,
                name=f"chunk_{i}",
                episode_body=chunk,
                source_description="document",
            )

    def get_graph_data(self, graph_id):
        return self.backend.get_graph_data(graph_id)

    def delete_graph(self, graph_id):
        self.backend.delete_graph(graph_id)
```

**Key changes:**
- `graph_id` namespace management becomes explicit and mandatory
- `set_ontology()` remains meaningful: preserve or normalize the ontology contract instead of dropping it
- `add_text_batches()` + `_wait_for_episodes()` collapse into a simpler ingestion flow
- `get_graph_data()` uses backend-managed Cypher filtered by `graph_id`
- `delete_graph()` must delete only one graph namespace, never the whole database

### File: `backend/app/services/zep_entity_reader.py` → Rename to `entity_reader.py`

Current: Uses Zep SDK to fetch nodes/edges, filter by entity type, enrich with related edges.

**Migration:**

```python
class EntityReader:
    def __init__(self):
        self.backend = GraphitiFactory.from_config()

    def get_all_nodes(self, graph_id):
        with self.backend.session() as session:
            result = session.run("""
                MATCH (n:Entity {graph_id: $graph_id})
                RETURN n.uuid AS uuid, n.name AS name,
                       labels(n) AS labels, n.summary AS summary
            """, graph_id=graph_id)
            return [dict(r) for r in result]

    def get_node_edges(self, graph_id, node_uuid):
        with self.backend.session() as session:
            result = session.run("""
                MATCH (n {uuid: $uuid, graph_id: $graph_id})-[r]-(m {graph_id: $graph_id})
                RETURN r, n.uuid AS source, m.uuid AS target,
                       type(r) AS rel_type
            """, uuid=node_uuid, graph_id=graph_id)
            return [dict(r) for r in result]

    def filter_defined_entities(self, graph_id, defined_entity_types=None, ...):
        # Use Cypher label filtering instead of client-side loops
        if defined_entity_types:
            # MATCH (n {graph_id: $graph_id}) WHERE any(l IN labels(n) WHERE l IN $types)
            pass
```

**Key improvement:** Entity type filtering moves from Python-side loops to Cypher `WHERE` clauses — much faster for large graphs.

**Important:** this file still depends on stable custom labels. That is why ontology preservation cannot be treated as optional.

### File: `backend/app/services/zep_tools.py` → Rename to `graph_tools.py`

Current: Three search modes (QuickSearch, PanoramaSearch, InsightForge) + node/edge accessors.

**Migration:**

```python
class GraphToolsService:
    def __init__(self):
        self.backend = GraphitiFactory.from_config()

    def search_graph(self, graph_id, query, limit=10, scope="edges"):
        # Graphiti provides hybrid search (semantic + BM25)
        results = self.backend.search(graph_id=graph_id, query=query, num_results=limit)
        # results contain edges with facts, source/target nodes
        # Map to existing SearchResult dataclass

    def get_all_nodes(self, graph_id) -> List[NodeInfo]:
        # Direct Cypher query
        ...

    def get_all_edges(self, graph_id, include_temporal=True) -> List[EdgeInfo]:
        # Direct Cypher query — temporal fields are native Graphiti edge properties
        ...

    def get_node_detail(self, node_uuid) -> Optional[NodeInfo]:
        # Single Cypher lookup
        ...
```

**InsightForge** stays largely unchanged conceptually, but this service still needs to preserve:

- `get_graph_statistics()`
- `get_simulation_context()`
- `get_entities_by_type()`
- `get_entity_summary()`
- `interview_agents()` integration points used by the report agent

The migration is not just a `search_graph()` swap.

### File: `backend/app/services/zep_graph_memory_updater.py` → Rename to `graph_memory_updater.py`

Current: Queues agent activities, batches them, sends text to Zep via `client.graph.add()`.

**Migration is straightforward:**

```python
class GraphMemoryUpdater:
    def __init__(self, graph_id):
        self.backend = GraphitiFactory.from_config()
        # Keep: Queue, threading, batching, AgentActivity (unchanged)

    def _send_batch_activities(self, activities, platform):
        combined_text = "\n".join(a.to_episode_text() for a in activities)
        self.backend.add_episode(
            graph_id=self.graph_id,
            name=f"simulation_{platform}_batch",
            episode_body=combined_text,
            source_description=f"simulation_{platform}",
        )
```

**`AgentActivity` dataclass and all `to_episode_text()` methods stay completely unchanged** — they generate natural language text that works identically with Graphiti's extraction.

### File: `backend/app/services/oasis_profile_generator.py`

Uses Zep search for optional entity enrichment. Update this to use `GraphToolsService` or the new backend abstraction rather than directly instantiating a second graph client. This keeps search behavior centralized.

### Files: `backend/app/api/graph.py`, `backend/app/api/simulation.py`, `backend/app/api/report.py`

These routes need more than import updates:

- replace `ZEP_API_KEY` validation checks
- update user-facing error messages
- update service imports if files are renamed
- preserve existing response payloads so the frontend does not need to change

### File: `backend/app/services/__init__.py`

Update exported service names after the rename from `zep_*` modules to generic graph backend modules.

---

## Migration Order

| Phase | Files | Effort | Risk |
|---|---|---|---|
| **1. Backend abstraction** | `graphiti_factory.py` or `graph_backend.py` | Medium | Medium |
| **2. Infrastructure/config** | `docker-compose.yml`, `.env.example`, `backend/pyproject.toml`, `config.py` | Low | Low |
| **3. Core graph** | `graph_builder.py` (rewrite) | High | High — this is the centerpiece |
| **4. Entity reader + profile enrichment** | `zep_entity_reader.py`, `oasis_profile_generator.py`, `simulation_config_generator.py` | Medium | Medium |
| **5. Search/report tools** | `zep_tools.py`, `report_agent.py`, `api/report.py` | High | High |
| **6. Simulation memory updates** | `zep_graph_memory_updater.py`, `simulation_runner.py` | Medium | Medium |
| **7. Cleanup** | Delete `zep_paging.py`, update `__init__.py` exports, update imports in `api/*.py` | Low | Low |

**Phase 3 is the critical path.** The graph builder is where graph namespace rules, ontology preservation, and ingestion semantics all meet.

---

## Async Consideration

Graphiti's API is async (`await graphiti.add_episode(...)`). MiroFish's backend is Flask (sync). Options:

1. **Use `asyncio.run()` wrappers behind a sync backend facade** — simplest initial path, but keep it inside one abstraction layer rather than scattering it through routes/services
2. **Switch to Quart** (async Flask) — larger change, but better long-term
3. **Run Graphiti calls in thread pool** with `loop.run_in_executor()` — keeps Flask sync, runs Graphiti in background threads (similar to current `threading.Thread` pattern)

Option 1 is recommended for the first migration pass, but only if it is encapsulated in a single backend service. Avoid sprinkling raw `asyncio.run()` in route handlers, report tools, and worker threads.

---

## What Stays the Same

- **`AgentActivity` dataclass** and all `to_episode_text()` methods — unchanged
- **`TextProcessor`** — chunking logic is independent of storage backend
- **`ontology_generator.py`** — LLM-based ontology extraction stays the same at the API boundary; the output is adapted to the new graph backend rather than discarded
- **Frontend** — `GraphPanel.vue` and all D3 visualization code stays unchanged; it consumes the same JSON shape from `/api/graph/data`
- **`SearchResult`, `NodeInfo`, `EdgeInfo` dataclasses** — keep as-is, just populate from Cypher results instead of Zep SDK objects
- **Report Agent tools** — `InsightForge`, `PanoramaSearch`, `interview_agents` logic stays the same; only the underlying `search_graph` call changes

---

## Summary Recommendation

Proceed with Graphiti + Neo4j, but treat this as a backend replacement project rather than a simple SDK swap.

The highest-risk items are:

1. preserving `graph_id` isolation
2. preserving stable ontology/type labels used by simulation prep
3. centralizing Graphiti client initialization and async bridging
4. migrating the report/search tooling surface, not just the graph builder
