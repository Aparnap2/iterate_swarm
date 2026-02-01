"""Triage Agent using LangGraph for feedback classification.

This agent analyzes feedback and classifies it as:
- bug: Something is broken or not working
- feature: A request for new functionality
- question: A user inquiry that doesn't indicate a problem
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


class TriageState(TypedDict):
    """State for the Triage Agent workflow."""

    # Input
    feedback_id: str
    content: str
    source: str

    # Output
    classification: str  # bug, feature, or question
    severity: str  # low, medium, high, critical
    reasoning: str
    confidence: float


# ========================
# Pydantic Models for Structured Output
# ========================


from pydantic import BaseModel, Field


class TriageResult(BaseModel):
    """Structured output from the Triage Agent."""

    classification: str = Field(
        description="Classification: 'bug', 'feature', or 'question'",
        pattern="^(bug|feature|question)$",
    )
    severity: str = Field(
        description="Severity level: 'low', 'medium', 'high', or 'critical'",
        pattern="^(low|medium|high|critical)$",
    )
    reasoning: str = Field(
        description="Brief explanation of the classification decision",
        min_length=10,
    )
    confidence: float = Field(
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


TRIAGE_SYSTEM_PROMPT = """You are a Triage Agent for a software project.

Your job is to analyze incoming user feedback and classify it accurately.

Classification Rules:
- **bug**: The feedback reports something that is broken, not working as expected, or producing errors.
- **feature**: The feedback requests new functionality, improvements, or capabilities that don't exist.
- **question**: The feedback is asking for help, clarification, or information without indicating a problem.

Severity Guidelines:
- **critical**: Data loss, security vulnerability, or complete system failure
- **high**: Major feature broken, affects many users, workarounds unavailable
- **medium**: Feature partially broken, affects some users, workaround exists
- **low**: Minor issue, cosmetic, or easy to work around

Output Requirements:
Provide your classification with clear reasoning. Be confident but honest about uncertainty."""

TRIAGE_HUMAN_PROMPT = """Analyze the following feedback:

---
Feedback ID: {feedback_id}
Source: {source}
Content: {content}
---

{format_instructions}
"""


# ========================
# Agent Node
# ========================


@observe(name="triage_agent.classify")
async def triage_node(state: TriageState) -> dict[str, Any]:
    """Process feedback and classify it.

    Args:
        state: The current triage state

    Returns:
        Updated state with classification results
    """
    logger.info(
        "Processing feedback for triage",
        feedback_id=state["feedback_id"],
        content_preview=state["content"][:100],
    )

    try:
        # Initialize LLM client
        llm = get_llm_client()

        # Create prompt
        parser = PydanticOutputParser(pydantic_object=TriageResult)

        prompt = ChatPromptTemplate.from_messages([
            ("system", TRIAGE_SYSTEM_PROMPT),
            ("human", TRIAGE_HUMAN_PROMPT),
        ])

        # Format the prompt
        formatted_prompt = prompt.format_messages(
            feedback_id=state["feedback_id"],
            source=state["source"],
            content=state["content"],
            format_instructions=parser.get_format_instructions(),
        )

        # Call LLM with structured output
        response = await llm.chat.completions.create(
            messages=[HumanMessage(content=formatted_prompt[1].content)],
            model="qwen2.5-coder:3b",
            temperature=0.1,
        )

        # Parse structured output
        result = parser.parse(response.choices[0].message.content)

        logger.info(
            "Triage complete",
            feedback_id=state["feedback_id"],
            classification=result.classification,
            severity=result.severity,
            confidence=result.confidence,
        )

        return {
            "classification": result.classification,
            "severity": result.severity,
            "reasoning": result.reasoning,
            "confidence": result.confidence,
        }

    except Exception as e:
        logger.error(
            "Triage failed",
            feedback_id=state["feedback_id"],
            error=str(e),
        )
        # Return safe defaults on error
        return {
            "classification": "question",
            "severity": "low",
            "reasoning": f"Classification failed: {str(e)}. Defaulting to question.",
            "confidence": 0.0,
        }


# ========================
# Graph Compilation
# ========================


def create_triage_graph() -> StateGraph:
    """Create and compile the Triage Agent workflow graph.

    Returns:
        Compiled StateGraph ready for invocation
    """
    # Create the graph
    workflow = StateGraph(TriageState)

    # Add the triage node
    workflow.add_node("triage", triage_node)

    # Set entry point
    workflow.set_entry_point("triage")

    # Add edge to end (single node workflow)
    workflow.add_edge("triage", END)

    # Compile the graph with debug checks
    return workflow.compile()


# Create the compiled graph
triage_graph = create_triage_graph()


# ========================
# Convenience Functions
# ========================


async def classify_feedback(
    feedback_id: str,
    content: str,
    source: str = "unknown",
) -> TriageResult:
    """Convenience function to classify a single feedback item.

    Args:
        feedback_id: Unique identifier for the feedback
        content: The feedback text
        source: Where the feedback came from (discord, slack, etc.)

    Returns:
        TriageResult with classification and severity
    """
    initial_state: TriageState = {
        "feedback_id": feedback_id,
        "content": content,
        "source": source,
        "classification": "question",  # Default
        "severity": "low",  # Default
        "reasoning": "",
        "confidence": 0.0,
    }

    result = await triage_graph.ainvoke(initial_state)

    return TriageResult(
        classification=result["classification"],
        severity=result["severity"],
        reasoning=result["reasoning"],
        confidence=result["confidence"],
    )
