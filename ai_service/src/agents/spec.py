"""Spec Writer Agent using LangGraph for GitHub Issue creation.

This agent takes classified feedback and writes a production-ready GitHub Issue spec.
"""

import logging
from typing import Any, TypedDict
from uuid import uuid4

import structlog
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langfuse import observe
from langgraph.graph import END, StateGraph
from openai import AsyncOpenAI

from src.core.config import settings

logger = structlog.get_logger(__name__)


# ========================
# State Definition
# ========================


class SpecState(TypedDict):
    """State for the Spec Writer Agent workflow."""

    # Input
    feedback_id: str
    content: str
    source: str

    # From triage
    classification: str
    severity: str
    reasoning: str
    confidence: float

    # Output
    title: str
    reproduction_steps: list[str]
    affected_components: list[str]
    acceptance_criteria: list[str]
    suggested_labels: list[str]
    spec_confidence: float


# ========================
# Pydantic Models for Structured Output
# ========================


from pydantic import BaseModel, Field


class SpecResult(BaseModel):
    """Structured output from the Spec Writer Agent."""

    title: str = Field(
        description="A concise, descriptive title for the GitHub Issue",
        min_length=5,
        max_length=100,
    )
    reproduction_steps: list[str] = Field(
        description="Step-by-step instructions to reproduce the issue (for bugs)",
        min_length=0,
        max_length=10,
    )
    affected_components: list[str] = Field(
        description="List of affected components or modules",
        min_length=1,
        max_length=5,
    )
    acceptance_criteria: list[str] = Field(
        description="List of measurable acceptance criteria for resolution",
        min_length=1,
        max_length=5,
    )
    suggested_labels: list[str] = Field(
        description="GitHub labels based on classification and severity",
        min_length=1,
        max_length=5,
    )
    spec_confidence: float = Field(
        description="Confidence score from 0.0 to 1.0",
        ge=0.0,
        le=1.0,
    )


# ========================
# LLM Client Factory
# ========================


def get_llm_client() -> AsyncOpenAI:
    """Get configured OpenAI-compatible LLM client.

    Uses Ollama with qwen2.5-coder for local development.
    """
    return AsyncOpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama",  # Dummy key for Ollama
        model="qwen2.5-coder:3b",
    )


# ========================
# Prompt Template
# ========================


SPEC_SYSTEM_PROMPT = """You are a Senior Product Manager and Technical Writer.

Your job is to transform categorized feedback into production-ready GitHub Issues.

Guidelines:
- **Title**: Be specific and actionable (e.g., "Fix login timeout on mobile Safari" not "Bug in login")
- **Reproduction Steps**: For bugs, provide clear, numbered steps anyone can follow
- **Components**: Identify affected code areas (auth, API, frontend, database, etc.)
- **Acceptance Criteria**: Write measurable, testable criteria for resolution
- **Labels**: Suggest GitHub labels based on type and severity

For feature requests:
- Focus on user stories and business value
- Identify potential edge cases
- Suggest implementation approach if helpful

For questions:
- Summarize what information is being asked
- Suggest where to find the answer in documentation"""


SPEC_HUMAN_PROMPT = """Transform the following feedback into a GitHub Issue spec:

---
Feedback ID: {feedback_id}
Source: {source}
Content: {content}
---

Classification: {classification} (confidence: {confidence:.2f})
Severity: {severity}
Reasoning: {reasoning}
---

{format_instructions}
"""


# ========================
# Agent Node
# ========================


