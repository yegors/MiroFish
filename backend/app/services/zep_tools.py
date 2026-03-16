"""
ZepSearch tool service
Provides graph search, node read, edge query, and other tools for the Report Agent.

Core search tools (optimized):
1. InsightForge (deep insight search) - The most powerful hybrid search; automatically generates sub-questions and searches across multiple dimensions
2. PanoramaSearch (breadth search) - Get the full picture, including expired content
3. QuickSearch (simple search) - Quick search
"""

import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges

logger = get_logger('mirofish.zep_tools')


@dataclass
class SearchResult:
    """Search results"""
    facts: List[str]
    edges: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    query: str
    total_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "edges": self.edges,
            "nodes": self.nodes,
            "query": self.query,
            "total_count": self.total_count
        }
    
    def to_text(self) -> str:
        """Convert to text format for LLM consumption."""
        text_parts = [f"Search: {self.query}", f"Found {self.total_count} related items"]
        
        if self.facts:
            text_parts.append("\n### Related Facts:")
            for i, fact in enumerate(self.facts, 1):
                text_parts.append(f"{i}. {fact}")
        
        return "\n".join(text_parts)


@dataclass
class NodeInfo:
    """Node information"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes
        }
    
    def to_text(self) -> str:
        """Convert to text format."""
        entity_type = next((l for l in self.labels if l not in ["Entity", "Node"]), "Unknown Type")
        return f"Entity: {self.name} (Type: {entity_type})\nSummary: {self.summary}"


@dataclass
class EdgeInfo:
    """Edge information"""
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: Optional[str] = None
    target_node_name: Optional[str] = None
    # time information
    created_at: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "source_node_name": self.source_node_name,
            "target_node_name": self.target_node_name,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at
        }
    
    def to_text(self, include_temporal: bool = False) -> str:
        """Convert to text format."""
        source = self.source_node_name or self.source_node_uuid[:8]
        target = self.target_node_name or self.target_node_uuid[:8]
        base_text = f"Relation: {source} --[{self.name}]--> {target}\nFact: {self.fact}"
        
        if include_temporal:
            valid_at = self.valid_at or "Unknown"
            invalid_at = self.invalid_at or "Present"
            base_text += f"\nValidity: {valid_at} - {invalid_at}"
            if self.expired_at:
                base_text += f" (Expired: {self.expired_at})"
        
        return base_text
    
    @property
    def is_expired(self) -> bool:
        """Has it expired?"""
        return self.expired_at is not None
    
    @property
    def is_invalid(self) -> bool:
        """Has it expired?"""
        return self.invalid_at is not None


@dataclass
class InsightForgeResult:
    """
    Deep insights into search results (InsightForge).
    Search results containing multiple sub-questions and comprehensive analysis.
    """
    query: str
    simulation_requirement: str
    sub_queries: List[str]
    
    # Search results for each dimension
    semantic_facts: List[str] = field(default_factory=list)  # Semantic search results
    entity_insights: List[Dict[str, Any]] = field(default_factory=list)  # entity insights
    relationship_chains: List[str] = field(default_factory=list)  # relationship chain
    
    # Statistics
    total_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "simulation_requirement": self.simulation_requirement,
            "sub_queries": self.sub_queries,
            "semantic_facts": self.semantic_facts,
            "entity_insights": self.entity_insights,
            "relationship_chains": self.relationship_chains,
            "total_facts": self.total_facts,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships
        }
    
    def to_text(self) -> str:
        """Convert to a detailed text format for LLM consumption."""
        text_parts = [
            f"## Future Prediction Deep Analysis",
            f"Analysis Question: {self.query}",
            f"Scenario: {self.simulation_requirement}",
            f"\n### Prediction Statistics",
            f"- Related Predicted Facts: {self.total_facts}",
            f"- Related Entities: {self.total_entities}",
            f"- Relation Chains: {self.total_relationships}"
        ]
        
        # subproblem
        if self.sub_queries:
            text_parts.append(f"\n### Sub-Questions")
            for i, sq in enumerate(self.sub_queries, 1):
                text_parts.append(f"{i}. {sq}")
        
        # Semantic search results
        if self.semantic_facts:
            text_parts.append(f"\n### Key Facts (quote these verbatim in the report)")
            for i, fact in enumerate(self.semantic_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # entity insights
        if self.entity_insights:
            text_parts.append(f"\n### Core Entities")
            for entity in self.entity_insights:
                text_parts.append(f"- **{entity.get('name', 'Unknown')}** ({entity.get('type', 'Entity')})")
                if entity.get('summary'):
                    text_parts.append(f"  Summary: \"{entity.get('summary')}\"")
                if entity.get('related_facts'):
                    text_parts.append(f"  Related Facts: {len(entity.get('related_facts', []))}")
        
        # relationship chain
        if self.relationship_chains:
            text_parts.append(f"\n### Relation Chains")
            for chain in self.relationship_chains:
                text_parts.append(f"- {chain}")
        
        return "\n".join(text_parts)


@dataclass
class PanoramaResult:
    """
    Breadth search results (Panorama).
    Contains all relevant information, including expired content.
    """
    query: str
    
    # All nodes
    all_nodes: List[NodeInfo] = field(default_factory=list)
    # All edges (including expired)
    all_edges: List[EdgeInfo] = field(default_factory=list)
    # Current facts
    active_facts: List[str] = field(default_factory=list)
    # Expired/invalidated facts (historical)
    historical_facts: List[str] = field(default_factory=list)
    
    # statistics
    total_nodes: int = 0
    total_edges: int = 0
    active_count: int = 0
    historical_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "all_nodes": [n.to_dict() for n in self.all_nodes],
            "all_edges": [e.to_dict() for e in self.all_edges],
            "active_facts": self.active_facts,
            "historical_facts": self.historical_facts,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "active_count": self.active_count,
            "historical_count": self.historical_count
        }
    
    def to_text(self) -> str:
        """Convert to text format without truncation."""
        text_parts = [
            f"## Panorama Search Results (future overview)",
            f"Search: {self.query}",
            f"\n### Statistics",
            f"- Total Nodes: {self.total_nodes}",
            f"- Total Edges: {self.total_edges}",
            f"- Current Active Facts: {self.active_count}",
            f"- Historical/Expired Facts: {self.historical_count}"
        ]
        
        # Current facts (full output, no truncation)
        if self.active_facts:
            text_parts.append(f"\n### Current Active Facts (verbatim simulation output)")
            for i, fact in enumerate(self.active_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # Historical/expired facts (full output, no truncation)
        if self.historical_facts:
            text_parts.append(f"\n### Historical/Expired Facts (evolution log)")
            for i, fact in enumerate(self.historical_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # Key entities (full output, no truncation)
        if self.all_nodes:
            text_parts.append(f"\n### Related Entities")
            for node in self.all_nodes:
                entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "Entity")
                text_parts.append(f"- **{node.name}** ({entity_type})")
        
        return "\n".join(text_parts)


@dataclass
class AgentInterview:
    """Single Agent interview result"""
    agent_name: str
    agent_role: str  # Role type (e.g. student, teacher, media, etc.)
    agent_bio: str  # Introduction
    question: str  # interview questions
    response: str  # Interview answers
    key_quotes: List[str] = field(default_factory=list)  # Key Quotes
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "agent_bio": self.agent_bio,
            "question": self.question,
            "response": self.response,
            "key_quotes": self.key_quotes
        }
    
    def to_text(self) -> str:
        text = f"**{self.agent_name}** ({self.agent_role})\n"
        text += f"_Bio: {self.agent_bio}_\n\n"
        text += f"**Q:** {self.question}\n\n"
        text += f"**A:** {self.response}\n"
        if self.key_quotes:
            text += "\n**Key Quotes:**\n"
            for quote in self.key_quotes:
                # Clean up various quotes
                clean_quote = quote.replace('\u201c', '').replace('\u201d', '').replace('"', '')
                clean_quote = clean_quote.replace('\u300c', '').replace('\u300d', '')
                clean_quote = clean_quote.strip()
                # Remove the leading punctuation
                while clean_quote and clean_quote[0] in ',,;;::,.!?\n\r\t ':
                    clean_quote = clean_quote[1:]
                # Filter spam containing question numbers (question 1-9)
                skip = False
                for d in '123456789':
                    if f'\u95ee\u9898{d}' in clean_quote:
                        skip = True
                        break
                if skip:
                    continue
                # Truncate overly long content (truncate at period rather than hard truncation)
                if len(clean_quote) > 150:
                    dot_pos = clean_quote.find('\u3002', 80)
                    if dot_pos > 0:
                        clean_quote = clean_quote[:dot_pos + 1]
                    else:
                        clean_quote = clean_quote[:147] + "..."
                if clean_quote and len(clean_quote) >= 10:
                    text += f'> "{clean_quote}"\n'
        return text


@dataclass
class InterviewResult:
    """
    Interview results.
    Contains interview answers from multiple simulated Agents.
    """
    interview_topic: str  # Interview topic
    interview_questions: List[str]  # List of interview questions

    # Agents Selected for interview
    Selected_agents: List[Dict[str, Any]] = field(default_factory=list)
    # Each Agent's interview answers
    interviews: List[AgentInterview] = field(default_factory=list)

    # Agent selection reasoning
    selection_reasoning: str = ""
    # Consolidated interview summary
    summary: str = ""
    
    # statistics
    total_agents: int = 0
    interviewed_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "interview_topic": self.interview_topic,
            "interview_questions": self.interview_questions,
            "Selected_agents": self.Selected_agents,
            "interviews": [i.to_dict() for i in self.interviews],
            "selection_reasoning": self.selection_reasoning,
            "summary": self.summary,
            "total_agents": self.total_agents,
            "interviewed_count": self.interviewed_count
        }
    
    def to_text(self) -> str:
        """Convert to a detailed text format for LLM use and report citation."""
        text_parts = [
            "## Deep Interview Report",
            f"**Interview Topic:** {self.interview_topic}",
            f"**Interview Count:** {self.interviewed_count} / {self.total_agents} simulated agents",
            "\n### Selection Reasoning",
            self.selection_reasoning or "(Auto-Selected)",
            "\n---",
            "\n### Interview Transcript",
        ]

        if self.interviews:
            for i, interview in enumerate(self.interviews, 1):
                text_parts.append(f"\n#### Interview #{i}: {interview.agent_name}")
                text_parts.append(interview.to_text())
                text_parts.append("\n---")
        else:
            text_parts.append("(No interview records)\n\n---")

        text_parts.append("\n### Interview Summary and Key Takeaways")
        text_parts.append(self.summary or "(No summary)")

        return "\n".join(text_parts)


class ZepToolsService:
    """
    ZepSearch tool service.

    [Core search tools - optimized]
    1. insight_forge - Deep insight search (most powerful; auto-generates sub-questions, multi-dimensional search)
    2. panorama_search - Breadth search (full picture, includes expired content)
    3. quick_search - Simple search (quick lookup)
    4. interview_agents - In-depth interview (interview simulated Agents, get multiple perspectives)

    [Basic tools]
    - search_graph - Graph semantic search
    - get_all_nodes - Get all nodes in the graph
    - get_all_edges - Get all edges of the graph (includes temporal information)
    - get_node_detail - Get node details
    - get_node_edges - Get edges related to a node
    - get_entities_by_type - Get entities by type
    - get_entity_summary - Get an entity's relationship summary
    """
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    
    def __init__(self, api_key: Optional[str] = None, llm_client: Optional[LLMClient] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY Not configured")
        
        self.client = Zep(api_key=self.api_key)
        # LLM client used by InsightForge to generate sub-questions
        self._llm_client = llm_client
        logger.info("ZepToolsService initialization completed")
    
    @property
    def llm(self) -> LLMClient:
        """Lazily initialize the LLM client."""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client
    
    def _call_with_retry(self, func, operation_name: str, max_retries: int = None):
        """API call with retry mechanism."""
        max_retries = max_retries or self.MAX_RETRIES
        last_exception = None
        delay = self.RETRY_DELAY
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Zep {operation_name} attempt {attempt + 1} failed: {str(e)[:100]}, "
                        f"retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(f"Zep {operation_name} failed after {max_retries} attempts: {str(e)}")
        
        raise last_exception
    
    def search_graph(
        self, 
        graph_id: str, 
        query: str, 
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        Graph semantic search.

        Uses hybrid search (semantic + BM25) to find relevant information in the graph.
        If the Zep Cloud search API is unavailable, falls back to local keyword matching.

        Args:
            graph_id: Graph ID (standalone graph)
            query: Search query
            limit: Number of results to return
            scope: Search scope, "edges" or "nodes"

        Returns:
            SearchResult: Search results
        """
        logger.info(f"Graph search: graph_id={graph_id}, query={query[:50]}...")
        
        # Try using the Zep Cloud Search API
        try:
            search_results = self._call_with_retry(
                func=lambda: self.client.graph.search(
                    graph_id=graph_id,
                    query=query,
                    limit=limit,
                    scope=scope,
                    reranker="cross_encoder"
                ),
                operation_name=f"graph search (graph={graph_id})"
            )
            
            facts = []
            edges = []
            nodes = []
            
            # Parse edge search results
            if hasattr(search_results, 'edges') and search_results.edges:
                for edge in search_results.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        facts.append(edge.fact)
                    edges.append({
                        "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                        "name": getattr(edge, 'name', ''),
                        "fact": getattr(edge, 'fact', ''),
                        "source_node_uuid": getattr(edge, 'source_node_uuid', ''),
                        "target_node_uuid": getattr(edge, 'target_node_uuid', ''),
                    })
            
            # Parse node search results
            if hasattr(search_results, 'nodes') and search_results.nodes:
                for node in search_results.nodes:
                    nodes.append({
                        "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                        "name": getattr(node, 'name', ''),
                        "labels": getattr(node, 'labels', []),
                        "summary": getattr(node, 'summary', ''),
                    })
                    # Node summaries also count as facts
                    if hasattr(node, 'summary') and node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")
            
            logger.info(f"Search completed: found {len(facts)} relevant facts")
            
            return SearchResult(
                facts=facts,
                edges=edges,
                nodes=nodes,
                query=query,
                total_count=len(facts)
            )
            
        except Exception as e:
            logger.warning(f"Zep Search API failed, falling back to local search: {str(e)}")
            # Fallback: search using local keyword matching
            return self._local_search(graph_id, query, limit, scope)
    
    def _local_search(
        self, 
        graph_id: str, 
        query: str, 
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        Local keyword matching search (fallback for Zep Search API).

        Gets all edges/nodes, then performs keyword matching locally.

        Args:
            graph_id: Graph ID
            query: Search query
            limit: Number of results to return
            scope: Search scope

        Returns:
            SearchResult: Search results
        """
        logger.info(f"Use local search: query={query[:30]}...")
        
        facts = []
        edges_result = []
        nodes_result = []
        
        # Extract query keywords (simple tokenization)
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace(',', ' ').split() if len(w.strip()) > 1]
        
        def match_score(text: str) -> int:
            """Calculate the match score between text and query"""
            if not text:
                return 0
            text_lower = text.lower()
            # exact match query
            if query_lower in text_lower:
                return 100
            # keyword matching
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 10
            return score
        
        try:
            if scope in ["edges", "both"]:
                # Get all edges and match
                all_edges = self.get_all_edges(graph_id)
                scored_edges = []
                for edge in all_edges:
                    score = match_score(edge.fact) + match_score(edge.name)
                    if score > 0:
                        scored_edges.append((score, edge))
                
                # Sort by score
                scored_edges.sort(key=lambda x: x[0], reverse=True)
                
                for score, edge in scored_edges[:limit]:
                    if edge.fact:
                        facts.append(edge.fact)
                    edges_result.append({
                        "uuid": edge.uuid,
                        "name": edge.name,
                        "fact": edge.fact,
                        "source_node_uuid": edge.source_node_uuid,
                        "target_node_uuid": edge.target_node_uuid,
                    })
            
            if scope in ["nodes", "both"]:
                # Get all nodes and match
                all_nodes = self.get_all_nodes(graph_id)
                scored_nodes = []
                for node in all_nodes:
                    score = match_score(node.name) + match_score(node.summary)
                    if score > 0:
                        scored_nodes.append((score, node))
                
                scored_nodes.sort(key=lambda x: x[0], reverse=True)
                
                for score, node in scored_nodes[:limit]:
                    nodes_result.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "labels": node.labels,
                        "summary": node.summary,
                    })
                    if node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")
            
            logger.info(f"Local search completed: found {len(facts)} relevant facts")
            
        except Exception as e:
            logger.error(f"Local search failed: {str(e)}")
        
        return SearchResult(
            facts=facts,
            edges=edges_result,
            nodes=nodes_result,
            query=query,
            total_count=len(facts)
        )
    
    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        """
        Get all nodes of the graph (paginated).

        Args:
            graph_id: Graph ID

        Returns:
            List of nodes
        """
        logger.info(f"Getting all nodes of graph {graph_id}...")

        nodes = fetch_all_nodes(self.client, graph_id)

        result = []
        for node in nodes:
            node_uuid = getattr(node, 'uuid_', None) or getattr(node, 'uuid', None) or ""
            result.append(NodeInfo(
                uuid=str(node_uuid) if node_uuid else "",
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            ))

        logger.info(f"Got {len(result)} nodes")
        return result

    def get_all_edges(self, graph_id: str, include_temporal: bool = True) -> List[EdgeInfo]:
        """
        Get all edges of the graph (paginated, with temporal information).

        Args:
            graph_id: Graph ID
            include_temporal: Whether to include temporal information (default True)

        Returns:
            List of edges (includes created_at, valid_at, invalid_at, expired_at)
        """
        logger.info(f"Getting all edges of graph {graph_id}...")

        edges = fetch_all_edges(self.client, graph_id)

        result = []
        for edge in edges:
            edge_uuid = getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', None) or ""
            edge_info = EdgeInfo(
                uuid=str(edge_uuid) if edge_uuid else "",
                name=edge.name or "",
                fact=edge.fact or "",
                source_node_uuid=edge.source_node_uuid or "",
                target_node_uuid=edge.target_node_uuid or ""
            )

            # Add time information
            if include_temporal:
                edge_info.created_at = getattr(edge, 'created_at', None)
                edge_info.valid_at = getattr(edge, 'valid_at', None)
                edge_info.invalid_at = getattr(edge, 'invalid_at', None)
                edge_info.expired_at = getattr(edge, 'expired_at', None)

            result.append(edge_info)

        logger.info(f"Got {len(result)} edges")
        return result
    
    def get_node_detail(self, node_uuid: str) -> Optional[NodeInfo]:
        """
        Get details of a single node.

        Args:
            node_uuid: Node UUID

        Returns:
            Node information, or None
        """
        logger.info(f"Get node details: {node_uuid[:8]}...")
        
        try:
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=node_uuid),
                operation_name=f"get node detail (uuid={node_uuid[:8]}...)"
            )
            
            if not node:
                return None
            
            return NodeInfo(
                uuid=getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            )
        except Exception as e:
            logger.error(f"Failed to obtain node details: {str(e)}")
            return None
    
    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeInfo]:
        """
        Get all edges related to a node.

        Gets all edges of the graph, then filters for edges related to the specified node.

        Args:
            graph_id: Graph ID
            node_uuid: Node UUID

        Returns:
            List of edges
        """
        logger.info(f"Getting edges related to node {node_uuid[:8]}...")
        
        try:
            # Get all edges of the graph, then filter
            all_edges = self.get_all_edges(graph_id)
            
            result = []
            for edge in all_edges:
                # Check whether the edge is related to the specified node (as source or target)
                if edge.source_node_uuid == node_uuid or edge.target_node_uuid == node_uuid:
                    result.append(edge)
            
            logger.info(f"Found {len(result)} edges related to node")
            return result
            
        except Exception as e:
            logger.warning(f"Failed to obtain node edges: {str(e)}")
            return []
    
    def get_entities_by_type(
        self, 
        graph_id: str, 
        entity_type: str
    ) -> List[NodeInfo]:
        """
        Get entities by type.

        Args:
            graph_id: Graph ID
            entity_type: Entity type (e.g. Student, PublicFigure, etc.)

        Returns:
            List of entities matching the type
        """
        logger.info(f"Getting entities of type {entity_type}...")
        
        all_nodes = self.get_all_nodes(graph_id)
        
        filtered = []
        for node in all_nodes:
            # Check whether labels include the specified type
            if entity_type in node.labels:
                filtered.append(node)
        
        logger.info(f"Found {len(filtered)} entities of type {entity_type}")
        return filtered
    
    def get_entity_summary(
        self, 
        graph_id: str, 
        entity_name: str
    ) -> Dict[str, Any]:
        """
        Get the relationship summary for the specified entity.

        Searches for all information related to this entity and generates a summary.

        Args:
            graph_id: Graph ID
            entity_name: Entity name

        Returns:
            Entity summary information
        """
        logger.info(f"Getting relationship summary for entity {entity_name}...")
        
        # First search for information related to the entity
        search_result = self.search_graph(
            graph_id=graph_id,
            query=entity_name,
            limit=20
        )
        
        # Try to find the entity in all nodes
        all_nodes = self.get_all_nodes(graph_id)
        entity_node = None
        for node in all_nodes:
            if node.name.lower() == entity_name.lower():
                entity_node = node
                break
        
        related_edges = []
        if entity_node:
            # Pass graph_id parameter
            related_edges = self.get_node_edges(graph_id, entity_node.uuid)
        
        return {
            "entity_name": entity_name,
            "entity_info": entity_node.to_dict() if entity_node else None,
            "related_facts": search_result.facts,
            "related_edges": [e.to_dict() for e in related_edges],
            "total_relations": len(related_edges)
        }
    
    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        """
        Get graph statistics.

        Args:
            graph_id: Graph ID

        Returns:
            Statistics
        """
        logger.info(f"Getting statistics for graph {graph_id}...")
        
        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)
        
        # Statistical entity type distribution
        entity_types = {}
        for node in nodes:
            for label in node.labels:
                if label not in ["Entity", "Node"]:
                    entity_types[label] = entity_types.get(label, 0) + 1
        
        # Statistical relationship type distribution
        relation_types = {}
        for edge in edges:
            relation_types[edge.name] = relation_types.get(edge.name, 0) + 1
        
        return {
            "graph_id": graph_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": entity_types,
            "relation_types": relation_types
        }
    
    def get_simulation_context(
        self, 
        graph_id: str,
        simulation_requirement: str,
        limit: int = 30
    ) -> Dict[str, Any]:
        """
        Get simulation-related contextual information
        
        Comprehensive search for all information relevant to your simulation needs
        
        Args:
            graph_id: AtlasID
            simulation_requirement: Simulation requirement description
            limit: Quantity limit for each type of information
            
        Returns:
            Simulation context information
        """
        logger.info(f"Get simulation context: {simulation_requirement[:50]}...")
        
        # Search for information related to simulation requirements
        search_result = self.search_graph(
            graph_id=graph_id,
            query=simulation_requirement,
            limit=limit
        )
        
        # Get graph statistics
        stats = self.get_graph_statistics(graph_id)
        
        # Get all entity nodes
        all_nodes = self.get_all_nodes(graph_id)
        
        # Filter entities with actual types (not bare Entity nodes)
        entities = []
        for node in all_nodes:
            custom_labels = [l for l in node.labels if l not in ["Entity", "Node"]]
            if custom_labels:
                entities.append({
                    "name": node.name,
                    "type": custom_labels[0],
                    "summary": node.summary
                })
        
        return {
            "simulation_requirement": simulation_requirement,
            "related_facts": search_result.facts,
            "graph_statistics": stats,
            "entities": entities[:limit],  # limited quantity
            "total_entities": len(entities)
        }
    
    # ========== Core search tools (optimized) ==========
    
    def insight_forge(
        self,
        graph_id: str,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_sub_queries: int = 5
    ) -> InsightForgeResult:
        """
        [InsightForge - Deep insight search]

        The most powerful hybrid search function. Automatically decomposes questions and searches across multiple dimensions:
        1. Use LLM to break the problem into sub-questions
        2. Semantic search for each sub-question
        3. Extract related entities and get their details
        4. Trace the chain of relationships
        5. Consolidate all results and generate deep insights

        Args:
            graph_id: Graph ID
            query: User query
            simulation_requirement: Simulation requirement description
            report_context: Report context (optional, for more accurate sub-question generation)
            max_sub_queries: Maximum number of sub-questions

        Returns:
            InsightForgeResult: Deep insights search results
        """
        logger.info(f"InsightForge Deep insight search: {query[:50]}...")
        
        result = InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=[]
        )
        
        # Step 1: Use LLM to generate sub-questions
        sub_queries = self._generate_sub_queries(
            query=query,
            simulation_requirement=simulation_requirement,
            report_context=report_context,
            max_queries=max_sub_queries
        )
        result.sub_queries = sub_queries
        logger.info(f"Generated {len(sub_queries)} sub-questions")
        
        # Step 2: Semantic search for each sub-question
        all_facts = []
        all_edges = []
        seen_facts = set()
        
        for sub_query in sub_queries:
            search_result = self.search_graph(
                graph_id=graph_id,
                query=sub_query,
                limit=15,
                scope="edges"
            )
            
            for fact in search_result.facts:
                if fact not in seen_facts:
                    all_facts.append(fact)
                    seen_facts.add(fact)
            
            all_edges.extend(search_result.edges)
        
        # Also search for the original question
        main_search = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=20,
            scope="edges"
        )
        for fact in main_search.facts:
            if fact not in seen_facts:
                all_facts.append(fact)
                seen_facts.add(fact)
        
        result.semantic_facts = all_facts
        result.total_facts = len(all_facts)
        
        # Step 3: Extract related entity UUIDs from edges; only get info for these entities (not all nodes)
        entity_uuids = set()
        for edge_data in all_edges:
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                if source_uuid:
                    entity_uuids.add(source_uuid)
                if target_uuid:
                    entity_uuids.add(target_uuid)
        
        # Get details of all related entities (no quantity limit, full output)
        entity_insights = []
        node_map = {}  # Used for subsequent relationship chain building
        
        for uuid in list(entity_uuids):  # Process all entities, no truncation
            if not uuid:
                continue
            try:
                # Get information about each relevant node individually
                node = self.get_node_detail(uuid)
                if node:
                    node_map[uuid] = node
                    entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "entity")
                    
                    # Get all facts related to this entity(Do not truncate)
                    related_facts = [
                        f for f in all_facts 
                        if node.name.lower() in f.lower()
                    ]
                    
                    entity_insights.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "type": entity_type,
                        "summary": node.summary,
                        "related_facts": related_facts  # full output,Do not truncate
                    })
            except Exception as e:
                logger.debug(f"Get node {uuid} fail: {e}")
                continue
        
        result.entity_insights = entity_insights
        result.total_entities = len(entity_insights)
        
        # Step 4: Build all relationship chains(No limit on quantity)
        relationship_chains = []
        for edge_data in all_edges:  # Process all edges,Do not truncate
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                relation_name = edge_data.get('name', '')
                
                source_name = node_map.get(source_uuid, NodeInfo('', '', [], '', {})).name or source_uuid[:8]
                target_name = node_map.get(target_uuid, NodeInfo('', '', [], '', {})).name or target_uuid[:8]
                
                chain = f"{source_name} --[{relation_name}]--> {target_name}"
                if chain not in relationship_chains:
                    relationship_chains.append(chain)
        
        result.relationship_chains = relationship_chains
        result.total_relationships = len(relationship_chains)
        
        logger.info(f"InsightForgeFinish: {result.total_facts}facts, {result.total_entities}entities, {result.total_relationships}relationship")
        return result
    
    def _generate_sub_queries(
        self,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_queries: int = 5
    ) -> List[str]:
        """
        useLLMGenerate subproblems
        
        Decompose complex problems into multiple sub-problems that can be retrieved independently
        """
        system_prompt = """You are a professional problem analyzer.Your task is to decompose a complex problem into multiple sub-problems that can be independently observed in a simulated world.

Require:
1. Each sub-question should be specific enough,Related ones can be found in Simulation WorldAgentbehavior or event
2. Subproblems should cover different dimensions of the original problem(like:who,What,Why,How about it,when,Where)
3. Sub-problems should be relevant to the simulation scenario
4. returnJSONFormat:{"sub_queries": ["subproblem1", "subproblem2", ...]}"""

        user_prompt = f"""Simulation requirements background:
{simulation_requirement}

{f"Report context:{report_context[:500]}" if report_context else ""}

Please break down the following questions into{max_queries}sub-problem:
{query}

returnJSONList of sub-questions in format."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            sub_queries = response.get("sub_queries", [])
            # Make sure it is a list of strings
            return [str(sq) for sq in sub_queries[:max_queries]]
            
        except Exception as e:
            logger.warning(f"Failed to generate subquestion: {str(e)},Use default subquestion")
            # Downgrade:Returns a variation based on the original question
            return [
                query,
                f"{query} major players in",
                f"{query} causes and effects",
                f"{query} development process"
            ][:max_queries]
    
    def panorama_search(
        self,
        graph_id: str,
        query: str,
        include_expired: bool = True,
        limit: int = 50
    ) -> PanoramaResult:
        """
        [PanoramaSearch - breadth search]
        
        Get a full view,Includes all relevant content and history/Expired information:
        1. Get all related nodes
        2. Get all edges(including expired/invalid)
        3. Classify currently valid and historical information
        
        This tool is suitable for those who need to understand the whole incident,Scenarios that track their evolution.
        
        Args:
            graph_id: AtlasID
            query: search query(for relevance ranking)
            include_expired: Does it contain expired content?(defaultTrue)
            limit: Limit on the number of results returned
            
        Returns:
            PanoramaResult: Breadth search results
        """
        logger.info(f"PanoramaSearch breadth search: {query[:50]}...")
        
        result = PanoramaResult(query=query)
        
        # Get all nodes
        all_nodes = self.get_all_nodes(graph_id)
        node_map = {n.uuid: n for n in all_nodes}
        result.all_nodes = all_nodes
        result.total_nodes = len(all_nodes)
        
        # Get all edges(Contains time information)
        all_edges = self.get_all_edges(graph_id, include_temporal=True)
        result.all_edges = all_edges
        result.total_edges = len(all_edges)
        
        # Classification facts
        active_facts = []
        historical_facts = []
        
        for edge in all_edges:
            if not edge.fact:
                continue
            
            # Add entity name to fact
            source_name = node_map.get(edge.source_node_uuid, NodeInfo('', '', [], '', {})).name or edge.source_node_uuid[:8]
            target_name = node_map.get(edge.target_node_uuid, NodeInfo('', '', [], '', {})).name or edge.target_node_uuid[:8]
            
            # Determine whether it has expired/Invalid
            is_historical = edge.is_expired or edge.is_invalid
            
            if is_historical:
                # history/expired fact,Add time stamp
                valid_at = edge.valid_at or "unknown"
                invalid_at = edge.invalid_at or edge.expired_at or "unknown"
                fact_with_time = f"[{valid_at} - {invalid_at}] {edge.fact}"
                historical_facts.append(fact_with_time)
            else:
                # current valid facts
                active_facts.append(edge.fact)
        
        # Relevance ranking based on query
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace(',', ' ').split() if len(w.strip()) > 1]
        
        def relevance_score(fact: str) -> int:
            fact_lower = fact.lower()
            score = 0
            if query_lower in fact_lower:
                score += 100
            for kw in keywords:
                if kw in fact_lower:
                    score += 10
            return score
        
        # Sort and limit quantity
        active_facts.sort(key=relevance_score, reverse=True)
        historical_facts.sort(key=relevance_score, reverse=True)
        
        result.active_facts = active_facts[:limit]
        result.historical_facts = historical_facts[:limit] if include_expired else []
        result.active_count = len(active_facts)
        result.historical_count = len(historical_facts)
        
        logger.info(f"PanoramaSearchFinish: {result.active_count}valid, {result.historical_count}history")
        return result
    
    def quick_search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10
    ) -> SearchResult:
        """
        [QuickSearch - Simple search]
        
        fast,Lightweight search tool:
        1. call directlyZepSemantic search
        2. Return the most relevant results
        3. suitable for simple,direct search requirements
        
        Args:
            graph_id: AtlasID
            query: search query
            limit: Number of results returned
            
        Returns:
            SearchResult: Search results
        """
        logger.info(f"QuickSearch Simple search: {query[:50]}...")
        
        # Directly call an existingsearch_graphmethod
        result = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit,
            scope="edges"
        )
        
        logger.info(f"QuickSearchFinish: {result.total_count}results")
        return result
    
    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 5,
        custom_questions: List[str] = None
    ) -> InterviewResult:
        """
        [InterviewAgents - in-depth interview]
        
        call realOASISinterviewAPI,Interview simulation runningAgent:
        1. Automatically read character files,Learn about all simulationsAgent
        2. useLLMAnalyze interview needs,Intelligent selection of the most relevantAgent
        3. useLLMGenerate interview questions
        4. call /api/simulation/interview/batch interface for real interviews(Simultaneous interviews on dual platforms)
        5. Integrate all interview results,Generate interview report
        
        [important]This feature requires the simulation environment to be running(OASISThe environment is not closed)
        
        [Usage scenarios]
        - Need to understand events from different role perspectives
        - Need to collect opinions and perspectives from multiple parties
        - Need to get simulationAgentreal answer(NoLLMsimulation)
        
        Args:
            simulation_id: simulation ID(Used to locate persona files and call interviewsAPI)
            interview_requirement: Interview requirement description(unstructured,like"Understand students’ views on the incident")
            simulation_requirement: Simulation requirements background(Optional)
            max_agents: Most interviewedAgentquantity
            custom_questions: Custom interview questions(Optional,If not provided, it will be automatically generated.)
            
        Returns:
            InterviewResult: Interview results
        """
        from .simulation_runner import SimulationRunner
        
        logger.info(f"InterviewAgents in-depth interview(realityAPI): {interview_requirement[:50]}...")
        
        result = InterviewResult(
            interview_topic=interview_requirement,
            interview_questions=custom_questions or []
        )
        
        # Step 1: Read character file
        profiles = self._load_agent_profiles(simulation_id)
        
        if not profiles:
            logger.warning(f"Simulation not found {simulation_id} Persona file")
            result.summary = "No interviews foundAgentPersona file"
            return result
        
        result.total_agents = len(profiles)
        logger.info(f"Loaded {len(profiles)}  agentsPersonality")
        
        # Step 2: useLLMChoose to interviewAgent(returnagent_idlist)
        Selected_agents, Selected_indices, selection_reasoning = self._select_agents_for_interview(
            profiles=profiles,
            interview_requirement=interview_requirement,
            simulation_requirement=simulation_requirement,
            max_agents=max_agents
        )
        
        result.Selected_agents = Selected_agents
        result.selection_reasoning = selection_reasoning
        logger.info(f"Selected {len(Selected_agents)} agents for interview: {Selected_indices}")
        
        # Step 3: Generate interview questions(if not provided)
        if not result.interview_questions:
            result.interview_questions = self._generate_interview_questions(
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                Selected_agents=Selected_agents
            )
            logger.info(f"Generated {len(result.interview_questions)} interview questions")
        
        # Combine questions into one interviewprompt
        combined_prompt = "\n".join([f"{i+1}. {q}" for i, q in enumerate(result.interview_questions)])
        
        # Add optimization prefix,constraintAgentReply format
        INTERVIEW_PROMPT_PREFIX = (
            "You are being interviewed. Please draw on your personality, all past memories and actions, "
            "and answer the following questions directly in plain text.\n"
            "Reply requirements:\n"
            "1. Answer directly in natural language, don't call any tools\n"
            "2. Do not return JSON format or tool call format\n"
            "3. Do not use Markdown headings (like #, ##, ###)\n"
            "4. Answer each question by number. Each answer starts with 'questionX:' (X is the question number)\n"
            "5. Separate the answers to each question with a blank line\n"
            "6. Answers should be substantive, at least 2-3 sentences per question\n\n"
        )
        optimized_prompt = f"{INTERVIEW_PROMPT_PREFIX}{combined_prompt}"
        
        # Step 4: call real interviewAPI(no platform specified,Dual-platform simultaneous interviews by default)
        try:
            # Build batch interview list(no platform specified,Dual-platform interview)
            interviews_request = []
            for agent_idx in Selected_indices:
                interviews_request.append({
                    "agent_id": agent_idx,
                    "prompt": optimized_prompt  # Use optimizedprompt
                    # no platform specified,APIwill be intwitterandredditInterviews on both platforms
                })
            
            logger.info(f"Call batch interview API (dual-platform): {len(interviews_request)}  agents")
            
            # call SimulationRunner batch interview method(Not passed onplatform,Dual-platform interview)
            api_result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id,
                interviews=interviews_request,
                platform=None,  # no platform specified,Dual-platform interview
                timeout=180.0   # Dual-platforms require longer timeouts
            )
            
            logger.info(f"interviewAPIreturn: {api_result.get('interviews_count', 0)} results, success={api_result.get('success')}")
            
            # examineAPIIs the call successful?
            if not api_result.get("success", False):
                error_msg = api_result.get("error", "unknown error")
                logger.warning(f"interviewAPIReturn failure: {error_msg}")
                result.summary = f"interviewAPIcall failed:{error_msg}.Check, pleaseOASISSimulate environment state."
                return result
            
            # Step 5: parseAPIReturn results,buildAgentInterviewobject
            # Dual-platform mode return format: {"twitter_0": {...}, "reddit_0": {...}, "twitter_1": {...}, ...}
            api_data = api_result.get("result", {})
            results_dict = api_data.get("results", {}) if isinstance(api_data, dict) else {}
            
            for i, agent_idx in enumerate(Selected_indices):
                agent = Selected_agents[i]
                agent_name = agent.get("realname", agent.get("username", f"Agent_{agent_idx}"))
                agent_role = agent.get("profession", "unknown")
                agent_bio = agent.get("bio", "")
                
                # Get theAgentInterview results on both platforms
                twitter_result = results_dict.get(f"twitter_{agent_idx}", {})
                reddit_result = results_dict.get(f"reddit_{agent_idx}", {})
                
                twitter_response = twitter_result.get("response", "")
                reddit_response = reddit_result.get("response", "")

                # Clean up possible tool calls JSON pack
                twitter_response = self._clean_tool_call_response(twitter_response)
                reddit_response = self._clean_tool_call_response(reddit_response)

                # Always output dual platform tags
                twitter_text = twitter_response if twitter_response else "(The platform did not receive a reply)"
                reddit_text = reddit_response if reddit_response else "(The platform did not receive a reply)"
                response_text = f"[TwitterPlatform answer]\n{twitter_text}\n\n[RedditPlatform answer]\n{reddit_text}"

                # Extract key quotes(Answers from both platforms)
                import re
                combined_responses = f"{twitter_response} {reddit_response}"

                # Clean response text:remove mark,serial number,Markdown Waiting for interference
                clean_text = re.sub(r'#{1,6}\s+', '', combined_responses)
                clean_text = re.sub(r'\{[^}]*tool_name[^}]*\}', '', clean_text)
                clean_text = re.sub(r'[*_`|>~\-]{2,}', '', clean_text)
                clean_text = re.sub(r'question\d+[::]\s*', '', clean_text)
                clean_text = re.sub(r'[[^]]+]', '', clean_text)

                # Strategy1(host): Extract complete sentences with substantial content
                sentences = re.split(r'[.!?]', clean_text)
                meaningful = [
                    s.strip() for s in sentences
                    if 20 <= len(s.strip()) <= 150
                    and not re.match(r'^[\s\W,,;;::,]+', s.strip())
                    and not s.strip().startswith(('{', 'question'))
                ]
                meaningful.sort(key=len, reverse=True)
                key_quotes = [s + "." for s in meaningful[:3]]

                # Strategy 2 (fallback): Extract text from paired quotation marks
                if not key_quotes:
                    paired = re.findall(r'\u201c([^\u201c\u201d]{15,100})\u201d', clean_text)
                    paired += re.findall(r'\u300c([^\u300c\u300d]{15,100})\u300d', clean_text)
                    key_quotes = [q for q in paired if not re.match(r'^[,,;;::,]', q)][:3]
                
                interview = AgentInterview(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    agent_bio=agent_bio[:1000],  # expandbiolength limit
                    question=combined_prompt,
                    response=response_text,
                    key_quotes=key_quotes[:5]
                )
                result.interviews.append(interview)
            
            result.interviewed_count = len(result.interviews)
            
        except ValueError as e:
            # The simulation environment is not running
            logger.warning(f"interviewAPIcall failed(Environment is not running?): {e}")
            result.summary = f"Interview failed:{str(e)}.The simulation environment may be down,please make sureOASISenvironment is running."
            return result
        except Exception as e:
            logger.error(f"interviewAPICall exception: {e}")
            import traceback
            logger.error(traceback.format_exc())
            result.summary = f"An error occurred during the interview:{str(e)}"
            return result
        
        # Step 6: Generate interview summary
        if result.interviews:
            result.summary = self._generate_interview_summary(
                interviews=result.interviews,
                interview_requirement=interview_requirement
            )
        
        logger.info(f"Interview agents completed: interviewed {result.interviewed_count} agents (dual-platform)")
        return result
    
    @staticmethod
    def _clean_tool_call_response(response: str) -> str:
        """clean up Agent in reply JSON tool call package,Extract actual content"""
        if not response or not response.strip().startswith('{'):
            return response
        text = response.strip()
        if 'tool_name' not in text[:80]:
            return response
        import re as _re
        try:
            data = json.loads(text)
            if isinstance(data, dict) and 'arguments' in data:
                for key in ('content', 'text', 'body', 'message', 'reply'):
                    if key in data['arguments']:
                        return str(data['arguments'][key])
        except (json.JSONDecodeError, KeyError, TypeError):
            match = _re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if match:
                return match.group(1).replace('\\n', '\n').replace('\\"', '"')
        return response

    def _load_agent_profiles(self, simulation_id: str) -> List[Dict[str, Any]]:
        """load simulatedAgentPersona file"""
        import os
        import csv
        
        # Build character file path
        sim_dir = os.path.join(
            os.path.dirname(__file__), 
            f'../../uploads/simulations/{simulation_id}'
        )
        
        profiles = []
        
        # Try to read firstReddit JSONFormat
        reddit_profile_path = os.path.join(sim_dir, "reddit_profiles.json")
        if os.path.exists(reddit_profile_path):
            try:
                with open(reddit_profile_path, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                logger.info(f"from reddit_profiles.json loaded {len(profiles)} personal settings")
                return profiles
            except Exception as e:
                logger.warning(f"read reddit_profiles.json fail: {e}")
        
        # try to readTwitter CSVFormat
        twitter_profile_path = os.path.join(sim_dir, "twitter_profiles.csv")
        if os.path.exists(twitter_profile_path):
            try:
                with open(twitter_profile_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # CSVConvert format to unified format
                        profiles.append({
                            "realname": row.get("name", ""),
                            "username": row.get("username", ""),
                            "bio": row.get("description", ""),
                            "persona": row.get("user_char", ""),
                            "profession": "unknown"
                        })
                logger.info(f"from twitter_profiles.csv loaded {len(profiles)} personal settings")
                return profiles
            except Exception as e:
                logger.warning(f"read twitter_profiles.csv fail: {e}")
        
        return profiles
    
    def _select_agents_for_interview(
        self,
        profiles: List[Dict[str, Any]],
        interview_requirement: str,
        simulation_requirement: str,
        max_agents: int
    ) -> tuple:
        """
        useLLMChoose to interviewAgent
        
        Returns:
            tuple: (Selected_agents, Selected_indices, reasoning)
                - Selected_agents: SelectedAgentComplete list of information
                - Selected_indices: SelectedAgentindex list of(used forAPIcall)
                - reasoning: Reason for selection
        """
        
        # buildAgentsummary list
        agent_summaries = []
        for i, profile in enumerate(profiles):
            summary = {
                "index": i,
                "name": profile.get("realname", profile.get("username", f"Agent_{i}")),
                "profession": profile.get("profession", "unknown"),
                "bio": profile.get("bio", "")[:200],
                "interested_topics": profile.get("interested_topics", [])
            }
            agent_summaries.append(summary)
        
        system_prompt = """You are a professional interview planning expert.Your task is based on interview needs,from simulationAgentSelect the most suitable person to interview from the list.

selection criteria:
1. Agentidentity/Careers related to interview topics
2. AgentMay hold unique or valuable perspectives
3. Choose a diverse perspective(like:Supporters,Opposition,neutral party,Professionals etc.)
4. Prioritize roles directly related to the event

returnJSONFormat:
{
    "Selected_indices": [SelectedAgentindex list of],
    "reasoning": "Reason for selection"
}"""

        user_prompt = f"""Interview requirements:
{interview_requirement}

Analog background:
{simulation_requirement if simulation_requirement else "Not provided"}

Available agent list (total{len(agent_summaries)}agents):
{json.dumps(agent_summaries, ensure_ascii=False, indent=2)}

Please select the most{max_agents}the most suitable for interviewsAgent,and explain the reasons for the choice."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            Selected_indices = response.get("Selected_indices", [])[:max_agents]
            reasoning = response.get("reasoning", "Automatic selection based on relevance")
            
            # Get SelectedAgentComplete information
            Selected_agents = []
            valid_indices = []
            for idx in Selected_indices:
                if 0 <= idx < len(profiles):
                    Selected_agents.append(profiles[idx])
                    valid_indices.append(idx)
            
            return Selected_agents, valid_indices, reasoning
            
        except Exception as e:
            logger.warning(f"LLMchooseAgentfail,Use default selection: {e}")
            # Fallback: select top Nindividual
            Selected = profiles[:max_agents]
            indices = list(range(min(max_agents, len(profiles))))
            return Selected, indices, "Use default selection strategy"
    
    def _generate_interview_questions(
        self,
        interview_requirement: str,
        simulation_requirement: str,
        Selected_agents: List[Dict[str, Any]]
    ) -> List[str]:
        """useLLMGenerate interview questions"""
        
        agent_roles = [a.get("profession", "unknown") for a in Selected_agents]
        
        system_prompt = """You are a professional journalist/interviewer. Based on the interview needs, generate 3-5 in-depth interview questions.

Question request:
1. open question,Detailed answers are encouraged
2. There may be different answers for different roles
3. cover the facts,point of view,Feelings and other dimensions
4. natural language,like a real interview
5. Each problem is controlled within50Within words,concise and clear
6. direct question,Do not include background notes or prefixes

returnJSONFormat:{"questions": ["question1", "question2", ...]}"""

        user_prompt = f"""Interview requirements:{interview_requirement}

Analog background:{simulation_requirement if simulation_requirement else "Not provided"}

interviewee role:{', '.join(agent_roles)}

Please generate3-5interview questions."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5
            )
            
            return response.get("questions", [f"about{interview_requirement},what do you think?"])
            
        except Exception as e:
            logger.warning(f"Failed to generate interview questions: {e}")
            return [
                f"about{interview_requirement},what is your point of view?",
                "How does this affect you or the group you represent??",
                "How do you think this problem should be solved or improved??"
            ]
    
    def _generate_interview_summary(
        self,
        interviews: List[AgentInterview],
        interview_requirement: str
    ) -> str:
        """Generate interview summary"""
        
        if not interviews:
            return "No interviews completed"
        
        # Collect all interviews
        interview_texts = []
        for interview in interviews:
            interview_texts.append(f"[{interview.agent_name}({interview.agent_role})]\n{interview.response[:500]}")
        
        system_prompt = """You are a professional news editor.Please base your answers on multiple respondents,Generate an interview summary.

Abstract requirements:
1. Extract the main points of view of all parties
2. Point out consensus and differences of opinion
3. Highlight valuable quotes
4. objective and neutral,Don't take sides
5. controlled in1000within the word

format constraints(Must comply with):
- Use plain text paragraphs,Separate different parts with blank lines
- Do not useMarkdowntitle(like#,##,###)
- Don't use dividing lines(like---,***)
- Use quotation marks when quoting the interviewee’s original words
- Can be used**Bold**Mark keywords,but don't use otherMarkdowngrammar"""

        user_prompt = f"""Interview topics:{interview_requirement}

Interview content:
{"".join(interview_texts)}

Please generate interview summary."""

        try:
            summary = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            return summary
            
        except Exception as e:
            logger.warning(f"Failed to generate interview summary: {e}")
            # Downgrade:Simple splicing
            return f"Interviewed in total{len(interviews)}respondents,include:" + ",".join([i.agent_name for i in interviews])
