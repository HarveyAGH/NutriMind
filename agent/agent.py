from langchain.agents import create_agent
from langchain_aws import ChatBedrockConverse
from state import NutriState, DecisionRouting
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from IPython.display import Image, display

from langgraph.graph import StateGraph, START, END
import os




load_dotenv()
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")

supervisor_llm = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION, temperature=0)

profile_agent_llm = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION, temperature=0.1)

nutrition_agent_llm = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION, temperature=0.3)

recommendation_llm = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION, temperature=0.7)

tracker_agent_llm = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION, temperature=0)


### PROMPTS ###

PROFILE_AGENT_PROMPT = ("""""")
NUTRITION_AGENT_PROMPT = ("""""")
RECOMMENDATION_PROMPT = ("""""")
TRACKER_AGENT_PROMPT = ("""""")

SUPERVISOR_PROMPT = ("""
   You are a nutrition assistant supervisor.
Route the user's message to exactly one specialist:

- profile_agent: user is updating personal info (weight, age, goals, dietary restrictions)
- nutrition_agent: user asks about food, nutrients, calories, or health info
- recommendation_agent: user wants a meal plan or food suggestions
- tracker_agent: user is logging what they ate
- FINISH: question is fully answered, no more agents needed

Read the full conversation. Route once. Never do the work yourself.                  
                     
                     
                     """)
structured_output_supervisor = supervisor_llm.with_structured_output(DecisionRouting)

def Supervisor(state: NutriState) -> Command:
    decision = structured_output_supervisor.invoke([SystemMessage(content=SUPERVISOR_PROMPT)] + list(state["messages"])) 
    
    goto = decision.next
    if goto == "FINISH":
        return Command(goto=END)
    return Command(
        update={"next": goto}, goto=goto
    )
    
def profile_node(state: NutriState) -> Command:
    profile_agent = create_agent(
        model=profile_agent_llm,
        tools=[],
        system_prompt= PROFILE_AGENT_PROMPT
    )
    result = profile_agent.invoke({"messages": state["messages"]})
    last_message = result["messages"][-1].content
    return Command(
        update={"messages": [AIMessage(content=last_message, name = "profile_agent")]
        },
        goto="supervisor"
    )
    
def nutrition_node(state: NutriState) -> Command:
    nutrition_agent = create_agent(
        model=nutrition_agent_llm,
        tools=[],
        system_prompt=NUTRITION_AGENT_PROMPT
    )
    result = nutrition_agent.invoke({"messages": state["messages"]})
    last_message = result["messages"][-1].content
    return Command(
        update={"messages": [AIMessage(content=last_message, name= "nutrition_agent")]
        },
        goto="supervisor"
    )
    
    
def recommendation_node(state: NutriState) -> Command:
    recommendation_agent = create_agent(
        model=recommendation_llm,
        tools=[],
        system_prompt=RECOMMENDATION_PROMPT
    )
    result = recommendation_agent.invoke({'messages': state["messages"]})
    last_message = result['messages'][-1].content
    return Command(
        update={
            "messages": [AIMessage(content=last_message, name = "recommendation_agent")]
        },
        goto="supervisor"
    )
    
def tracker_node(state: NutriState) -> Command:
    tracker_agent = create_agent(
        model=tracker_agent_llm,
        tools=[],
        system_prompt= TRACKER_AGENT_PROMPT
    )
    result = tracker_agent.invoke({'messages': state["messages"]})
    last_message = result['messages'][-1].content
    return Command(
        update={
            "messages": [AIMessage(content=last_message, name= "tracker_agent")]
        },
        goto="supervisor"
    )
    
graph = StateGraph(NutriState)

# Nodes
graph.add_node("supervisor", Supervisor)
graph.add_node("profile_agent", profile_node)
graph.add_node("nutrition_agent", nutrition_node)
graph.add_node("recommendation_agent", recommendation_node)
graph.add_node("tracker_agent", tracker_node)

#Edges
graph.add_edge(START, "supervisor")

#Compile
app = graph.compile()



result = app.invoke({
    "messages": [HumanMessage(content="I want to update my weight to 70kg")],
    "user_profile": {},
    "meal_log": [],
    "next": ""
})

print(result["messages"][-1].content)