@observe(name="spec_writer.write")
async def spec_writer_node(state: SpecState) -> dict[str, Any]:
    """Write a GitHub Issue spec from classified feedback.

    Args:
        state: The current spec writer state

    Returns:
        Updated state with spec details
    """
    logger.info(
        "Writing spec for feedback",
        feedback_id=state["feedback_id"],
        classification=state["classification"],
    )

    try:
        # Initialize LLM client
        llm = get_llm_client()

        # Create prompt
        parser = PydanticOutputParser(pydantic_object=SpecResult)

        prompt = ChatPromptTemplate.from_messages([
            ("system", SPEC_SYSTEM_PROMPT),
            ("human", SPEC_HUMAN_PROMPT),
        ])

        # Format the prompt
        formatted_prompt = prompt.format_messages(
            feedback_id=state["feedback_id"],
            source=state["source"],
            content=state["content"],
            classification=state["classification"],
            severity=state["severity"],
            reasoning=state["reasoning"],
            confidence=state["confidence"],
            format_instructions=parser.get_format_instructions(),
        )

        # Call LLM with structured output
        response = await llm.chat.completions.create(
            messages=[HumanMessage(content=formatted_prompt[1].content)],
            model="qwen2.5-coder:3b",
            temperature=0.2,
        )

        # Parse structured output
        result = parser.parse(response.choices[0].message.content)

        logger.info(
            "Spec written successfully",
            feedback_id=state["feedback_id"],
            title=result.title,
            components=result.affected_components,
        )

        return {
            "title": result.title,
            "reproduction_steps": result.reproduction_steps,
            "affected_components": result.affected_components,
            "acceptance_criteria": result.acceptance_criteria,
            "suggested_labels": result.suggested_labels,
            "spec_confidence": result.spec_confidence,
        }

    except Exception as e:
        logger.error(
            "Spec writing failed",
            feedback_id=state["feedback_id"],
            error=str(e),
        )
        # Return safe defaults on error
        return {
            "title": f"[{state['classification'].upper()}] {state['content'][:80]}",
            "reproduction_steps": [],
            "affected_components": ["unknown"],
            "acceptance_criteria": ["Verify the issue is resolved"],
            "suggested_labels": [state["classification"], state["severity"]],
            "spec_confidence": 0.0,
        }


# ========================
# Graph Compilation
# ========================


def create_spec_graph() -> StateGraph:
    """Create and compile the Spec Writer Agent workflow graph.

    Returns:
        Compiled StateGraph ready for invocation
    """
    # Create the graph
    workflow = StateGraph(SpecState)

    # Add the spec writer node
    workflow.add_node("spec_writer", spec_writer_node)

    # Set entry point
    workflow.set_entry_point("spec_writer")

    # Add edge to end (single node workflow)
    workflow.add_edge("spec_writer", END)

    # Compile the graph with debug checks
    return workflow.compile()


# Create the compiled graph
spec_graph = create_spec_graph()


# ========================
# Convenience Functions
# ========================


async def write_spec(
    feedback_id: str,
    content: str,
    source: str,
    classification: str,
    severity: str,
    reasoning: str,
    confidence: float,
) -> SpecResult:
    """Convenience function to write a spec for a single feedback item.

    Args:
        feedback_id: Unique identifier for the feedback
        content: The feedback text
        source: Where the feedback came from
        classification: From triage (bug/feature/question)
        severity: From triage (low/medium/high/critical)
        reasoning: From triage explanation
        confidence: From triage confidence score

    Returns:
        SpecResult with title, reproduction steps, components, etc.
    """
    initial_state: SpecState = {
        "feedback_id": feedback_id,
        "content": content,
        "source": source,
        "classification": classification,
        "severity": severity,
        "reasoning": reasoning,
        "confidence": confidence,
        "title": "",
        "reproduction_steps": [],
        "affected_components": [],
        "acceptance_criteria": [],
        "suggested_labels": [],
        "spec_confidence": 0.0,
    }

    result = await spec_graph.ainvoke(initial_state)

    return SpecResult(
        title=result["title"],
        reproduction_steps=result["reproduction_steps"],
        affected_components=result["affected_components"],
        acceptance_criteria=result["acceptance_criteria"],
        suggested_labels=result["suggested_labels"],
        spec_confidence=result["spec_confidence"],
    )
