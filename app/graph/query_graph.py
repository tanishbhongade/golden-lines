from langgraph.prebuilt import ToolNode
from langchain_core.messages import ToolMessage, AIMessage, SystemMessage, HumanMessage
from langchain_aws import ChatBedrockConverse
from langgraph.graph import END, START, StateGraph

from app.graph.state import GraphState
from app.core.config import settings
from app.tools import make_all_tools
from app.graph.nodes.agent import make_agent_node

MAX_TOOL_CALLS = 10

SYSTEM_PROMPT = """You answer questions about the user's personal knowledge base \
of "Golden Lines" — short sentences, insights, and principles worth remembering.

You have no knowledge of this corpus except what tools return.

Grounding:
- Every slug path you use must come from a tool result. Never invent one.
- Any name mentioned by the user: call resolve_entity first.
- If resolve_entity returns nothing or is ambiguous, ask the user.

Searching:
- If your first search returns a plausible match, use it. Only re-search with
  reworded queries if the previous search returned nothing relevant.
- Do not run the same search twice with synonyms. One query per intent.

Answering:
- When you have enough information, stop calling tools and answer.
- Quote golden lines verbatim.
- Reference pages by slug path in backticks, e.g. `golden-lines/systems-over-goals`.
- If tools returned nothing useful, say so. Do not invent.
- If a tool returns an error, read it and adjust. Do not repeat the same call.
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


import json
from langchain_core.messages import ToolMessage


def _get_page_paths(messages: list) -> list[str]:
    """Pages the agent explicitly fetched."""
    seen: set[str] = set()
    ordered: list[str] = []
    for m in messages:
        if not isinstance(m, ToolMessage):
            continue
        if getattr(m, "name", "") != "get_page":
            continue
        content = m.content
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                continue
        if isinstance(content, dict):
            key = content.get("path") or content.get("key")
            if isinstance(key, str) and key not in seen:
                seen.add(key)
                ordered.append(key)
    return ordered


def _top_search_path(messages: list) -> str | None:
    """Highest-scoring line_path across all search calls."""
    best_score = -1.0
    best_path: str | None = None

    for m in messages:
        if not isinstance(m, ToolMessage):
            continue
        if getattr(m, "name", "") not in ("semantic_search", "hybrid_search"):
            continue
        content = m.content
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                continue
        if not isinstance(content, dict):
            continue
        for row in content.get("results", []):
            score = row.get("score", 0.0)
            path = row.get("line_path")
            if path and score > best_score:
                best_score = score
                best_path = path

    return best_path


def _extract_citations(messages: list) -> list[str]:
    """
    Pages that contributed to the answer.

    Primary: pages the agent explicitly fetched via get_page.
    Fallback: the highest-scoring search result when no get_page was made.
    """
    fetched = _get_page_paths(messages)
    if fetched:
        return fetched

    top = _top_search_path(messages)
    return [top] if top else []


async def run_query(question: str, pool) -> dict:
    graph = build_graph(pool, make_llm())
    initial_state: GraphState = {
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=question),
        ]
    }
    result = await graph.ainvoke(initial_state)
    messages = result["messages"]
    return {
        "answer": _extract_text(messages[-1].content),
        "citations": _extract_citations(messages),
        "messages": messages,
    }
