"""
Report AgentServe
useLangChain + ZepaccomplishReACTModel simulation report generation

Function:
1. Based on simulation needs andZepSpectrum information generation report
2. Plan the directory structure first,Then generate it in sections
3. Each paragraph usesReACTMultiple rounds of thinking and reflection mode
4. Support dialogue with users,Call search tools autonomously during conversations
"""

import os
import json
import time
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .zep_tools import (
    ZepToolsService, 
    SearchResult, 
    InsightForgeResult, 
    PanoramaResult,
    InterviewResult
)

logger = get_logger('mirofish.report_agent')


class ReportLogger:
    """
    Report Agent Verbose logger
    
    Generate in report folder agent_log.jsonl document,Record every detailed action.
    Each line is a complete JSON object,Contains timestamp,action type,Details, etc..
    """
    
    def __init__(self, report_id: str):
        """
        Initialize the logger
        
        Args:
            report_id: ReportID,Used to determine the log file path
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, 'reports', report_id, 'agent_log.jsonl'
        )
        self.start_time = datetime.now()
        self._ensure_log_file()
    
    def _ensure_log_file(self):
        """Make sure the directory where the log file is located exists"""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def _get_elapsed_time(self) -> float:
        """Get the elapsed time from start to now(Second)"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def log(
        self, 
        action: str, 
        stage: str,
        details: Dict[str, Any],
        section_title: str = None,
        section_index: int = None
    ):
        """
        record a log
        
        Args:
            action: action type,like 'start', 'tool_call', 'llm_response', 'section_complete' wait
            stage: current stage,like 'planning', 'generating', 'completed'
            details: Detailed content dictionary,Do not truncate
            section_title: Current chapter title(Optional)
            section_index: Current chapter index(Optional)
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": round(self._get_elapsed_time(), 2),
            "report_id": self.report_id,
            "action": action,
            "stage": stage,
            "section_title": section_title,
            "section_index": section_index,
            "details": details
        }
        
        # append write JSONL document
        with open(self.log_file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def log_start(self, simulation_id: str, graph_id: str, simulation_requirement: str):
        """Logging report generation starts"""
        self.log(
            action="report_start",
            stage="pending",
            details={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "simulation_requirement": simulation_requirement,
                "message": "Report generation task starts"
            }
        )
    
    def log_planning_start(self):
        """Record Outline Planning Begins"""
        self.log(
            action="planning_start",
            stage="planning",
            details={"message": "Start planning your report outline"}
        )
    
    def log_planning_context(self, context: Dict[str, Any]):
        """Record contextual information obtained during planning"""
        self.log(
            action="planning_context",
            stage="planning",
            details={
                "message": "Get simulation context information",
                "context": context
            }
        )
    
    def log_planning_complete(self, outline_dict: Dict[str, Any]):
        """Record outline planning completed"""
        self.log(
            action="planning_complete",
            stage="planning",
            details={
                "message": "Outline planning completed",
                "outline": outline_dict
            }
        )
    
    def log_section_start(self, section_title: str, section_index: int):
        """Record chapter generation starts"""
        self.log(
            action="section_start",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={"message": f"Start generating chapters: {section_title}"}
        )
    
    def log_react_thought(self, section_title: str, section_index: int, iteration: int, thought: str):
        """Record ReACT thought process"""
        self.log(
            action="react_thought",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "thought": thought,
                "message": f"ReACT No.{iteration}round of thinking"
            }
        )
    
    def log_tool_call(
        self, 
        section_title: str, 
        section_index: int,
        tool_name: str, 
        parameters: Dict[str, Any],
        iteration: int
    ):
        """Logging tool calls"""
        self.log(
            action="tool_call",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "parameters": parameters,
                "message": f"Call tool: {tool_name}"
            }
        )
    
    def log_tool_result(
        self,
        section_title: str,
        section_index: int,
        tool_name: str,
        result: str,
        iteration: int
    ):
        """Record tool call results(full content,Do not truncate)"""
        self.log(
            action="tool_result",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "result": result,  # full results,Do not truncate
                "result_length": len(result),
                "message": f"tool {tool_name} Return results"
            }
        )
    
    def log_llm_response(
        self,
        section_title: str,
        section_index: int,
        response: str,
        iteration: int,
        has_tool_calls: bool,
        has_final_answer: bool
    ):
        """Record LLM response(full content,Do not truncate)"""
        self.log(
            action="llm_response",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "response": response,  # full response,Do not truncate
                "response_length": len(response),
                "has_tool_calls": has_tool_calls,
                "has_final_answer": has_final_answer,
                "message": f"LLM response (Tool call: {has_tool_calls}, final answer: {has_final_answer})"
            }
        )
    
    def log_section_content(
        self,
        section_title: str,
        section_index: int,
        content: str,
        tool_calls_count: int
    ):
        """Record chapter content generation completed(Only record content,Does not mean the entire chapter is complete)"""
        self.log(
            action="section_content",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": content,  # full content,Do not truncate
                "content_length": len(content),
                "tool_calls_count": tool_calls_count,
                "message": f"chapter {section_title} Content generation completed"
            }
        )
    
    def log_section_full_complete(
        self,
        section_title: str,
        section_index: int,
        full_content: str
    ):
        """
        Record chapter generation completed

        The front end should listen to this log to determine whether a chapter is actually completed,and get full content
        """
        self.log(
            action="section_complete",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": full_content,
                "content_length": len(full_content),
                "message": f"chapter {section_title} Generation completed"
            }
        )
    
    def log_report_complete(self, total_sections: int, total_time_seconds: float):
        """Record report generation completed"""
        self.log(
            action="report_complete",
            stage="completed",
            details={
                "total_sections": total_sections,
                "total_time_seconds": round(total_time_seconds, 2),
                "message": "Report generation completed"
            }
        )
    
    def log_error(self, error_message: str, stage: str, section_title: str = None):
        """Log errors"""
        self.log(
            action="error",
            stage=stage,
            section_title=section_title,
            section_index=None,
            details={
                "error": error_message,
                "message": f"An error occurred: {error_message}"
            }
        )


class ReportConsoleLogger:
    """
    Report Agent console logger
    
    Configure console style logging(INFO,WARNINGwait)written in the report folder console_log.txt document.
    These logs are related to agent_log.jsonl different,Is the console output in plain text format.
    """
    
    def __init__(self, report_id: str):
        """
        Initialize the console logger
        
        Args:
            report_id: ReportID,Used to determine the log file path
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, 'reports', report_id, 'console_log.txt'
        )
        self._ensure_log_file()
        self._file_handler = None
        self._setup_file_handler()
    
    def _ensure_log_file(self):
        """Make sure the directory where the log file is located exists"""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def _setup_file_handler(self):
        """Set up file handler,Write logs to file simultaneously"""
        import logging
        
        # Create file handler
        self._file_handler = logging.FileHandler(
            self.log_file_path,
            mode='a',
            encoding='utf-8'
        )
        self._file_handler.setLevel(logging.INFO)
        
        # Use the same concise format as the console
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        self._file_handler.setFormatter(formatter)
        
        # add to report_agent relevant logger
        loggers_to_attach = [
            'mirofish.report_agent',
            'mirofish.zep_tools',
        ]
        
        for logger_name in loggers_to_attach:
            target_logger = logging.getLogger(logger_name)
            # Avoid duplicate additions
            if self._file_handler not in target_logger.handlers:
                target_logger.addHandler(self._file_handler)
    
    def close(self):
        """Close the file processor and start from logger removed from"""
        import logging
        
        if self._file_handler:
            loggers_to_detach = [
                'mirofish.report_agent',
                'mirofish.zep_tools',
            ]
            
            for logger_name in loggers_to_detach:
                target_logger = logging.getLogger(logger_name)
                if self._file_handler in target_logger.handlers:
                    target_logger.removeHandler(self._file_handler)
            
            self._file_handler.close()
            self._file_handler = None
    
    def __del__(self):
        """Make sure to close the file handler on destruction"""
        self.close()


class ReportStatus(str, Enum):
    """Report status"""
    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportSection:
    """Report Chapter"""
    title: str
    content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content
        }

    def to_markdown(self, level: int = 2) -> str:
        """Convert toMarkdownFormat"""
        md = f"{'#' * level} {self.title}\n\n"
        if self.content:
            md += f"{self.content}\n\n"
        return md


@dataclass
class ReportOutline:
    """Report outline"""
    title: str
    summary: str
    sections: List[ReportSection]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections]
        }
    
    def to_markdown(self) -> str:
        """Convert toMarkdownFormat"""
        md = f"# {self.title}\n\n"
        md += f"> {self.summary}\n\n"
        for section in self.sections:
            md += section.to_markdown()
        return md


