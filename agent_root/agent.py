from google.adk.agents import Agent, LlmAgent
from .tools.kube_tools import *
from google.adk.models.lite_llm import LiteLlm
from contextlib import AsyncExitStack
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters, SseServerParams
import os

kubernetes_agent = Agent(
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




async def create_cost_analysis_agent():
  """Gets tools from MCP Server."""
  common_exit_stack = AsyncExitStack()

  local_tools, _ = await MCPToolset.from_server(
      connection_params=StdioServerParameters(
          # Use this for AWS Cost Analysis
          command='uvx',
          args= ["awslabs.cost-analysis-mcp-server@latest"],
          env={
            "FASTMCP_LOG_LEVEL": "ERROR",
            "AWS_PROFILE": os.environ.get("AWS_PROFILE", "default")
            },
            disabled = False,
            autoApprove = []
      ),
      async_exit_stack=common_exit_stack
  )

  agent = LlmAgent(
    name="sre_agent",
    model=LiteLlm(model="bedrock/arn:aws:bedrock:us-east-1:827541288795:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0"),
    description="An assistant to help you with your AWS Cost Analysis",
    instruction="You are an expert in AWS Cost Analysis and you can help me with my AWS Cost Analysis",
    tools=[
        *local_tools,
    ],
)
  return agent, common_exit_stack

cost_analysis_agent = create_cost_analysis_agent()


root_agent = create_agent()
