from typing import TypedDict, Sequence, Literal, Annotated
from langgraph.graph.message import add_messages, BaseMessage
from pydantic import BaseModel


class NutriState(TypedDict):
    messages : Annotated[Sequence[BaseMessage], add_messages]
    user_profile: dict
    meal_log: list
    next: str
    
class DecisionRouting(BaseModel):
    next: Literal["profile_agent", "nutrition_agent", "recommendation_agent", "tracker_agent", "Finish"]
    