@dataclass
class Report:
    """full report"""
    report_id: str
    simulation_id: str
    graph_id: str
    simulation_requirement: str
    status: ReportStatus
    outline: Optional[ReportOutline] = None
    markdown_content: str = ""
    created_at: str = ""
    completed_at: str = ""
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "status": self.status.value,
            "outline": self.outline.to_dict() if self.outline else None,
            "markdown_content": self.markdown_content,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error
        }


# ═══════════════════════════════════════════════════════════════
# Prompt Template constants
# ═══════════════════════════════════════════════════════════════

# ── Tool description ──

TOOL_DESC_INSIGHT_FORGE = """\
[Deep insight search - Powerful search tools]
This is our powerful retrieval function,Designed for in-depth analysis.it will:
1. Automatically break your problem into sub-problems
2. Retrieve information from simulation maps in multiple dimensions
3. Integrate semantic search,entity analysis,Relationship chain tracking results
4. Return to the most comprehensive,The deepest search content

[Usage scenarios]
- Need to analyze a topic in depth
- Need to understand multiple aspects of an event
- Need to obtain rich materials to support the report chapters

[Return content]
- Relevant facts original text(Can be quoted directly)
- Core Entity Insights
- Relationship chain analysis"""

TOOL_DESC_PANORAMA_SEARCH = """\
[breadth search - Get a full view]
This tool is used to get a complete picture of the simulation results,Particularly suitable for understanding the evolution of events.it will:
1. Get all relevant nodes and relationships
2. Distinguish between currently valid facts and history/Expired facts
3. Help you understand how public opinion evolves

[Usage scenarios]
- Need to understand the complete development of the incident
- Need to compare changes in public opinion at different stages
- Need to obtain comprehensive entity and relationship information

[Return content]
- current valid facts(Simulate the latest results)
- history/expired fact(Evolution record)
- all entities involved"""

TOOL_DESC_QUICK_SEARCH = """\
[Simple search - Quick search]
Lightweight fast search tool,Suitable for simplicity,direct information inquiry.

[Usage scenarios]
- Need to find specific information quickly
- Need to verify a fact
- Simple information retrieval

[Return content]
- List of facts most relevant to the query"""

TOOL_DESC_INTERVIEW_AGENTS = """\
[In-depth interview - real agent interview (dual-platform)]
callOASISInterview in a simulated environmentAPI,for a running simulationAgentconduct real interviews!
this is notLLMsimulation,Instead, call the real interview interface to obtain the simulationAgentoriginal answer.
Default inTwitterandRedditInterview on two platforms simultaneously,Get a more comprehensive view.

Functional flow:
1. Automatically read character files,Learn about all simulationsAgent
2. Intelligent selection of the most relevant to the interview topicAgent(such as students,media,Official, etc.)
3. Automatically generate interview questions
4. call /api/simulation/interview/batch Interface for real interviews on dual platforms
5. Integrate all interview results,Provide multi-perspective analysis

[Usage scenarios]
- Need to understand events from different role perspectives(What do students think??What does the media think??What does the official say??)
- Need to collect opinions and positions from multiple parties
- Need to get simulationAgentreal answer(fromOASISsimulated environment)
- Want to make the report more vivid,Include"Interview transcript"

[Return content]
- be interviewedAgentidentity information
- each agent's interview answers from both Twitter and Reddit platforms
- Key Quotes(Can be quoted directly)
- Interview summary and perspective comparison

[important]needOASISThe simulation environment must be running to use this feature!"""

# ── outline planning prompt ──

PLAN_SYSTEM_PROMPT = """\
you are a"Future Forecast Report"writing expert,Have an understanding of the simulated world"God's perspective"——You can gain insight into every person in the simulationAgentbehavior,speech and interaction.

[core concept]
We built a simulated world,and injected specific"Simulation requirements"as a variable.The evolution of the simulated world,It is a prediction of what may happen in the future.What you are observing is not"experimental data",Rather"Preview of the future".

[your task]
write a"Future Forecast Report",answer:
1. under the conditions we set,what happened in the future?
2. All kindsAgent(crowd)how to react and act?
3. What this simulation reveals about future trends and risks worth watching?

[Report positioning]
- ✅ This is a simulation-based future forecast report,reveal"If so,what will happen in the future"
- ✅ Focus on predicting outcomes:Event trend,group reaction,emergent phenomenon,Potential risks
- ✅ in a simulated worldAgentWords and actions are predictions of future crowd behavior
- ❌ Not an analysis of real-world conditions
- ❌ This is not a general summary of public opinion.

[Chapter number limit]
- least2chapters,most5chapters
- No subsections required,Write the complete content directly for each chapter
- Content should be refined,Focus on core predictive discoveries
- The chapter structure is designed by you based on the prediction results

Please outputJSONFormat report outline,The format is as follows:
{
    "title": "Report title",
    "summary": "Report Summary(One sentence summarizing the core prediction findings)",
    "sections": [
        {
            "title": "Chapter title",
            "description": "Chapter content description"
        }
    ]
}

Notice:sections array: at least 2, at most 5 elements!"""

PLAN_USER_PROMPT_TEMPLATE = """\
[Predictive scenario setting]
Variables we inject into the simulated world(Simulation requirements):{simulation_requirement}

[simulate world scale]
- Number of entities participating in the simulation: {total_nodes}
- The number of relationships generated between entities: {total_edges}
- Entity type distribution: {entity_types}
- activeAgentquantity: {total_entities}

[Samples of some of the future facts predicted by the simulation]
{related_facts_json}

Please use"God's perspective"Check out this preview of the future:
1. under the conditions we set,What does the future look like??
2. All kinds of people(Agent)How to react and act?
3. What this simulation reveals about future trends worth watching?

Design the most appropriate report chapter structure based on the prediction results.

[reminder again]Report chapters: at least 2, at most 5,Content should be refined and focused on core predictions and findings."""

# ── Chapter generation prompt ──

