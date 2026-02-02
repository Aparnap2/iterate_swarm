"""Base activity module."""

# Re-export activities for easier imports
from src.activities import analyze_feedback, AnalyzeFeedbackInput, AnalyzeFeedbackOutput

__all__ = [
    "analyze_feedback",
    "AnalyzeFeedbackInput",
    "AnalyzeFeedbackOutput",
]
