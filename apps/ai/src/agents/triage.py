"""LangGraph Agent for feedback triage (classification + severity)."""

from typing import Any, TypedDict

from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from src.config import get_config


# ========================
# State Definition
# ========================


class TriageState(TypedDict):
    """State for the Triage Agent workflow."""

    feedback_id: str
    content: str
    source: str

    # Output
    classification: str  # bug, feature, or question
    severity: str  # low, medium, high, critical
    reasoning: str
    confidence: float


# ========================
# Pydantic Models
# ========================


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
# LLM Client
# ========================


def get_llm_client() -> AsyncOpenAI:
    """Get configured OpenAI-compatible LLM client (Ollama)."""
    config = get_config().ollama
    return AsyncOpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
    )


# ========================
# Prompt Templates
# ========================


TRIAGE_SYSTEM_PROMPT = """You are a Triage Agent for a software project.

Your job is to analyze incoming user feedback and classify it accurately.

Classification Rules:
- **bug**: The feedback reports something broken, not working, or producing errors.
- **feature**: The feedback requests new functionality or improvements.
- **question**: The feedback asks for help without indicating a problem.

Severity Guidelines:
- **critical**: Data loss, security vulnerability, or complete system failure
- **high**: Major feature broken, affects many users, no workaround
- **medium**: Feature partially broken, affects some users, workaround exists
- **low**: Minor issue, cosmetic, or easy to work around

Output your classification with clear reasoning."""


TRIAGE_HUMAN_PROMPT = """Analyze the following feedback:

---
Feedback ID: {feedback_id}
Source: {source}
Content: {content}
---

{format_instructions}"""


# ========================
# Agent Node
# ========================


async def triage_node(state: TriageState) -> dict[str, Any]:
    """Process feedback and classify it."""
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
        model=get_config().ollama.model,
        temperature=0.1,
    )

    # Parse structured output
    result = parser.parse(response.choices[0].message.content)

    return {
        "classification": result.classification,
        "severity": result.severity,
        "reasoning": result.reasoning,
        "confidence": result.confidence,
    }


# ========================
# Graph Compilation
# ========================


def create_triage_graph() -> StateGraph:
    """Create and compile the Triage Agent workflow graph."""
    workflow = StateGraph(TriageState)
    workflow.add_node("triage", triage_node)
    workflow.set_entry_point("triage")
    workflow.add_edge("triage", END)
    return workflow.compile()


# Create the compiled graph
triage_graph = create_triage_graph()


# ========================
# Convenience Function
# ========================


async def classify_feedback(
    feedback_id: str,
    content: str,
    source: str = "unknown",
) -> TriageResult:
    """Convenience function to classify a single feedback item."""
    initial_state: TriageState = {
        "feedback_id": feedback_id,
        "content": content,
        "source": source,
        "classification": "question",
        "severity": "low",
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