SECTION_SYSTEM_PROMPT_TEMPLATE = """\
you are a"Future Forecast Report"writing expert,Writing a chapter of the report.

Report title: {report_title}
Report Summary: {report_summary}
Prediction scenarios(Simulation requirements): {simulation_requirement}

Chapter currently being written: {section_title}

═══════════════════════════════════════════════════════════════
[core concept]
═══════════════════════════════════════════════════════════════

The simulated world is a preview of the future.We inject specific conditions into the simulated world(Simulation requirements),
SimulatingAgentbehavior and interactions,It is the prediction of future crowd behavior..

your task is:
- revealed under set conditions,what happened in the future
- Predict various groups of people(Agent)How to react and act
- Discover future trends worth watching,risks and opportunities

❌ Don’t write it as an analysis of real-world conditions
✅ to focus on"what will happen in the future"——The simulation result is the predicted future

═══════════════════════════════════════════════════════════════
[The most important rule - Must comply with]
═══════════════════════════════════════════════════════════════

1. [Tools must be called to observe the simulated world]
   - you are using"God's perspective"Watch a preview of the future
   - All content must be derived from events occurring in the simulated world andAgentwords and deeds
   - Do not use your own knowledge to prepare report content
   - Each chapter calls at least3secondary tools(most5Second-rate)Come observe the simulated world,it represents the future

2. [Must quoteAgentoriginal words and deeds]
   - Agentspeech and behavior are predictions of future crowd behavior
   - Present these forecasts in reports using citation formats,For example:
     > "Some people will say:Original content..."
   - These citations are core evidence for simulation predictions

3. [Language consistency - Quotes must match the report language]
   - The content returned by the tool may contain mixed-language expressions
   - The report should be written in the same language as the simulation requirements and source materials
   - When quoting tool content in a different language, translate it naturally while preserving the original meaning
   - This rule applies to both inline text and quotation blocks (> format)

4. [Faithfully present prediction results]
   - Report content must reflect simulation results that represent the future in a simulated world
   - Do not add information that does not exist in the simulation
   - If there is insufficient information in some aspect,Explain truthfully

═══════════════════════════════════════════════════════════════
[⚠️ Format specifications - extremely important!]
═══════════════════════════════════════════════════════════════

[a chapter = Minimum content unit]
- Each chapter is the smallest unit of reporting
- ❌ It is prohibited to use any Markdown title(#,##,###,#### wait)
- ❌ It is forbidden to add the main chapter title at the beginning of the content
- ✅ Chapter titles are automatically added by the system,You only need to write pure text content
- ✅ use**Bold**,Paragraph separation,Quote,Lists to organize content,But don't use a title

[Correct example]
```
This chapter analyzes the public opinion communication trend of the incident.Through in-depth analysis of simulated data,we found...

**First detonation stage**

Weibo serves as the first site for public opinion,Undertakes the core function of information publishing:

> "Weibo contributed68%The initial volume of..."

**emotional amplification stage**

The Douyin platform further amplified the impact of the incident:

- Strong visual impact
- High emotional resonance
```

[Error example]
```
## executive summary          ← mistake!don't add any title
### one,initial stage     ← mistake!Don't use###divided into sections
#### 1.1 Detailed analysis   ← mistake!Don't use####Segmentation

This chapter analyzes...
```

═══════════════════════════════════════════════════════════════
[Available search tools](Called per chapter3-5Second-rate)
═══════════════════════════════════════════════════════════════

{tools_description}

[Tool usage suggestions - Please use a mix of tools,Don't just use one]
- insight_forge: Deep insight analysis,Automatically decompose problems and retrieve facts and relationships in multiple dimensions
- panorama_search: Wide angle panoramic search,Get the full story,Timeline and evolution
- quick_search: Quickly verify a specific information point
- interview_agents: Interview simulationAgent,Get first-person perspectives and real reactions from different characters

═══════════════════════════════════════════════════════════════
[Workflow]
═══════════════════════════════════════════════════════════════

You can only do one of two things for each reply:(cannot be done at the same time):

OptionsA - Call tool:
Output your thoughts,Then call a tool with the following format:
<tool_call>
{{"name": "Tool name", "parameters": {{"Parameter name": "Parameter value"}}}}
</tool_call>
The system will execute the tool and return the results to you.You don’t need and can’t write your own tools to return results.

OptionsB - Output final content:
When you have obtained enough information through the tool,by "Final Answer:" Output chapter content at the beginning.

⚠️ strictly prohibited:
- It is prohibited to include both tool calls and Final Answer
- Do not make up your own tools to return results(Observation),All tool results are injected by the system
- At most one tool can be called per reply

═══════════════════════════════════════════════════════════════
[Chapter content requirements]
═══════════════════════════════════════════════════════════════

1. Content must be based on simulated data retrieved by the tool
2. Extensive quotes from the original text to demonstrate simulation effects
3. useMarkdownFormat(But the use of titles is prohibited):
   - use **bold text** Mark the important points(instead of subtitle)
   - use list(-or1.2.3.)Organizational Points
   - Use blank lines to separate paragraphs
   - ❌ Prohibited use #,##,###,#### etc. any title syntax
4. [Citation format specifications - must be separated into segments]
   Quotations must be in separate paragraphs,There is a blank line before and after,cannot be mixed in paragraphs:

   ✅ Correct format:
   ```
   The school's response was seen as lacking substance..

   > "The school’s response model appears rigid and slow in the ever-changing social media environment."

   This assessment reflects widespread public dissatisfaction.
   ```

   ❌ Bad format:
   ```
   The school's response was seen as lacking substance..> "The school’s response model..." This evaluation reflects...
   ```
5. Maintain logical coherence with other chapters
6. [avoid duplication]Read carefully the completed chapters below,Do not describe the same information repeatedly
7. [Again]don't add any title!use**Bold**Replaces section title"""

SECTION_USER_PROMPT_TEMPLATE = """\
Completed chapter content(Please read carefully,avoid duplication):
{previous_content}

═══════════════════════════════════════════════════════════════
[current task]Write a chapter: {section_title}
═══════════════════════════════════════════════════════════════

[Important reminder]
1. Carefully read the completed chapters above,Avoid repeating the same content!
2. Before starting, you must first call the tool to obtain simulation data
3. Please use a mix of tools,Don't just use one
4. Report content must come from search results,Don't use your own knowledge

[⚠️ format warning - Must comply with]
- ❌ don't write any title(#,##,###,####Neither works)
- ❌ don't write"{section_title}"as a beginning
- ✅ Chapter titles are automatically added by the system
- ✅ Write the text directly,use**Bold**Replaces section title

please start:
1. think first(Thought)What information is needed for this chapter?
2. Then call the tool(Action)Get simulation data
3. Collect enough information and output Final Answer(Pure text,no title)"""

# ── ReACT In-loop message template ──

REACT_OBSERVATION_TEMPLATE = """\
Observation(Search results):

═══ tool {tool_name} return ═══
{result}

═══════════════════════════════════════════════════════════════
Tool called {tool_calls_count}/{max_tool_calls} Second-rate(Used: {used_tools_str}){unused_hint}
- If the information is sufficient:by "Final Answer:" Output chapter content at the beginning(The above original text must be cited)
- If you need more information:Call a tool to continue the search
═══════════════════════════════════════════════════════════════"""

REACT_INSUFFICIENT_TOOLS_MSG = (
    "[Notice]You just called{tool_calls_count}secondary tools,At least required{min_tool_calls}Second-rate."
    "Please call the tool again to obtain more simulation data,and then output Final Answer.{unused_hint}"
)

REACT_INSUFFICIENT_TOOLS_MSG_ALT = (
    "Currently only called {tool_calls_count} secondary tools,At least required {min_tool_calls} Second-rate."
    "Please call the tool to obtain simulation data.{unused_hint}"
)

REACT_TOOL_LIMIT_MSG = (
    "The number of tool calls has reached the upper limit({tool_calls_count}/{max_tool_calls}),Tools can no longer be called."
    'Please immediately based on the information you have obtained,by "Final Answer:" Output chapter content at the beginning.'
)

REACT_UNUSED_TOOLS_HINT = "\n💡 You haven't used it yet: {unused_list},It is recommended to try different tools to obtain multi-angle information"

REACT_FORCE_FINAL_MSG = "Tool call limit reached,Please output directly Final Answer: and generate chapter content."

# ── Chat prompt ──

CHAT_SYSTEM_PROMPT_TEMPLATE = """\
You are a concise and efficient simulation prediction assistant.

[background]
Prediction conditions: {simulation_requirement}

[Generated analysis report]
{report_content}

[rule]
1. Prioritize answering questions based on the above report content
2. answer questions directly,Avoid long thought-provoking discussions
3. Only if the report is insufficient to answer,before calling the tool to retrieve more data
4. Be concise in your answer,clear,Organized

[Available tools](Use only when needed,Most calls1-2Second-rate)
{tools_description}

[Tool call format]
<tool_call>
{{"name": "Tool name", "parameters": {{"Parameter name": "Parameter value"}}}}
</tool_call>

[answer style]
- Simple and direct,Don't make long remarks
- use > Format citation of key content
- Give priority to conclusions,Explain the reason again"""

CHAT_OBSERVATION_SUFFIX = "\n\nPlease answer the question concisely."


# ═══════════════════════════════════════════════════════════════
# ReportAgent main class
# ═══════════════════════════════════════════════════════════════


