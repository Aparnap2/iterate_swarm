"""LangGraph Agent for writing GitHub Issue specs."""

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


class SpecState(TypedDict):
    """State for the Spec Writer Agent workflow."""

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
# Pydantic Models
# ========================


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


SPEC_SYSTEM_PROMPT = """You are a Senior Product Manager and Technical Writer.

Your job is to transform categorized feedback into production-ready GitHub Issues.

Guidelines:
- **Title**: Be specific and actionable (e.g., "Fix login timeout on mobile Safari")
- **Reproduction Steps**: For bugs, provide clear, numbered steps
- **Components**: Identify affected code areas (auth, API, frontend, database)
- **Acceptance Criteria**: Write measurable, testable criteria
- **Labels**: Suggest GitHub labels based on type and severity

For feature requests: Focus on user stories and business value.
For questions: Summarize what information is being asked."""


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

{format_instructions}"""


# ========================
# Agent Node
# ========================


async def spec_writer_node(state: SpecState) -> dict[str, Any]:
    """Write a GitHub Issue spec from classified feedback."""
    llm = get_llm_client()

    parser = PydanticOutputParser(pydantic_object=SpecResult)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SPEC_SYSTEM_PROMPT),
        ("human", SPEC_HUMAN_PROMPT),
    ])

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

    response = await llm.chat.completions.create(
        messages=[HumanMessage(content=formatted_prompt[1].content)],
        model=get_config().ollama.model,
        temperature=0.2,
    )

    result = parser.parse(response.choices[0].message.content)

    return {
        "title": result.title,
        "reproduction_steps": result.reproduction_steps,
        "affected_components": result.affected_components,
        "acceptance_criteria": result.acceptance_criteria,
        "suggested_labels": result.suggested_labels,
        "spec_confidence": result.spec_confidence,
    }


# ========================
# Graph Compilation
# ========================


def create_spec_graph() -> StateGraph:
    """Create and compile the Spec Writer Agent workflow graph."""
    workflow = StateGraph(SpecState)
    workflow.add_node("spec_writer", spec_writer_node)
    workflow.set_entry_point("spec_writer")
    workflow.add_edge("spec_writer", END)
    return workflow.compile()


# Create the compiled graph
spec_graph = create_spec_graph()


# ========================
# Convenience Function
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
    """Convenience function to write a spec for a single feedback item."""
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
