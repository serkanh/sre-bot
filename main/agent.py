from google.adk.agents import LlmAgent
from google.adk.agents.utils import load_instruction_template
from .tools.kube_tools import *

kubernetes_agent = LlmAgent(
    name="kubernetes_agent",
    model="gemini-2.0-flash-exp",
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
        get_events_all_namespaces
    ],
    output_key="kubernetes_agent_output"
)

sre_agent = LlmAgent(
    name="sre_agent",
    model="gemini-2.0-flash-exp",
    instruction="You are experienced SRE/Devops expert specialized in AWS, Kubernetes and various tools that are relevant to the cloud native ecosystem.",
    description="An assistant that can help you with your Kubernetes cluster",
    instruction_template=load_instruction_template("sre_agent_context.txt"),
    sub_agents=[
        kubernetes_agent
    ]
)

root_agent = sre_agent
