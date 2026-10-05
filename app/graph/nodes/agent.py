from app.graph.state import GraphState
from langchain_aws import ChatBedrockConverse


def make_agent_node(llm_with_tools):
    async def agent_node(state: GraphState) -> dict:
        response = await llm_with_tools.ainvoke(state['messages'])
        return {'messages': [response]}

    return agent_node
