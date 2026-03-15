"""
OASIS agent profiles Generator
Converts Zep graph entities into the agent profiles format required by the OASIS simulation platform.

Optimization and improvement:
1. Call Zep search function to enrich node information
2. Optimize prompts to generate very detailed characters
3. Distinguish between personal entities and abstract group entities
"""

import json
import random
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from zep_cloud.client import Zep

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('mirofish.oasis_profile')


@dataclass
class OasisAgentProfile:
    """OASIS agent profiles data structure"""
    # Common fields
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str
    
    # Optional fields - Reddit style
    karma: int = 1000
    
    # Optional fields - Twitter style
    friend_count: int = 100
    follower_count: int = 150
    statuses_count: int = 500
    
    # Additional character information
    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    interested_topics: List[str] = field(default_factory=list)
    
    # Source entity information
    source_entity_uuid: Optional[str] = None
    source_entity_type: Optional[str] = None
    
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    
    def to_reddit_format(self) -> Dict[str, Any]:
        """Convert to Reddit platform format"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS library requires the field name to be "username" (no underscore)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at,
        }

        # Add additional personality information (if available)
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_twitter_format(self) -> Dict[str, Any]:
        """Convert to Twitter platform format"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS library requires the field name to be "username" (no underscore)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "created_at": self.created_at,
        }
        
        # Add additional personality information
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to full dictionary format"""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
            "profession": self.profession,
            "interested_topics": self.interested_topics,
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "created_at": self.created_at,
        }


class OasisProfileGenerator:
    """
    OASIS Profile Generator

    Converts Zep graph entities into the agent profiles required by OASIS simulation.

    Optimization features:
    1. Call Zep graph search capabilities for richer context
    2. Generate highly detailed personas (including basic info, career experience, character traits, social media behavior, etc.)
    3. Distinguish between personal entities and abstract group entities
    """
    
    # MBTI type list
    MBTI_TYPES = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP"
    ]
    
    # List of common countries
    COUNTRIES = [
        "China", "US", "UK", "Japan", "Germany", "France", 
        "Canada", "Australia", "Brazil", "India", "South Korea"
    ]
    
    # Person type entity (needs specific persona generation)
    INDIVIDUAL_ENTITY_TYPES = [
        "student", "alumni", "professor", "person", "publicfigure", 
        "expert", "faculty", "official", "journalist", "activist"
    ]
    
    # Group/organization type entity (needs group representative persona generation)
    GROUP_ENTITY_TYPES = [
        "university", "governmentagency", "organization", "ngo", 
        "mediaoutlet", "company", "institution", "group", "community"
    ]
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        zep_api_key: Optional[str] = None,
        graph_id: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME

        self.llm = LLMClient(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model_name
        )
        
        # Zep client used to retrieve rich context
        self.zep_api_key = zep_api_key or Config.ZEP_API_KEY
        self.zep_client = None
        self.graph_id = graph_id
        
        if self.zep_api_key:
            try:
                self.zep_client = Zep(api_key=self.zep_api_key)
            except Exception as e:
                logger.warning(f"Zep client initialization failed: {e}")
    
    def generate_profile_from_entity(
        self, 
        entity: EntityNode, 
        user_id: int,
        use_llm: bool = True
    ) -> OasisAgentProfile:
        """
        Generate an OASIS agent profiles from a Zep entity.

        Args:
            entity: Zep entity node
            user_id: User ID (used for OASIS)
            use_llm: Whether to use LLM to generate detailed persona

        Returns:
            OasisAgentProfile
        """
        entity_type = entity.get_entity_type() or "Entity"
        
        # Basic information
        name = entity.name
        user_name = self._generate_username(name)
        
        # Build contextual information
        context = self._build_entity_context(entity)
        
        if use_llm:
            # Use LLM to generate detailed persona
            profile_data = self._generate_profile_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context
            )
        else:
            # Use rules to generate basic characters
            profile_data = self._generate_profile_rule_based(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes
            )
        
        return OasisAgentProfile(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=profile_data.get("bio", f"{entity_type}: {name}"),
            persona=profile_data.get("persona", entity.summary or f"A {entity_type} named {name}."),
            karma=profile_data.get("karma", random.randint(500, 5000)),
            friend_count=profile_data.get("friend_count", random.randint(50, 500)),
            follower_count=profile_data.get("follower_count", random.randint(100, 1000)),
            statuses_count=profile_data.get("statuses_count", random.randint(100, 2000)),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            mbti=profile_data.get("mbti"),
            country=profile_data.get("country"),
            profession=profile_data.get("profession"),
            interested_topics=profile_data.get("interested_topics", []),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
        )
    
    def _generate_username(self, name: str) -> str:
        """Generate username"""
        # Remove special characters, convert to lowercase
        username = name.lower().replace(" ", "_")
        username = ''.join(c for c in username if c.isalnum() or c == '_')
        
        # Add random suffix to avoid duplicates
        suffix = random.randint(100, 999)
        return f"{username}_{suffix}"
    
    def _search_zep_for_entity(self, entity: EntityNode) -> Dict[str, Any]:
        """
        Use Zep graph hybrid search to obtain rich information related to entities.

        Zep has no built-in hybrid search interface, so edges and nodes must be searched
        separately and then merged. Parallel requests are used for efficiency.

        Args:
            entity: Entity node object

        Returns:
            Dictionary containing facts, node_summaries, and context
        """
        import concurrent.futures
        
        if not self.zep_client:
            return {"facts": [], "node_summaries": [], "context": ""}
        
        entity_name = entity.name
        
        results = {
            "facts": [],
            "node_summaries": [],
            "context": ""
        }
        
        # Must have graph_id to search
        if not self.graph_id:
            logger.debug(f"Skipping Zep search: graph_id not set")
            return results
        
        comprehensive_query = f"All information about {entity_name}, activities, events, relationships, and context"
        
        def search_edges():
            """Search edges (facts/relations) - with retry mechanism"""
            max_retries = 3
            last_exception = None
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=30,
                        scope="edges",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"Zep edge search attempt {attempt + 1} failed: {str(e)[:80]}, retrying...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"Zep edge search failed after {max_retries} attempts: {e}")
            return None
        
        def search_nodes():
            """Search nodes (entity summaries) - with retry mechanism"""
            max_retries = 3
            last_exception = None
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=20,
                        scope="nodes",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"Zep node search attempt {attempt + 1} failed: {str(e)[:80]}, retrying...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"Zep node search failed after {max_retries} attempts: {e}")
            return None
        
        try:
            # Execute edges and nodes search in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                edge_future = executor.submit(search_edges)
                node_future = executor.submit(search_nodes)
                
                # Get results
                edge_result = edge_future.result(timeout=30)
                node_result = node_future.result(timeout=30)
            
            # Processing edge search results
            all_facts = set()
            if edge_result and hasattr(edge_result, 'edges') and edge_result.edges:
                for edge in edge_result.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        all_facts.add(edge.fact)
            results["facts"] = list(all_facts)
            
            # Process node search results
            all_summaries = set()
            if node_result and hasattr(node_result, 'nodes') and node_result.nodes:
                for node in node_result.nodes:
                    if hasattr(node, 'summary') and node.summary:
                        all_summaries.add(node.summary)
                    if hasattr(node, 'name') and node.name and node.name != entity_name:
                        all_summaries.add(f"related entities: {node.name}")
            results["node_summaries"] = list(all_summaries)
            
            # Build comprehensive context
            context_parts = []
            if results["facts"]:
                context_parts.append("factual information:\n" + "\n".join(f"- {f}" for f in results["facts"][:20]))
            if results["node_summaries"]:
                context_parts.append("related entities:\n" + "\n".join(f"- {s}" for s in results["node_summaries"][:10]))
            results["context"] = "\n\n".join(context_parts)
            
            logger.info(f"Zep hybrid search completed: {entity_name}, found {len(results['facts'])} facts, {len(results['node_summaries'])} related nodes")
            
        except concurrent.futures.TimeoutError:
            logger.warning(f"Zep retrieval timeout ({entity_name})")
        except Exception as e:
            logger.warning(f"Zep retrieval failed ({entity_name}): {e}")
        
        return results
    
    def _build_entity_context(self, entity: EntityNode) -> str:
        """
        Build complete contextual information for an entity.

        Includes:
        1. The entity's own factual information
        2. Details of associated nodes
        3. Rich information from Zep hybrid search
        """
        context_parts = []
        
        # 1. Add entity attribute information
        if entity.attributes:
            attrs = []
            for key, value in entity.attributes.items():
                if value and str(value).strip():
                    attrs.append(f"- {key}: {value}")
            if attrs:
                context_parts.append("### Entity properties\n" + "\n".join(attrs))
        
        # 2. Add relevant factual information (facts/relations)
        existing_facts = set()
        if entity.related_edges:
            relationships = []
            for edge in entity.related_edges:  # No limit on quantity
                fact = edge.get("fact", "")
                edge_name = edge.get("edge_name", "")
                direction = edge.get("direction", "")
                
                if fact:
                    relationships.append(f"- {fact}")
                    existing_facts.add(fact)
                elif edge_name:
                    if direction == "outgoing":
                        relationships.append(f"- {entity.name} --[{edge_name}]--> (related entities)")
                    else:
                        relationships.append(f"- (related entities) --[{edge_name}]--> {entity.name}")
            
            if relationships:
                context_parts.append("### Relevant facts and relationships\n" + "\n".join(relationships))
        
        # 3. Add details of associated nodes
        if entity.related_nodes:
            related_info = []
            for node in entity.related_nodes:  # No limit on quantity
                node_name = node.get("name", "")
                node_labels = node.get("labels", [])
                node_summary = node.get("summary", "")
                
                # Filter out default tags
                custom_labels = [l for l in node_labels if l not in ["Entity", "Node"]]
                label_str = f" ({', '.join(custom_labels)})" if custom_labels else ""
                
                if node_summary:
                    related_info.append(f"- **{node_name}**{label_str}: {node_summary}")
                else:
                    related_info.append(f"- **{node_name}**{label_str}")
            
            if related_info:
                context_parts.append("### Related entity information\n" + "\n".join(related_info))
        
        # 4. Use Zep hybrid search for richer information
        zep_results = self._search_zep_for_entity(entity)
        
        if zep_results.get("facts"):
            # Remove duplicates: exclude existing facts
            new_facts = [f for f in zep_results["facts"] if f not in existing_facts]
            if new_facts:
                context_parts.append("### Zep retrieved factual information\n" + "\n".join(f"- {f}" for f in new_facts[:15]))
        
        if zep_results.get("node_summaries"):
            context_parts.append("### Zep retrieved related nodes\n" + "\n".join(f"- {s}" for s in zep_results["node_summaries"][:10]))
        
        return "\n\n".join(context_parts)
    
    def _is_individual_entity(self, entity_type: str) -> bool:
        """Determine whether this is a personal type entity"""
        return entity_type.lower() in self.INDIVIDUAL_ENTITY_TYPES
    
    def _is_group_entity(self, entity_type: str) -> bool:
        """Determine whether this is a group/organization type entity"""
        return entity_type.lower() in self.GROUP_ENTITY_TYPES
    
    def _generate_profile_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        Use LLM to generate highly detailed personas.

        Distinguishes based on entity type:
        - Personal entity: Generate specific character settings
        - Group/institutional entity: Generate representative account settings
        """
        
        is_individual = self._is_individual_entity(entity_type)
        
        if is_individual:
            prompt = self._build_individual_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        else:
            prompt = self._build_group_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )

        # Try to generate multiple times, until successful or maximum retries reached
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                messages = [
                    {"role": "system", "content": self._get_system_prompt(is_agents)},
                    {"role": "user", "content": prompt}
                ]
                result = self.llm.chat_json(
                    messages=messages,
                    temperature=0.7 - (attempt * 0.1),
                    max_tokens=8192
                )

                # Validate required fields
                if "bio" not in result or not result["bio"]:
                    result["bio"] = entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"
                if "persona" not in result or not result["persona"]:
                    result["persona"] = entity_summary or f"{entity_name} is a {entity_type}."

                return result

            except ValueError as ve:
                logger.warning(f"JSON parsing failed (attempt {attempt+1}): {str(ve)[:80]}")

                # Try to extract the original content from the error and fix it
                error_msg = str(ve)
                if "LLM returned invalid JSON:" in error_msg:
                    raw_content = error_msg.split("LLM returned invalid JSON:", 1)[1].strip()
                    result = self._try_fix_json(raw_content, entity_name, entity_type, entity_summary)
                    if result.get("_fixed"):
                        del result["_fixed"]
                        return result

                last_error = ve

            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(1 * (attempt + 1))
        
        logger.warning(f"LLM failed to generate character ({max_attempts} attempts): {last_error}, falling back to rule-based generation")
        return self._generate_profile_rule_based(
            entity_name, entity_type, entity_summary, entity_attributes
        )
    
    def _fix_truncated_json(self, content: str) -> str:
        """Fix truncated JSON (output cut off by max_tokens limit)"""
        import re
        
        # If JSON is truncated, try to close it
        content = content.strip()
        
        # Count unclosed parentheses
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # Check if there is an unclosed string
        # Simple check: if there is no comma or closing bracket after the last quote, the string may be truncated
        if content and content[-1] not in '",}]':
            # Try to close the string
            content += '"'
        
        # Close brackets
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_json(self, content: str, entity_name: str, entity_type: str, entity_summary: str = "") -> Dict[str, Any]:
        """Try to repair broken JSON"""
        import re
        
        # 1. First try to fix the truncated case
        content = self._fix_truncated_json(content)
        
        # 2. Try to extract JSON part
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # 3. Dealing with newline characters in strings
            # Find all string values ​​and replace newlines in them
            def fix_string_newlines(match):
                s = match.group(0)
                # Replace actual newlines within a string with spaces
                s = s.replace('\n', ' ').replace('\r', ' ')
                # Replace extra spaces
                s = re.sub(r'\s+', ' ', s)
                return s
            
            # Match JSON string values
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string_newlines, json_str)
            
            # 4. Try to parse
            try:
                result = json.loads(json_str)
                result["_fixed"] = True
                return result
            except json.JSONDecodeError as e:
                # 5. If it still fails, try a more aggressive fix
                try:
                    # Remove all control characters
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                    # Replace all consecutive whitespace
                    json_str = re.sub(r'\s+', ' ', json_str)
                    result = json.loads(json_str)
                    result["_fixed"] = True
                    return result
                except:
                    pass
        
        # 6. Try to extract some information from the content
        bio_match = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
        persona_match = re.search(r'"persona"\s*:\s*"([^"]*)', content)  # may be truncated
        
        bio = bio_match.group(1) if bio_match else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}")
        persona = persona_match.group(1) if persona_match else (entity_summary or f"{entity_name} is a {entity_type}.")

        # If meaningful content is extracted, mark as fixed
        if bio_match or persona_match:
            logger.info(f"from damagedJSONSome information was extracted from")
            return {
                "bio": bio,
                "persona": persona,
                "_fixed": True
            }
        
        # 7. complete failure,Return to infrastructure
        logger.warning(f"JSONRepair failed,Return to infrastructure")
        return {
            "bio": entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name}is a{entity_type}."
        }
    
    def _get_system_prompt(self, is_individual: bool) -> str:
        """Get system prompt words"""
        base_prompt = "You are an expert in generating social media personas.Generate detailed,Real characters are used for public opinion simulation,Restore existing reality to the greatest extent possible.Must return a validJSONFormat,All string values ​​cannot contain unescaped newlines.Use Chinese."
        return base_prompt
    
    def _build_individual_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """Construct detailed personality prompts for personal entities"""
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "none"
        context_str = context[:3000] if context else "no additional context"
        
        return f"""Generate detailed social media personas for entities,Restore existing reality to the greatest extent possible.

Entity name: {entity_name}
Entity type: {entity_type}
Entity summary: {entity_summary}
Entity properties: {attrs_str}

contextual information:
{context_str}

Please generateJSON,Contains the following fields:

1. bio: Introduction to social media,200Character
2. persona: Detailed character description(2000plain text of word),Need to include:
   - Basic information(age,Profession,Educational background,location)
   - Character background(important experience,association with events,social relations)
   - Character traits(MBTItype,core character,emotional expression)
   - social media behavior(Post frequency,Content preferences,interactive style,language features)
   - standpoint(attitude towards the topic,may be irritated/touching content)
   - unique characteristics(mantra,special experience,personal hobbies)
   - personal memory(important part of personality,To introduce the relationship between this individual and the event,and the individual’s actions and reactions in the event.)
3. age: age number(Must be an integer)
4. gender: gender,Must be in English: "male" or "female"
5. mbti: MBTItype(likeINTJ,ENFPwait)
6. country: nation(Use Chinese,like"China")
7. profession: Profession
8. interested_topics: array of interesting topics

important:
- All field values ​​must be strings or numbers,Don't use newline characters
- personaMust be a coherent text description
- Use Chinese(Apart fromgenderFields must be in Englishmale/female)
- Content should be consistent with entity information
- ageMust be a valid integer,gendermust be"male"or"female"
"""

    def _build_group_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """Build a group/Detailed personal prompts for institutional entities"""
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "none"
        context_str = context[:3000] if context else "no additional context"
        
        return f"""for institutions/Group entities generate detailed social media account settings,Restore existing reality to the greatest extent possible.

Entity name: {entity_name}
Entity type: {entity_type}
Entity summary: {entity_summary}
Entity properties: {attrs_str}

contextual information:
{context_str}

Please generateJSON,Contains the following fields:

1. bio: Official account introduction,200Character,Professional and decent
2. persona: Detailed account setting description(2000plain text of word),Need to include:
   - Basic information of the organization(official name,Institutional nature,Establishment background,Main functions)
   - Account positioning(Account type,target audience,Core functions)
   - speaking style(language features,Common expressions,Taboo topics)
   - Features of published content(Content type,Release frequency,Active time period)
   - stance(Official stance on core topics,How to deal with disputes)
   - Special instructions(Portrait of a representative group,Operational habits)
   - institutional memory(An important part of the organization’s personality,To introduce the relationship between this organization and the event,and the organization’s actions and reactions during the incident.)
3. age: Fixed filling30(Virtual age of organization account)
4. gender: Fixed filling"other"(Institutional account useothermeans impersonal)
5. mbti: MBTItype,Used to describe account style,likeISTJRepresents strictness and conservatism
6. country: nation(Use Chinese,like"China")
7. profession: Organizational Function Description
8. interested_topics: array of areas of concern

important:
- All field values ​​must be strings or numbers,not allowednullvalue
- personaMust be a coherent text description,Don't use newline characters
- Use Chinese(Apart fromgenderFields must be in English"other")
- ageMust be an integer30,genderMust be a string"other"
- Speeches from institutional accounts must conform to their identity and positioning"""
    
    def _generate_profile_rule_based(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use rules to generate basic characters"""
        
        # Generate different personas based on entity types
        entity_type_lower = entity_type.lower()
        
        if entity_type_lower in ["student", "alumni"]:
            return {
                "bio": f"{entity_type} with interests in academics and social issues.",
                "persona": f"{entity_name} is a {entity_type.lower()} who is actively engaged in academic and social discussions. They enjoy sharing perspectives and connecting with peers.",
                "age": random.randint(18, 30),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": "Student",
                "interested_topics": ["Education", "Social Issues", "Technology"],
            }
        
        elif entity_type_lower in ["publicfigure", "expert", "faculty"]:
            return {
                "bio": f"Expert and thought leader in their field.",
                "persona": f"{entity_name} is a recognized {entity_type.lower()} who shares insights and opinions on important matters. They are known for their expertise and influence in public discourse.",
                "age": random.randint(35, 60),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(["ENTJ", "INTJ", "ENTP", "INTP"]),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_attributes.get("occupation", "Expert"),
                "interested_topics": ["Politics", "Economics", "Culture & Society"],
            }
        
        elif entity_type_lower in ["mediaoutlet", "socialmediaplatform"]:
            return {
                "bio": f"Official account for {entity_name}. News and updates.",
                "persona": f"{entity_name} is a media entity that reports news and facilitates public discourse. The account shares timely updates and engages with the audience on current events.",
                "age": 30,  # Institutional virtual age
                "gender": "other",  # Institutional useother
                "mbti": "ISTJ",  # institutional style:Strict and conservative
                "country": "China",
                "profession": "Media",
                "interested_topics": ["General News", "Current Events", "Public Affairs"],
            }
        
        elif entity_type_lower in ["university", "governmentagency", "ngo", "organization"]:
            return {
                "bio": f"Official account of {entity_name}.",
                "persona": f"{entity_name} is an institutional entity that communicates official positions, announcements, and engages with stakeholders on relevant matters.",
                "age": 30,  # Institutional virtual age
                "gender": "other",  # Institutional useother
                "mbti": "ISTJ",  # institutional style:Strict and conservative
                "country": "China",
                "profession": entity_type,
                "interested_topics": ["Public Policy", "Community", "Official Announcements"],
            }
        
        else:
            # Default persona
            return {
                "bio": entity_summary[:150] if entity_summary else f"{entity_type}: {entity_name}",
                "persona": entity_summary or f"{entity_name} is a {entity_type.lower()} participating in social discussions.",
                "age": random.randint(25, 50),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_type,
                "interested_topics": ["General", "Social Issues"],
            }
    
    def set_graph_id(self, graph_id: str):
        """Set up the mapIDused forZepSearch"""
        self.graph_id = graph_id
    
    def generate_profiles_from_entities(
        self,
        entities: List[EntityNode],
        use_llm: bool = True,
        progress_callback: Optional[callable] = None,
        graph_id: Optional[str] = None,
        parallel_count: int = 5,
        realtime_output_path: Optional[str] = None,
        output_platform: str = "reddit"
    ) -> List[OasisAgentProfile]:
        """
        Generate from entities in batchesagent profiles(Supports parallel builds)
        
        Args:
            entities: Entity list
            use_llm: Whether to useLLMGenerate detailed persona
            progress_callback: Progress callback function (current, total, message)
            graph_id: AtlasID,used forZepSearch for richer context
            parallel_count: Number of parallel builds,default5
            realtime_output_path: File path written in real time(If provided,Write every time one is generated)
            output_platform: Output platform format ("reddit" or "twitter")
            
        Returns:
            agent profileslist
        """
        import concurrent.futures
        from threading import Lock
        
        # set upgraph_idused forZepSearch
        if graph_id:
            self.graph_id = graph_id
        
        total = len(entities)
        profiles = [None] * total  # Pre-allocated list maintains order
        completed_count = [0]  # Use lists for modification in closures
        lock = Lock()
        
        # Auxiliary function for writing files in real time
        def save_profiles_realtime():
            """Save the generated profiles to file"""
            if not realtime_output_path:
                return
            
            with lock:
                # Filter out generated profiles
                existing_profiles = [p for p in profiles if p is not None]
                if not existing_profiles:
                    return
                
                try:
                    if output_platform == "reddit":
                        # Reddit JSON Format
                        profiles_data = [p.to_reddit_format() for p in existing_profiles]
                        with open(realtime_output_path, 'w', encoding='utf-8') as f:
                            json.dump(profiles_data, f, ensure_ascii=False, indent=2)
                    else:
                        # Twitter CSV Format
                        import csv
                        profiles_data = [p.to_twitter_format() for p in existing_profiles]
                        if profiles_data:
                            fieldnames = list(profiles_data[0].keys())
                            with open(realtime_output_path, 'w', encoding='utf-8', newline='') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                writer.writerows(profiles_data)
                except Exception as e:
                    logger.warning(f"Save in real time profiles fail: {e}")
        
        def generate_single_profile(idx: int, entity: EntityNode) -> tuple:
            """Generate a singleprofileworking function"""
            entity_type = entity.get_entity_type() or "Entity"
            
            try:
                profile = self.generate_profile_from_entity(
                    entity=entity,
                    user_id=idx,
                    use_llm=use_llm
                )
                
                # Real-time output of the generated personality to the console and logs
                self._print_generated_profile(entity.name, entity_type, profile)
                
                return idx, profile, None
                
            except Exception as e:
                logger.error(f"Generate entity {entity.name} The persona failed: {str(e)}")
                # create a baseprofile
                fallback_profile = OasisAgentProfile(
                    user_id=idx,
                    user_name=self._generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity_type}: {entity.name}",
                    persona=entity.summary or f"A participant in social discussions.",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity_type,
                )
                return idx, fallback_profile, str(e)
        
        logger.info(f"Starting parallel build of {total}  agentsPersonality(Parallel number: {parallel_count})...")
        print(f"\n{'='*60}")
        print(f"Start generatingAgentPersonality - common {total} entities,Parallel number: {parallel_count}")
        print(f"{'='*60}\n")
        
        # Parallel execution using thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
            # Submit all tasks
            future_to_entity = {
                executor.submit(generate_single_profile, idx, entity): (idx, entity)
                for idx, entity in enumerate(entities)
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_entity):
                idx, entity = future_to_entity[future]
                entity_type = entity.get_entity_type() or "Entity"
                
                try:
                    result_idx, profile, error = future.result()
                    profiles[result_idx] = profile
                    
                    with lock:
                        completed_count[0] += 1
                        current = completed_count[0]
                    
                    # Write files in real time
                    save_profiles_realtime()
                    
                    if progress_callback:
                        progress_callback(
                            current, 
                            total, 
                            f"Completed {current}/{total}: {entity.name}({entity_type})"
                        )
                    
                    if error:
                        logger.warning(f"[{current}/{total}] {entity.name} Use alternate persona: {error}")
                    else:
                        logger.info(f"[{current}/{total}] Successfully generated character: {entity.name} ({entity_type})")
                        
                except Exception as e:
                    logger.error(f"Handle entities {entity.name} Exception occurs when: {str(e)}")
                    with lock:
                        completed_count[0] += 1
                    profiles[idx] = OasisAgentProfile(
                        user_id=idx,
                        user_name=self._generate_username(entity.name),
                        name=entity.name,
                        bio=f"{entity_type}: {entity.name}",
                        persona=entity.summary or "A participant in social discussions.",
                        source_entity_uuid=entity.uuid,
                        source_entity_type=entity_type,
                    )
                    # Write files in real time(Even as a backup persona)
                    save_profiles_realtime()
        
        print(f"\n{'='*60}")
        print(f"Profile generation completed! Generated {len([p for p in profiles if p])} agents")
        print(f"{'='*60}\n")
        
        return profiles
    
    def _print_generated_profile(self, entity_name: str, entity_type: str, profile: OasisAgentProfile):
        """Output the generated personality to the console in real time(full content,Do not truncate)"""
        separator = "-" * 70
        
        # Build the complete output content(Do not truncate)
        topics_str = ', '.join(profile.interested_topics) if profile.interested_topics else 'none'
        
        output_lines = [
            f"\n{separator}",
            f"[Generated] {entity_name} ({entity_type})",
            f"{separator}",
            f"username: {profile.user_name}",
            f"",
            f"[Introduction]",
            f"{profile.bio}",
            f"",
            f"[Detailed character design]",
            f"{profile.persona}",
            f"",
            f"[Basic properties]",
            f"age: {profile.age} | gender: {profile.gender} | MBTI: {profile.mbti}",
            f"Profession: {profile.profession} | nation: {profile.country}",
            f"Interesting topics: {topics_str}",
            separator
        ]
        
        output = "\n".join(output_lines)
        
        # Only output to console(avoid duplication,loggerNo longer output the complete content)
        print(output)
    
    def save_profiles(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """
        saveProfileto file(Choose the right format based on your platform)
        
        OASISPlatform format requirements:
        - Twitter: CSVFormat
        - Reddit: JSONFormat
        
        Args:
            profiles: Profilelist
            file_path: file path
            platform: Platform type ("reddit" or "twitter")
        """
        if platform == "twitter":
            self._save_twitter_csv(profiles, file_path)
        else:
            self._save_reddit_json(profiles, file_path)
    
    def _save_twitter_csv(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        saveTwitter ProfileforCSVFormat(conform toOASISofficial request)
        
        OASIS TwitterrequiredCSVField:
        - user_id: user ID (0-indexed, based on CSV order)
        - name: User real name
        - username: Username in the system
        - user_char: Detailed character description(Inject intoLLMSystem prompts,guideAgentBehavior)
        - description: short public profile(Displayed on user profile page)
        
        user_char vs description the difference:
        - user_char: Internal use,LLMSystem prompt,DecideAgenthow to think and act
        - description: external display,Profile visible to other users
        """
        import csv
        
        # Make sure the file extension is.csv
        if not file_path.endswith('.csv'):
            file_path = file_path.replace('.json', '.csv')
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # writeOASISrequired header
            headers = ['user_id', 'name', 'username', 'user_char', 'description']
            writer.writerow(headers)
            
            # Write data row
            for idx, profile in enumerate(profiles):
                # user_char: Complete character(bio + persona),used forLLMSystem prompt
                user_char = profile.bio
                if profile.persona and profile.persona != profile.bio:
                    user_char = f"{profile.bio} {profile.persona}"
                # Handling newlines(CSVReplace with spaces in)
                user_char = user_char.replace('\n', ' ').replace('\r', ' ')
                
                # description: short introduction,for external display
                description = profile.bio.replace('\n', ' ').replace('\r', ' ')
                
                row = [
                    idx,                    # user_id: from0starting orderID
                    profile.name,           # name: real name
                    profile.user_name,      # username: username
                    user_char,              # user_char: Complete character(internalLLMuse)
                    description             # description: short introduction(external display)
                ]
                writer.writerow(row)
        
        logger.info(f"Saved {len(profiles)} Twitter profiles to {file_path} (OASIS CSVFormat)")
    
    def _normalize_gender(self, gender: Optional[str]) -> str:
        """
        standardizationgenderThe fields areOASISRequired English format
        
        OASISRequire: male, female, other
        """
        if not gender:
            return "other"
        
        gender_lower = gender.lower().strip()
        
        # Chinese mapping
        gender_map = {
            "male": "male",
            "female": "female",
            "mechanism": "other",
            "other": "other",
            # Already available in English
            "male": "male",
            "female": "female",
            "other": "other",
        }
        
        return gender_map.get(gender_lower, "other")
    
    def _save_reddit_json(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        saveReddit ProfileforJSONFormat
        
        Use with to_reddit_format() consistent format,make sure OASIS can be read correctly.
        must contain user_id Field,This is OASIS agent_graph.get_agent() matching key!
        
        Required fields:
        - user_id: userID(integer,for matching initial_posts in poster_agent_id)
        - username: username
        - name: display name
        - bio: Introduction
        - persona: Detailed character design
        - age: age(integer)
        - gender: "male", "female", or "other"
        - mbti: MBTItype
        - country: nation
        """
        data = []
        for idx, profile in enumerate(profiles):
            # Use with to_reddit_format() consistent format
            item = {
                "user_id": profile.user_id if profile.user_id is not None else idx,  # key:must contain user_id
                "username": profile.user_name,
                "name": profile.name,
                "bio": profile.bio[:150] if profile.bio else f"{profile.name}",
                "persona": profile.persona or f"{profile.name} is a participant in social discussions.",
                "karma": profile.karma if profile.karma else 1000,
                "created_at": profile.created_at,
                # OASISRequired fields - Make sure there are default values
                "age": profile.age if profile.age else 30,
                "gender": self._normalize_gender(profile.gender),
                "mbti": profile.mbti if profile.mbti else "ISTJ",
                "country": profile.country if profile.country else "China",
            }
            
            # optional fields
            if profile.profession:
                item["profession"] = profile.profession
            if profile.interested_topics:
                item["interested_topics"] = profile.interested_topics
            
            data.append(item)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(profiles)} Reddit profiles to {file_path} (JSONFormat,Includeuser_idField)")
    
    # Keep old method names as aliases,Stay backwards compatible
    def save_profiles_to_json(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """[Deprecated] Please use save_profiles() method"""
        logger.warning("save_profiles_to_json is deprecated. Use save_profiles method instead")
        self.save_profiles(profiles, file_path, platform)