class ReportAgent:
    """
    Report Agent - Simulation report generationAgent

    useReACT(Reasoning + Acting)model:
    1. planning stage:Analyze simulation requirements,Planning the report directory structure
    2. generation phase:Generate content chapter by chapter,Each chapter can call the tool multiple times to obtain information
    3. reflection stage:Check content for completeness and accuracy
    """
    
    # Maximum number of tool calls(each chapter)
    MAX_TOOL_CALLS_PER_SECTION = 5
    
    # Maximum number of reflection rounds
    MAX_REFLECTION_ROUNDS = 3
    
    # Maximum number of tool calls in a conversation
    MAX_TOOL_CALLS_PER_CHAT = 2
    
    def __init__(
        self, 
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        llm_client: Optional[LLMClient] = None,
        zep_tools: Optional[ZepToolsService] = None
    ):
        """
        initializationReport Agent
        
        Args:
            graph_id: AtlasID
            simulation_id: simulation ID
            simulation_requirement: Simulation requirement description
            llm_client: LLM client(Optional)
            zep_tools: ZepTool services(Optional)
        """
        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self.simulation_requirement = simulation_requirement
        
        self.llm = llm_client or LLMClient()
        self.zep_tools = zep_tools or ZepToolsService()
        
        # Tool definition
        self.tools = self._define_tools()
        
        # Logger(exist generate_report Medium initialization)
        self.report_logger: Optional[ReportLogger] = None
        # console logger(exist generate_report Medium initialization)
        self.console_logger: Optional[ReportConsoleLogger] = None
        
        logger.info(f"ReportAgent Initialization completed: graph_id={graph_id}, simulation_id={simulation_id}")
    
    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """Define available tools"""
        return {
            "insight_forge": {
                "name": "insight_forge",
                "description": TOOL_DESC_INSIGHT_FORGE,
                "parameters": {
                    "query": "A question or topic you would like to analyze in depth",
                    "report_context": "The context of the current report chapter(Optional,Helps generate more precise sub-problems)"
                }
            },
            "panorama_search": {
                "name": "panorama_search",
                "description": TOOL_DESC_PANORAMA_SEARCH,
                "parameters": {
                    "query": "search query,for relevance ranking",
                    "include_expired": "Whether to include expiration/historical content(defaultTrue)"
                }
            },
            "quick_search": {
                "name": "quick_search",
                "description": TOOL_DESC_QUICK_SEARCH,
                "parameters": {
                    "query": "Search query string",
                    "limit": "Number of results returned(Optional,default10)"
                }
            },
            "interview_agents": {
                "name": "interview_agents",
                "description": TOOL_DESC_INTERVIEW_AGENTS,
                "parameters": {
                    "interview_topic": "Interview topic or need description(like:'Understand students’ views on the formaldehyde incident in dormitories')",
                    "max_agents": "Most interviewedAgentquantity(Optional,default5,maximum10)"
                }
            }
        }
    
    def _execute_tool(self, tool_name: str, parameters: Dict[str, Any], report_context: str = "") -> str:
        """
        Execute tool call
        
        Args:
            tool_name: Tool name
            parameters: Tool parameters
            report_context: Report context(used forInsightForge)
            
        Returns:
            Tool execution results(text format)
        """
        logger.info(f"Execution tool: {tool_name}, parameter: {parameters}")
        
        try:
            if tool_name == "insight_forge":
                query = parameters.get("query", "")
                ctx = parameters.get("report_context", "") or report_context
                result = self.zep_tools.insight_forge(
                    graph_id=self.graph_id,
                    query=query,
                    simulation_requirement=self.simulation_requirement,
                    report_context=ctx
                )
                return result.to_text()
            
            elif tool_name == "panorama_search":
                # breadth search - Get the full picture
                query = parameters.get("query", "")
                include_expired = parameters.get("include_expired", True)
                if isinstance(include_expired, str):
                    include_expired = include_expired.lower() in ['true', '1', 'yes']
                result = self.zep_tools.panorama_search(
                    graph_id=self.graph_id,
                    query=query,
                    include_expired=include_expired
                )
                return result.to_text()
            
            elif tool_name == "quick_search":
                # Simple search - Quick search
                query = parameters.get("query", "")
                limit = parameters.get("limit", 10)
                if isinstance(limit, str):
                    limit = int(limit)
                result = self.zep_tools.quick_search(
                    graph_id=self.graph_id,
                    query=query,
                    limit=limit
                )
                return result.to_text()
            
            elif tool_name == "interview_agents":
                # in-depth interview - call realOASISinterviewAPIGet simulationAgentanswer(Dual-platform)
                interview_topic = parameters.get("interview_topic", parameters.get("query", ""))
                max_agents = parameters.get("max_agents", 5)
                if isinstance(max_agents, str):
                    max_agents = int(max_agents)
                max_agents = min(max_agents, 10)
                result = self.zep_tools.interview_agents(
                    simulation_id=self.simulation_id,
                    interview_requirement=interview_topic,
                    simulation_requirement=self.simulation_requirement,
                    max_agents=max_agents
                )
                return result.to_text()
            
            # ========== Backward compatibility with legacy tools(Internal redirect to new tool) ==========
            
            elif tool_name == "search_graph":
                # redirect to quick_search
                logger.info("search_graph Redirected to quick_search")
                return self._execute_tool("quick_search", parameters, report_context)
            
            elif tool_name == "get_graph_statistics":
                result = self.zep_tools.get_graph_statistics(self.graph_id)
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            elif tool_name == "get_entity_summary":
                entity_name = parameters.get("entity_name", "")
                result = self.zep_tools.get_entity_summary(
                    graph_id=self.graph_id,
                    entity_name=entity_name
                )
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            elif tool_name == "get_simulation_context":
                # redirect to insight_forge,because it is more powerful
                logger.info("get_simulation_context Redirected to insight_forge")
                query = parameters.get("query", self.simulation_requirement)
                return self._execute_tool("insight_forge", {"query": query}, report_context)
            
            elif tool_name == "get_entities_by_type":
                entity_type = parameters.get("entity_type", "")
                nodes = self.zep_tools.get_entities_by_type(
                    graph_id=self.graph_id,
                    entity_type=entity_type
                )
                result = [n.to_dict() for n in nodes]
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            else:
                return f"unknown tool: {tool_name}.Please use one of the following tools: insight_forge, panorama_search, quick_search"
                
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}, mistake: {str(e)}")
            return f"Tool execution failed: {str(e)}"
    
    # Set of legal tool names,for bare JSON Verification during parsing
    VALID_TOOL_NAMES = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
        fromLLMParsing tool calls in response

        Supported formats(by priority):
        1. <tool_call>{"name": "tool_name", "parameters": {...}}</tool_call>
        2. bare JSON(The response as a whole or a single line is a tool call JSON)
        """
        tool_calls = []

        # Format1: XMLstyle(standard format)
        xml_pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
        for match in re.finditer(xml_pattern, response, re.DOTALL):
            try:
                call_data = json.loads(match.group(1))
                tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        if tool_calls:
            return tool_calls

        # Format2: reveal all the details - LLM Directly output bare JSON(No bag <tool_call> Label)
        # only in format1Try if no match,Avoid mismatching in the text JSON
        stripped = response.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            try:
                call_data = json.loads(stripped)
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
                    return tool_calls
            except json.JSONDecodeError:
                pass

        # Response may contain think text + bare JSON,Try to extract the last JSON object
        json_pattern = r'(\{"(?:name|tool)"\s*:.*?\})\s*$'
        match = re.search(json_pattern, stripped, re.DOTALL)
        if match:
            try:
                call_data = json.loads(match.group(1))
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        return tool_calls

    def _is_valid_tool_call(self, data: dict) -> bool:
        """parsed by verification JSON Is it a legal tool call?"""
        # support {"name": ..., "parameters": ...} and {"tool": ..., "params": ...} Two key names
        tool_name = data.get("name") or data.get("tool")
        if tool_name and tool_name in self.VALID_TOOL_NAMES:
            # Unified key name name / parameters
            if "tool" in data:
                data["name"] = data.pop("tool")
            if "params" in data and "parameters" not in data:
                data["parameters"] = data.pop("params")
            return True
        return False
    
    def _get_tools_description(self) -> str:
        """Generate tool description text"""
        desc_parts = ["Available tools:"]
        for name, tool in self.tools.items():
            params_desc = ", ".join([f"{k}: {v}" for k, v in tool["parameters"].items()])
            desc_parts.append(f"- {name}: {tool['description']}")
            if params_desc:
                desc_parts.append(f"  parameter: {params_desc}")
        return "\n".join(desc_parts)
    
    def plan_outline(
        self, 
        progress_callback: Optional[Callable] = None
    ) -> ReportOutline:
        """
        Planning report outline
        
        useLLMAnalyze simulation requirements,Planning the directory structure of reports
        
        Args:
            progress_callback: Progress callback function
            
        Returns:
            ReportOutline: Report outline
        """
        logger.info("Start planning your report outline...")
        
        if progress_callback:
            progress_callback("planning", 0, "Analyzing simulation requirements...")
        
        # First get the simulation context
        context = self.zep_tools.get_simulation_context(
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement
        )
        
        if progress_callback:
            progress_callback("planning", 30, "Generating report outline...")
        
        system_prompt = PLAN_SYSTEM_PROMPT
        user_prompt = PLAN_USER_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            total_nodes=context.get('graph_statistics', {}).get('total_nodes', 0),
            total_edges=context.get('graph_statistics', {}).get('total_edges', 0),
            entity_types=list(context.get('graph_statistics', {}).get('entity_types', {}).keys()),
            total_entities=context.get('total_entities', 0),
            related_facts_json=json.dumps(context.get('related_facts', [])[:10], ensure_ascii=False, indent=2),
        )

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            if progress_callback:
                progress_callback("planning", 80, "Parsing outline structure...")
            
            # Analyze the outline
            sections = []
            for section_data in response.get("sections", []):
                sections.append(ReportSection(
                    title=section_data.get("title", ""),
                    content=""
                ))
            
            outline = ReportOutline(
                title=response.get("title", "Simulation analysis report"),
                summary=response.get("summary", ""),
                sections=sections
            )
            
            if progress_callback:
                progress_callback("planning", 100, "Outline planning completed")
            
            logger.info(f"Outline planning completed: {len(sections)} chapters")
            return outline
            
        except Exception as e:
            logger.error(f"Outline planning failed: {str(e)}")
            # Return to default outline(3chapters,asfallback)
            return ReportOutline(
                title="Future Forecast Report",
                summary="Future trend and risk analysis based on simulation forecasts",
                sections=[
                    ReportSection(title="Predictive scenarios and core findings"),
                    ReportSection(title="Predictive analysis of crowd behavior"),
                    ReportSection(title="Trend Outlook and Risk Warning")
                ]
            )
    
    def _generate_section_react(
        self, 
        section: ReportSection,
        outline: ReportOutline,
        previous_sections: List[str],
        progress_callback: Optional[Callable] = None,
        section_index: int = 0
    ) -> str:
        """
        useReACTPattern to generate single chapter content
        
        ReACTcycle:
        1. Thought(think)- What information is needed for analysis
        2. Action(action)- Call tools to get information
        3. Observation(observe)- Analysis tools return results
        4. Repeat until information is sufficient or maximum times reached
        5. Final Answer(final answer)- Generate chapter content
        
        Args:
            section: Chapters to generate
            outline: full outline
            previous_sections: Contents of previous chapters(used to maintain continuity)
            progress_callback: Progress callback
            section_index: Chapter index(for logging)
            
        Returns:
            Chapter content(MarkdownFormat)
        """
        logger.info(f"ReACTGenerate chapters: {section.title}")
        
        # Record chapter start log
        if self.report_logger:
            self.report_logger.log_section_start(section.title, section_index)
        
        system_prompt = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
            report_title=outline.title,
            report_summary=outline.summary,
            simulation_requirement=self.simulation_requirement,
            section_title=section.title,
            tools_description=self._get_tools_description(),
        )

        # Build userprompt - Each completed chapter passes the maximum4000Character
        if previous_sections:
            previous_parts = []
            for sec in previous_sections:
                # Maximum per chapter4000Character
                truncated = sec[:4000] + "..." if len(sec) > 4000 else sec
                previous_parts.append(truncated)
            previous_content = "\n\n---\n\n".join(previous_parts)
        else:
            previous_content = "(This is the first chapter)"
        
        user_prompt = SECTION_USER_PROMPT_TEMPLATE.format(
            previous_content=previous_content,
            section_title=section.title,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # ReACTcycle
        tool_calls_count = 0
        max_iterations = 5  # Maximum number of iteration rounds
        min_tool_calls = 3  # Minimum number of tool calls
        conflict_retries = 0  # Tool calls andFinal AnswerThe number of consecutive conflicts that occur at the same time
        used_tools = set()  # Record the tool name that has been called
        all_tools = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

        # Report context,used forInsightForgeSub-problem generation of
        report_context = f"Chapter title: {section.title}\nSimulation requirements: {self.simulation_requirement}"
        
        for iteration in range(max_iterations):
            if progress_callback:
                progress_callback(
                    "generating", 
                    int((iteration / max_iterations) * 100),
                    f"In-depth search and writing ({tool_calls_count}/{self.MAX_TOOL_CALLS_PER_SECTION})"
                )
            
            # callLLM
            response = self.llm.chat(
                messages=messages,
                temperature=0.5,
                max_tokens=4096
            )

            # examine LLM Returns whether None(API Exception or empty content)
            if response is None:
                logger.warning(f"chapter {section.title} No. {iteration + 1} iterations: LLM return None")
                # If there are still iterations,Add message and try again
                if iteration < max_iterations - 1:
                    messages.append({"role": "assistant", "content": "(response is empty)"})
                    messages.append({"role": "user", "content": "Please continue to generate content."})
                    continue
                # The last iteration also returns None,Break out of the loop and enter the forced ending
                break

            logger.debug(f"LLMresponse: {response[:200]}...")

            # parse once,Reuse results
            tool_calls = self._parse_tool_calls(response)
            has_tool_calls = bool(tool_calls)
            has_final_answer = "Final Answer:" in response

            # ── Conflict handling:LLM Also output tool calls and Final Answer ──
            if has_tool_calls and has_final_answer:
                conflict_retries += 1
                logger.warning(
                    f"chapter {section.title} No. {iteration+1} wheel: "
                    f"LLM Also output tool calls and Final Answer(No. {conflict_retries} conflict)"
                )

                if conflict_retries <= 2:
                    # first two times:Discard this response,Require LLM Reply again
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": (
                            "[Format error]You included both tool calls and Final Answer,this is not allowed.\n"
                            "Each reply can only do one of the following two things::\n"
                            "- call a tool(Output a <tool_call> piece,don't write Final Answer)\n"
                            "- Output final content(by 'Final Answer:' beginning,don't include <tool_call>)\n"
                            "Please reply again,do only one of these things."
                        ),
                    })
                    continue
                else:
                    # third time:Downgrade processing,Truncate to first tool call,enforce
                    logger.warning(
                        f"chapter {section.title}: continuous {conflict_retries} conflict,"
                        "Downgrade to truncate execution of first tool call"
                    )
                    first_tool_end = response.find('</tool_call>')
                    if first_tool_end != -1:
                        response = response[:first_tool_end + len('</tool_call>')]
                        tool_calls = self._parse_tool_calls(response)
                        has_tool_calls = bool(tool_calls)
                    has_final_answer = False
                    conflict_retries = 0

            # Record LLM Response log
            if self.report_logger:
                self.report_logger.log_llm_response(
                    section_title=section.title,
                    section_index=section_index,
                    response=response,
                    iteration=iteration + 1,
                    has_tool_calls=has_tool_calls,
                    has_final_answer=has_final_answer
                )

            # ── Condition1:LLM Output Final Answer ──
            if has_final_answer:
                # Not enough tool calls,Refuse and ask to continue adjusting tools
                if tool_calls_count < min_tool_calls:
                    messages.append({"role": "assistant", "content": response})
                    unused_tools = all_tools - used_tools
                    unused_hint = f"(These tools are not yet used,Recommend using them: {', '.join(unused_tools)})" if unused_tools else ""
                    messages.append({
                        "role": "user",
                        "content": REACT_INSUFFICIENT_TOOLS_MSG.format(
                            tool_calls_count=tool_calls_count,
                            min_tool_calls=min_tool_calls,
                            unused_hint=unused_hint,
                        ),
                    })
                    continue

                # End normally
                final_answer = response.split("Final Answer:")[-1].strip()
                logger.info(f"chapter {section.title} Generation completed(Tool call: {tool_calls_count}Second-rate)")

                if self.report_logger:
                    self.report_logger.log_section_content(
                        section_title=section.title,
                        section_index=section_index,
                        content=final_answer,
                        tool_calls_count=tool_calls_count
                    )
                return final_answer

            # ── Condition2:LLM Try calling the tool ──
            if has_tool_calls:
                # Tool quota has been exhausted → clearly informed,Request output Final Answer
                if tool_calls_count >= self.MAX_TOOL_CALLS_PER_SECTION:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": REACT_TOOL_LIMIT_MSG.format(
                            tool_calls_count=tool_calls_count,
                            max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        ),
                    })
                    continue

                # Only execute the first tool call
                call = tool_calls[0]
                if len(tool_calls) > 1:
                    logger.info(f"LLM Try calling {len(tool_calls)} tools,Only execute the first one: {call['name']}")

                if self.report_logger:
                    self.report_logger.log_tool_call(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        parameters=call.get("parameters", {}),
                        iteration=iteration + 1
                    )

                result = self._execute_tool(
                    call["name"],
                    call.get("parameters", {}),
                    report_context=report_context
                )

                if self.report_logger:
                    self.report_logger.log_tool_result(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        result=result,
                        iteration=iteration + 1
                    )

                tool_calls_count += 1
                used_tools.add(call['name'])

                # Build unused tooltip
                unused_tools = all_tools - used_tools
                unused_hint = ""
                if unused_tools and tool_calls_count < self.MAX_TOOL_CALLS_PER_SECTION:
                    unused_hint = REACT_UNUSED_TOOLS_HINT.format(unused_list=",".join(unused_tools))

                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": REACT_OBSERVATION_TEMPLATE.format(
                        tool_name=call["name"],
                        result=result,
                        tool_calls_count=tool_calls_count,
                        max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        used_tools_str=", ".join(used_tools),
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # ── Condition3:Neither tool call,Neither Final Answer ──
            messages.append({"role": "assistant", "content": response})

            if tool_calls_count < min_tool_calls:
                # Not enough tool calls,Recommend unused tools
                unused_tools = all_tools - used_tools
                unused_hint = f"(These tools are not yet used,Recommend using them: {', '.join(unused_tools)})" if unused_tools else ""

                messages.append({
                    "role": "user",
                    "content": REACT_INSUFFICIENT_TOOLS_MSG_ALT.format(
                        tool_calls_count=tool_calls_count,
                        min_tool_calls=min_tool_calls,
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # Tool calls are sufficient,LLM The content was output but not included "Final Answer:" prefix
            # Just use this paragraph as the final answer,No more idling
            logger.info(f"chapter {section.title} not detected 'Final Answer:' prefix,directly adoptedLLMOutput as final content(Tool call: {tool_calls_count}Second-rate)")
            final_answer = response.strip()

            if self.report_logger:
                self.report_logger.log_section_content(
                    section_title=section.title,
                    section_index=section_index,
                    content=final_answer,
                    tool_calls_count=tool_calls_count
                )
            return final_answer
        
        # Maximum number of iterations reached,Force generated content
        logger.warning(f"chapter {section.title} Maximum number of iterations reached,Force generation")
        messages.append({"role": "user", "content": REACT_FORCE_FINAL_MSG})
        
        response = self.llm.chat(
            messages=messages,
            temperature=0.5,
            max_tokens=4096
        )

        # When checking for forced closing LLM Returns whether None
        if response is None:
            logger.error(f"chapter {section.title} When forced to close LLM return None,Use default error message")
            final_answer = f"(Generation of this chapter failed:LLM Return empty response,Please try again later)"
        elif "Final Answer:" in response:
            final_answer = response.split("Final Answer:")[-1].strip()
        else:
            final_answer = response
        
        # Record chapter content and generate completion log
        if self.report_logger:
            self.report_logger.log_section_content(
                section_title=section.title,
                section_index=section_index,
                content=final_answer,
                tool_calls_count=tool_calls_count
            )
        
        return final_answer
    
    def generate_report(
        self, 
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        report_id: Optional[str] = None
    ) -> Report:
        """
        Generate full report(Chapter-by-chapter real-time output)
        
        Each chapter is Saved to a folder immediately after it is generated.,No need to wait for the entire report to complete.
        File structure:
        reports/{report_id}/
            meta.json       - Report meta information
            outline.json    - Report outline
            progress.json   - Build progress
            section_01.md   - No.1chapter
            section_02.md   - No.2chapter
            ...
            full_report.md  - full report
        
        Args:
            progress_callback: Progress callback function (stage, progress, message)
            report_id: ReportID(Optional,If not passed, it will be automatically generated.)
            
        Returns:
            Report: full report
        """
        import uuid
        
        # If not passed in report_id,is automatically generated
        if not report_id:
            report_id = f"report_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now()
        
        report = Report(
            report_id=report_id,
            simulation_id=self.simulation_id,
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement,
            status=ReportStatus.PENDING,
            created_at=datetime.now().isoformat()
        )
        
        # List of completed chapter titles(for progress tracking)
        completed_section_titles = []
        
        try:
            # initialization:Create report folder and save initial state
            ReportManager._ensure_report_folder(report_id)
            
            # Initialize the logger(Structured log agent_log.jsonl)
            self.report_logger = ReportLogger(report_id)
            self.report_logger.log_start(
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement
            )
            
            # Initialize the console logger(console_log.txt)
            self.console_logger = ReportConsoleLogger(report_id)
            
            ReportManager.update_progress(
                report_id, "pending", 0, "Initialization report...",
                completed_sections=[]
            )
            ReportManager.save_report(report)
            
            # stage1: Planning outline
            report.status = ReportStatus.PLANNING
            ReportManager.update_progress(
                report_id, "planning", 5, "Start planning your report outline...",
                completed_sections=[]
            )
            
            # Record planning start log
            self.report_logger.log_planning_start()
            
            if progress_callback:
                progress_callback("planning", 0, "Start planning your report outline...")
            
            outline = self.plan_outline(
                progress_callback=lambda stage, prog, msg: 
                    progress_callback(stage, prog // 5, msg) if progress_callback else None
            )
            report.outline = outline
            
            # Record planning completion log
            self.report_logger.log_planning_complete(outline.to_dict())
            
            # Save outline to file
            ReportManager.save_outline(report_id, outline)
            ReportManager.update_progress(
                report_id, "planning", 15, f"Outline planning completed,common{len(outline.sections)}chapters",
                completed_sections=[]
            )
            ReportManager.save_report(report)
            
            logger.info(f"Outline Saved to file: {report_id}/outline.json")
            
            # stage2: Generate chapter by chapter(Save in chapters)
            report.status = ReportStatus.GENERATING
            
            total_sections = len(outline.sections)
            generated_sections = []  # Save content for context
            
            for i, section in enumerate(outline.sections):
                section_num = i + 1
                base_progress = 20 + int((i / total_sections) * 70)
                
                # update progress
                ReportManager.update_progress(
                    report_id, "generating", base_progress,
                    f"Generating chapters: {section.title} ({section_num}/{total_sections})",
                    current_section=section.title,
                    completed_sections=completed_section_titles
                )
                
                if progress_callback:
                    progress_callback(
                        "generating", 
                        base_progress, 
                        f"Generating chapters: {section.title} ({section_num}/{total_sections})"
                    )
                
                # Generate main chapter content
                section_content = self._generate_section_react(
                    section=section,
                    outline=outline,
                    previous_sections=generated_sections,
                    progress_callback=lambda stage, prog, msg:
                        progress_callback(
                            stage, 
                            base_progress + int(prog * 0.7 / total_sections),
                            msg
                        ) if progress_callback else None,
                    section_index=section_num
                )
                
                section.content = section_content
                generated_sections.append(f"## {section.title}\n\n{section_content}")

                # save chapter
                ReportManager.save_section(report_id, section_num, section)
                completed_section_titles.append(section.title)

                # Record chapter completion log
                full_section_content = f"## {section.title}\n\n{section_content}"

                if self.report_logger:
                    self.report_logger.log_section_full_complete(
                        section_title=section.title,
                        section_index=section_num,
                        full_content=full_section_content.strip()
                    )

                logger.info(f"Chapter Saved: {report_id}/section_{section_num:02d}.md")
                
                # update progress
                ReportManager.update_progress(
                    report_id, "generating", 
                    base_progress + int(70 / total_sections),
                    f"chapter {section.title} Completed",
                    current_section=None,
                    completed_sections=completed_section_titles
                )
            
            # stage3: Assemble the complete report
            if progress_callback:
                progress_callback("generating", 95, "Assembling full report...")
            
            ReportManager.update_progress(
                report_id, "generating", 95, "Assembling full report...",
                completed_sections=completed_section_titles
            )
            
            # useReportManagerAssemble the complete report
            report.markdown_content = ReportManager.assemble_full_report(report_id, outline)
            report.status = ReportStatus.COMPLETED
            report.completed_at = datetime.now().isoformat()
            
            # Calculate total time
            total_time_seconds = (datetime.now() - start_time).total_seconds()
            
            # Record report completion log
            if self.report_logger:
                self.report_logger.log_report_complete(
                    total_sections=total_sections,
                    total_time_seconds=total_time_seconds
                )
            
            # Save final report
            ReportManager.save_report(report)
            ReportManager.update_progress(
                report_id, "completed", 100, "Report generation completed",
                completed_sections=completed_section_titles
            )
            
            if progress_callback:
                progress_callback("completed", 100, "Report generation completed")
            
            logger.info(f"Report generation completed: {report_id}")
            
            # Turn off the console logger
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None
            
            return report
            
        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}")
            report.status = ReportStatus.FAILED
            report.error = str(e)
            
            # Record error log
            if self.report_logger:
                self.report_logger.log_error(str(e), "failed")
            
            # Save failed status
            try:
                ReportManager.save_report(report)
                ReportManager.update_progress(
                    report_id, "failed", -1, f"Report generation failed: {str(e)}",
                    completed_sections=completed_section_titles
                )
            except Exception:
                pass  # Ignore save failed errors
            
            # Turn off the console logger
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None
            
            return report
    
    def chat(
        self, 
        message: str,
        chat_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        andReport Agentdialogue
        
        in conversationAgentYou can call search tools independently to answer questions
        
        Args:
            message: User messages
            chat_history: Conversation history
            
        Returns:
            {
                "response": "Agentreply",
                "tool_calls": [List of tools called],
                "sources": [Source of information]
            }
        """
        logger.info(f"Report Agentdialogue: {message[:50]}...")
        
        chat_history = chat_history or []
        
        # Get generated report content
        report_content = ""
        try:
            report = ReportManager.get_report_by_simulation(self.simulation_id)
            if report and report.markdown_content:
                # Limit report length,Avoid long context
                report_content = report.markdown_content[:15000]
                if len(report.markdown_content) > 15000:
                    report_content += "\n\n... [Report content has been truncated] ..."
        except Exception as e:
            logger.warning(f"Failed to get report content: {e}")
        
        system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            report_content=report_content if report_content else "(No report yet)",
            tools_description=self._get_tools_description(),
        )

        # Build message
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add historical conversation
        for h in chat_history[-10:]:  # Limit history length
            messages.append(h)
        
        # Add user message
        messages.append({
            "role": "user", 
            "content": message
        })
        
        # ReACTcycle(Simplified version)
        tool_calls_made = []
        max_iterations = 2  # Reduce the number of iteration rounds
        
        for iteration in range(max_iterations):
            response = self.llm.chat(
                messages=messages,
                temperature=0.5
            )
            
            # Parsing tool call
            tool_calls = self._parse_tool_calls(response)
            
            if not tool_calls:
                # No tool calls,Return response directly
                clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', response, flags=re.DOTALL)
                clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
                
                return {
                    "response": clean_response.strip(),
                    "tool_calls": tool_calls_made,
                    "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
                }
            
            # Execute tool call(limited quantity)
            tool_results = []
            for call in tool_calls[:1]:  # Maximum execution per round1tool calls
                if len(tool_calls_made) >= self.MAX_TOOL_CALLS_PER_CHAT:
                    break
                result = self._execute_tool(call["name"], call.get("parameters", {}))
                tool_results.append({
                    "tool": call["name"],
                    "result": result[:1500]  # Limit result length
                })
                tool_calls_made.append(call)
            
            # Add results to message
            messages.append({"role": "assistant", "content": response})
            observation = "\n".join([f"[{r['tool']}result]\n{r['result']}" for r in tool_results])
            messages.append({
                "role": "user",
                "content": observation + CHAT_OBSERVATION_SUFFIX
            })
        
        # Reach maximum iteration,Get final response
        final_response = self.llm.chat(
            messages=messages,
            temperature=0.5
        )
        
        # Clean response
        clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', final_response, flags=re.DOTALL)
        clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
        
        return {
            "response": clean_response.strip(),
            "tool_calls": tool_calls_made,
            "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
        }


