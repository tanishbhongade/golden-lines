from langgraph.prebuilt import ToolNode
from langchain_core.messages import ToolMessage, AIMessage, SystemMessage, HumanMessage
from langchain_aws import ChatBedrockConverse
from langgraph.graph import END, START, StateGraph

from app.graph.state import GraphState
from app.core.config import settings
from app.tools import make_all_tools
from app.graph.nodes.agent import make_agent_node

MAX_TOOL_CALLS = 10

SYSTEM_PROMPT = """You answer questions about the user's personal knowledge \
base of "Golden Lines" — short sentences, insights, and principles worth remembering.

You have no knowledge of this corpus except what tools return.

Grounding:
- Every slug path you use must come from a tool result. Never invent one.
- Any name mentioned by the user: call resolve_entity first.
- If resolve_entity returns nothing or is ambiguous, ask the user.

Answering:
- When you have enough information, stop calling tools and answer.
- Quote golden lines verbatim.
- Reference pages by slug path in backticks, e.g. `golden-lines/systems-over-goals`.
- If tools returned nothing useful, say so. Do not invent.
- If a tool returns an error, read it and adjust. Do not repeat the same call.
- Do not add interpretation or context beyond what the pages contain. Quote and cite; do not gloss.
"""


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(b.get("text", ""))
        return "".join(parts)
    return str(content)


def should_continue(state: GraphState) -> str:
    tool_msgs = sum(1 for m in state['messages'] if isinstance(m, ToolMessage))
    if tool_msgs >= MAX_TOOL_CALLS:
        return END

    last = state['messages'][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"

    return END


def build_graph(pool, llm: ChatBedrockConverse):
    tools = make_all_tools(pool)
    llm_with_tools = llm.bind_tools(tools)

    agent_node = make_agent_node(llm_with_tools)
    tool_node = ToolNode(tools)

    graph = StateGraph(GraphState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {
        "tools": "tools", END: END
    })

    graph.add_edge("tools", "agent")

    return graph.compile()


def make_llm() -> ChatBedrockConverse:
    return ChatBedrockConverse(model_id=settings.llm_model, region_name=settings.aws_region)


async def run_query(question: str, pool) -> dict:
    graph = build_graph(pool, make_llm())

    initial_state: GraphState = {
        'messages': [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=question),
        ]
    }

    result = await graph.ainvoke(initial_state)

    return {
        'answer': _extract_text(result["messages"][-1].content),
        'messages': result['messages']
    }
