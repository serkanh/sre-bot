from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from contextlib import AsyncExitStack
from .tools.kube_tools import *


async def kubernetes_agent():
    exit_stack = AsyncExitStack()
    agent = Agent(
        name="kubernetes_agent",
        model=LiteLlm(
            model="bedrock/arn:aws:bedrock:us-east-1:827541288795:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0"
        ),
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
