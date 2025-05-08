from google.adk.agents import Agent, LlmAgent
from .tools.kube_tools import *
from google.adk.models.lite_llm import LiteLlm
from contextlib import AsyncExitStack
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters, SseServerParams
import os


async def kubernetes_agent():
    exit_stack = AsyncExitStack()
    agent = Agent(
        name="kubernetes_agent",
        model=LiteLlm(model="bedrock/arn:aws:bedrock:us-east-1:827541288795:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0"),
        instruction="You are experienced SRE/Devops expert specialized in AWS, Kubernetes and various tools that are relevant to the cloud native ecosystem.",
        description="An assistant that can help you with your Kubernetes cluster",
        tools=[
            list_namespaces,
            list_deployments_from_namespace,
            list_deployments_all_namespaces,
            list_pods_from_namespace,
            list_pods_all_namespaces,
            list_services_from_namespace,
            list_secrets_from_namespace,
            list_daemonsets_from_namespace,
            list_configmaps_from_namespace,
            list_all_resources,
            get_deployment_details,
            get_pod_details,
            scale_deployment,
            get_pod_logs,
            get_resource_health,
            get_events,
            get_events_all_namespaces,
        ],
        output_key="kubernetes_agent_output",
    )
    return agent, exit_stack



async def create_root_agent():
    k8s_agent, k8s_exit_stack = await kubernetes_agent()

    agent = Agent(
        name="root_agent",
        model=LiteLlm(model="bedrock/arn:aws:bedrock:us-east-1:827541288795:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0"),
        description="An assistant that can help you with your Kubernetes cluster and AWS Cost Analysis",
        instruction="""
        You are an helpful assistant who tries to understand the user's request and delegates it to the most appropriate sub agent.
        Here are the sub agents available:
        - kubernetes_agent: for Kubernetes related queries
        """,
        sub_agents=[
            k8s_agent,
        ]
    )
        
    return agent, k8s_exit_stack


async def get_root_agent():
    return await create_root_agent()

# Don't call create_root_agent directly
root_agent = get_root_agent()
