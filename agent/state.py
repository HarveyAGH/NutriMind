from typing import TypedDict, Sequence, Literal, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from pydantic import BaseModel


class NutriState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_profile: dict
    meal_log: list
    next: str


class DecisionRouting(BaseModel):
    next: Literal[
        "memory_agent",
        "nutrition_rag_agent",
        "planning_agent",
        "intake_agent",
        "insight_agent",
        "FINISH",
    ]