class ReportManager:
    """
    Report Manager
    
    Responsible for persistent storage and retrieval of reports
    
    File structure(Output in chapters):
    reports/
      {report_id}/
        meta.json          - Report meta information and status
        outline.json       - Report outline
        progress.json      - Build progress
        section_01.md      - No.1chapter
        section_02.md      - No.2chapter
        ...
        full_report.md     - full report
    """
    
    # Report storage directory
    REPORTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'reports')
    
    @classmethod
    def _ensure_reports_dir(cls):
        """Make sure the report root directory exists"""
        os.makedirs(cls.REPORTS_DIR, exist_ok=True)
    
    @classmethod
    def _get_report_folder(cls, report_id: str) -> str:
        """Get report folder path"""
        return os.path.join(cls.REPORTS_DIR, report_id)
    
    @classmethod
    def _ensure_report_folder(cls, report_id: str) -> str:
        """Make sure the reports folder exists and return the path"""
        folder = cls._get_report_folder(report_id)
        os.makedirs(folder, exist_ok=True)
        return folder
    
    @classmethod
    def _get_report_path(cls, report_id: str) -> str:
        """Get report metainformation file path"""
        return os.path.join(cls._get_report_folder(report_id), "meta.json")
    
    @classmethod
    def _get_report_markdown_path(cls, report_id: str) -> str:
        """Get the full reportMarkdownfile path"""
        return os.path.join(cls._get_report_folder(report_id), "full_report.md")
    
    @classmethod
    def _get_outline_path(cls, report_id: str) -> str:
        """Get outline file path"""
        return os.path.join(cls._get_report_folder(report_id), "outline.json")
    
    @classmethod
    def _get_progress_path(cls, report_id: str) -> str:
        """Get progress file path"""
        return os.path.join(cls._get_report_folder(report_id), "progress.json")
    
    @classmethod
    def _get_section_path(cls, report_id: str, section_index: int) -> str:
        """Get chaptersMarkdownfile path"""
        return os.path.join(cls._get_report_folder(report_id), f"section_{section_index:02d}.md")
    
    @classmethod
    def _get_agent_log_path(cls, report_id: str) -> str:
        """get Agent Log file path"""
        return os.path.join(cls._get_report_folder(report_id), "agent_log.jsonl")
    
    @classmethod
    def _get_console_log_path(cls, report_id: str) -> str:
        """Get console log file path"""
        return os.path.join(cls._get_report_folder(report_id), "console_log.txt")
    
    @classmethod
    def get_console_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        Get console log content
        
        This is the console output log during report generation(INFO,WARNINGwait),
        and agent_log.jsonl Different structured logs.
        
        Args:
            report_id: ReportID
            from_line: Which line should I start reading from?(for incremental acquisition,0 means starting from the beginning)
            
        Returns:
            {
                "logs": [List of log lines],
                "total_lines": Total number of rows,
                "from_line": Starting line number,
                "has_more": Are there more logs?
            }
        """
        log_path = cls._get_console_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    # Keep original log lines,Remove trailing newline character
                    logs.append(line.rstrip('\n\r'))
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # Read to the end
        }
    
    @classmethod
    def get_console_log_stream(cls, report_id: str) -> List[str]:
        """
        Get full console log(Get them all at once)
        
        Args:
            report_id: ReportID
            
        Returns:
            List of log lines
        """
        result = cls.get_console_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def get_agent_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        get Agent Log content
        
        Args:
            report_id: ReportID
            from_line: Which line should I start reading from?(for incremental acquisition,0 means starting from the beginning)
            
        Returns:
            {
                "logs": [List of log entries],
                "total_lines": Total number of rows,
                "from_line": Starting line number,
                "has_more": Are there more logs?
            }
        """
        log_path = cls._get_agent_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    try:
                        log_entry = json.loads(line.strip())
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        # Skip lines that failed to parse
                        continue
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # Read to the end
        }
    
    @classmethod
    def get_agent_log_stream(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        get complete Agent log(Used to get all at once)
        
        Args:
            report_id: ReportID
            
        Returns:
            List of log entries
        """
        result = cls.get_agent_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def save_outline(cls, report_id: str, outline: ReportOutline) -> None:
        """
        Save report outline
        
        Called immediately after the planning phase is complete
        """
        cls._ensure_report_folder(report_id)
        
        with open(cls._get_outline_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(outline.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"Outline Saved: {report_id}")
    
    @classmethod
    def save_section(
        cls,
        report_id: str,
        section_index: int,
        section: ReportSection
    ) -> str:
        """
        Save a single chapter

        Called immediately after each chapter is generated,Realize chapter-by-chapter output

        Args:
            report_id: ReportID
            section_index: Chapter index(from1start)
            section: Chapter object

        Returns:
            Saved file path
        """
        cls._ensure_report_folder(report_id)

        # Build a chapterMarkdowncontent - Clean up possible duplicate titles
        cleaned_content = cls._clean_section_content(section.content, section.title)
        md_content = f"## {section.title}\n\n"
        if cleaned_content:
            md_content += f"{cleaned_content}\n\n"

        # save file
        file_suffix = f"section_{section_index:02d}.md"
        file_path = os.path.join(cls._get_report_folder(report_id), file_suffix)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        logger.info(f"Chapter Saved: {report_id}/{file_suffix}")
        return file_path
    
    @classmethod
    def _clean_section_content(cls, content: str, section_title: str) -> str:
        """
        Clean up chapter content
        
        1. Remove content that duplicates the chapter title at the beginningMarkdowntitle line
        2. will all ### Titles at and below levels are converted to bold text
        
        Args:
            content: original content
            section_title: Chapter title
            
        Returns:
            Cleaned content
        """
        import re
        
        if not content:
            return content
        
        content = content.strip()
        lines = content.split('\n')
        cleaned_lines = []
        skip_next_empty = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Check if it isMarkdowntitle line
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title_text = heading_match.group(2).strip()
                
                # Check if the title is a duplicate of the chapter title(Skip before5Inline repetition)
                if i < 5:
                    if title_text == section_title or title_text.replace(' ', '') == section_title.replace(' ', ''):
                        skip_next_empty = True
                        continue
                
                # Convert all level headings(#, ##, ###, ####wait)Convert to bold
                # Because the chapter title is added by the system,Content should not have any titles
                cleaned_lines.append(f"**{title_text}**")
                cleaned_lines.append("")  # add blank line
                continue
            
            # If the previous line is a skipped header,and the current row is empty,also skip
            if skip_next_empty and stripped == '':
                skip_next_empty = False
                continue
            
            skip_next_empty = False
            cleaned_lines.append(line)
        
        # Remove leading blank lines
        while cleaned_lines and cleaned_lines[0].strip() == '':
            cleaned_lines.pop(0)
        
        # Remove leading separator
        while cleaned_lines and cleaned_lines[0].strip() in ['---', '***', '___']:
            cleaned_lines.pop(0)
            # Also remove empty lines after separators
            while cleaned_lines and cleaned_lines[0].strip() == '':
                cleaned_lines.pop(0)
        
        return '\n'.join(cleaned_lines)
    
    @classmethod
    def update_progress(
        cls, 
        report_id: str, 
        status: str, 
        progress: int, 
        message: str,
        current_section: str = None,
        completed_sections: List[str] = None
    ) -> None:
        """
        Update report generation progress
        
        The front end can read viaprogress.jsonGet real-time progress
        """
        cls._ensure_report_folder(report_id)
        
        progress_data = {
            "status": status,
            "progress": progress,
            "message": message,
            "current_section": current_section,
            "completed_sections": completed_sections or [],
            "updated_at": datetime.now().isoformat()
        }
        
        with open(cls._get_progress_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def get_progress(cls, report_id: str) -> Optional[Dict[str, Any]]:
        """Get report generation progress"""
        path = cls._get_progress_path(report_id)
        
        if not os.path.exists(path):
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @classmethod
    def get_generated_sections(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        Get the generated chapter list
        
        Returns all Saved chapter file information
        """
        folder = cls._get_report_folder(report_id)
        
        if not os.path.exists(folder):
            return []
        
        sections = []
        for filename in sorted(os.listdir(folder)):
            if filename.startswith('section_') and filename.endswith('.md'):
                file_path = os.path.join(folder, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Parse chapter index from filename
                parts = filename.replace('.md', '').split('_')
                section_index = int(parts[1])

                sections.append({
                    "filename": filename,
                    "section_index": section_index,
                    "content": content
                })

        return sections
    
    @classmethod
    def assemble_full_report(cls, report_id: str, outline: ReportOutline) -> str:
        """
        Assemble the complete report
        
        Assemble full report from Saved chapter files,and perform title cleaning
        """
        folder = cls._get_report_folder(report_id)
        
        # Build report header
        md_content = f"# {outline.title}\n\n"
        md_content += f"> {outline.summary}\n\n"
        md_content += f"---\n\n"
        
        # Read all chapter files sequentially
        sections = cls.get_generated_sections(report_id)
        for section_info in sections:
            md_content += section_info["content"]
        
        # Post-processing:Clean up title issues across reports
        md_content = cls._post_process_report(md_content, outline)
        
        # Save full report
        full_path = cls._get_report_markdown_path(report_id)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(f"Full report assembled: {report_id}")
        return md_content
    
    @classmethod
    def _post_process_report(cls, content: str, outline: ReportOutline) -> str:
        """
        Post-processing report content
        
        1. Remove duplicate titles
        2. Keep report main title(#)and chapter titles(##),Remove headers from other levels(###, ####wait)
        3. Clean up extra blank lines and separators
        
        Args:
            content: Original report content
            outline: Report outline
            
        Returns:
            Processed content
        """
        import re
        
        lines = content.split('\n')
        processed_lines = []
        prev_was_heading = False
        
        # Collect all chapter titles in the outline
        section_titles = set()
        for section in outline.sections:
            section_titles.add(section.title)
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Check if it is the header row
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                # Check if it is a duplicate title(in a row5Titles with the same content appear within the row)
                is_duplicate = False
                for j in range(max(0, len(processed_lines) - 5), len(processed_lines)):
                    prev_line = processed_lines[j].strip()
                    prev_match = re.match(r'^(#{1,6})\s+(.+)$', prev_line)
                    if prev_match:
                        prev_title = prev_match.group(2).strip()
                        if prev_title == title:
                            is_duplicate = True
                            break
                
                if is_duplicate:
                    # Skip repeated headers and empty lines after them
                    i += 1
                    while i < len(lines) and lines[i].strip() == '':
                        i += 1
                    continue
                
                # Title level processing:
                # - # (level=1) Keep only the main report title
                # - ## (level=2) Keep chapter titles
                # - ### and below (level>=3) Convert to bold text
                
                if level == 1:
                    if title == outline.title:
                        # Keep report main title
                        processed_lines.append(line)
                        prev_was_heading = True
                    elif title in section_titles:
                        # Chapter title used incorrectly#,Corrected to##
                        processed_lines.append(f"## {title}")
                        prev_was_heading = True
                    else:
                        # Other first-level headings are made bold
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                elif level == 2:
                    if title in section_titles or title == outline.title:
                        # Keep chapter titles
                        processed_lines.append(line)
                        prev_was_heading = True
                    else:
                        # Second-level headings that are not chapters are made bold
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                else:
                    # ### Titles at and below levels are converted to bold text
                    processed_lines.append(f"**{title}**")
                    processed_lines.append("")
                    prev_was_heading = False
                
                i += 1
                continue
            
            elif stripped == '---' and prev_was_heading:
                # Skip the separator immediately following the title
                i += 1
                continue
            
            elif stripped == '' and prev_was_heading:
                # Leave only a blank line after the title
                if processed_lines and processed_lines[-1].strip() != '':
                    processed_lines.append(line)
                prev_was_heading = False
            
            else:
                processed_lines.append(line)
                prev_was_heading = False
            
            i += 1
        
        # Clean multiple consecutive empty lines(Keep at most 2)
        result_lines = []
        empty_count = 0
        for line in processed_lines:
            if line.strip() == '':
                empty_count += 1
                if empty_count <= 2:
                    result_lines.append(line)
            else:
                empty_count = 0
                result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    @classmethod
    def save_report(cls, report: Report) -> None:
        """Save report meta information and full report"""
        cls._ensure_report_folder(report.report_id)
        
        # Save meta informationJSON
        with open(cls._get_report_path(report.report_id), 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        
        # save outline
        if report.outline:
            cls.save_outline(report.report_id, report.outline)
        
        # Save intactMarkdownReport
        if report.markdown_content:
            with open(cls._get_report_markdown_path(report.report_id), 'w', encoding='utf-8') as f:
                f.write(report.markdown_content)
        
        logger.info(f"Report Saved: {report.report_id}")
    
    @classmethod
    def get_report(cls, report_id: str) -> Optional[Report]:
        """Get report"""
        path = cls._get_report_path(report_id)
        
        if not os.path.exists(path):
            # Compatible with older formats:Checks are stored directly inreportsfiles in directory
            old_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
            if os.path.exists(old_path):
                path = old_path
            else:
                return None
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # reconstructionReportobject
        outline = None
        if data.get('outline'):
            outline_data = data['outline']
            sections = []
            for s in outline_data.get('sections', []):
                sections.append(ReportSection(
                    title=s['title'],
                    content=s.get('content', '')
                ))
            outline = ReportOutline(
                title=outline_data['title'],
                summary=outline_data['summary'],
                sections=sections
            )
        
        # ifmarkdown_contentis empty,try to start fromfull_report.mdread
        markdown_content = data.get('markdown_content', '')
        if not markdown_content:
            full_report_path = cls._get_report_markdown_path(report_id)
            if os.path.exists(full_report_path):
                with open(full_report_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
        
        return Report(
            report_id=data['report_id'],
            simulation_id=data['simulation_id'],
            graph_id=data['graph_id'],
            simulation_requirement=data['simulation_requirement'],
            status=ReportStatus(data['status']),
            outline=outline,
            markdown_content=markdown_content,
            created_at=data.get('created_at', ''),
            completed_at=data.get('completed_at', ''),
            error=data.get('error')
        )
    
    @classmethod
    def get_report_by_simulation(cls, simulation_id: str) -> Optional[Report]:
        """Get report by simulation ID"""
        cls._ensure_reports_dir()
        
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # new format:folder
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report and report.simulation_id == simulation_id:
                    return report
            # Compatible with older formats:JSONdocument
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report and report.simulation_id == simulation_id:
                    return report
        
        return None
    
    @classmethod
    def list_reports(cls, simulation_id: Optional[str] = None, limit: int = 50) -> List[Report]:
        """list reports"""
        cls._ensure_reports_dir()
        
        reports = []
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # new format:folder
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
            # Compatible with older formats:JSONdocument
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
        
        # In descending order of creation time
        reports.sort(key=lambda r: r.created_at, reverse=True)
        
        return reports[:limit]
    
    @classmethod
    def delete_report(cls, report_id: str) -> bool:
        """Delete report(entire folder)"""
        import shutil
        
        folder_path = cls._get_report_folder(report_id)
        
        # new format:Delete entire folder
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            shutil.rmtree(folder_path)
            logger.info(f"Report folder deleted: {report_id}")
            return True
        
        # Compatible with older formats:Delete individual files
        deleted = False
        old_json_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
        old_md_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.md")
        
        if os.path.exists(old_json_path):
            os.remove(old_json_path)
            deleted = True
        if os.path.exists(old_md_path):
            os.remove(old_md_path)
            deleted = True
        
        return deleted
