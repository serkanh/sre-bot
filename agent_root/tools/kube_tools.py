from kubernetes import client, config
from kubernetes.client.rest import ApiException
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone

config.load_config()


api_v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()
batch_v1 = client.BatchV1Api()


def list_namespaces() -> list:
    """
    List all namespaces in the Kubernetes cluster.

    Returns:
        list: A list of namespace names.
    """
    namespaces = api_v1.list_namespace()
    return [ns.metadata.name for ns in namespaces.items]


def list_deployments_from_namespace(namespace: str = "default") -> list:
    """
    List all deployments in a specific namespace.

    Args:
        namespace (str): The namespace to list deployments from. Defaults to "default".

    Returns:
        list: A list of deployment names in the specified namespace.
    """
    deployments = apps_v1.list_namespaced_deployment(namespace)
    return [deploy.metadata.name for deploy in deployments.items]


def list_deployments_all_namespaces() -> List[Dict]:
    """
    List deployments across all namespaces.

    Returns:
        List[Dict]: A list of dictionaries, each containing deployment name and namespace.
    """
    try:
        deployments = apps_v1.list_deployment_for_all_namespaces()
        return [
            {
                "name": deploy.metadata.name,
                "namespace": deploy.metadata.namespace,
                "replicas": deploy.spec.replicas,
            }
            for deploy in deployments.items
        ]
    except ApiException as e:
        return [
            {"error": f"Failed to list deployments across all namespaces: {str(e)}"}
        ]


def list_pods_from_namespace(namespace: str = "default") -> list:
    """
    List all pods in a specific namespace.

    Args:
        namespace (str): The namespace to list pods from. Defaults to "default".

    Returns:
        list: A list of pod names in the specified namespace.
    """
    pods = api_v1.list_namespaced_pod(namespace)
    return [pod.metadata.name for pod in pods.items]


def list_pods_all_namespaces() -> List[Dict]:
    """
    List pods across all namespaces.

    Returns:
        List[Dict]: A list of dictionaries, each containing pod name, namespace, and status.
    """
    try:
        pods = api_v1.list_pod_for_all_namespaces()
        return [
            {
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "status": pod.status.phase,
            }
            for pod in pods.items
        ]
    except ApiException as e:
        return [{"error": f"Failed to list pods across all namespaces: {str(e)}"}]


def list_services_from_namespace(namespace: str = "default") -> list:
    """
    List all services in a specific namespace.

    Args:
        namespace (str): The namespace to list services from. Defaults to "default".

    Returns:
        list: A list of service names in the specified namespace.
    """
    services = api_v1.list_namespaced_service(namespace)
    return [svc.metadata.name for svc in services.items]


def list_secrets_from_namespace(namespace: str = "default") -> list:
    """
    List all secrets in a specific namespace.

    Args:
        namespace (str): The namespace to list secrets from. Defaults to "default".

    Returns:
        list: A list of secret names in the specified namespace.
    """
    secrets = api_v1.list_namespaced_secret(namespace)
    return [secret.metadata.name for secret in secrets.items]


def list_daemonsets_from_namespace(namespace: str = "default") -> list:
    """
    List all daemonsets in a specific namespace.

    Args:
        namespace (str): The namespace to list daemonsets from. Defaults to "default".

    Returns:
        list: A list of daemonset names in the specified namespace.
    """
    daemonsets = apps_v1.list_namespaced_daemon_set(namespace)
    return [ds.metadata.name for ds in daemonsets.items]


def list_configmaps_from_namespace(namespace: str = "default") -> list:
    """
    List all configmaps in a specific namespace.

    Args:
        namespace (str): The namespace to list configmaps from. Defaults to "default".

    Returns:
        list: A list of configmap names in the specified namespace.
    """
    configmaps = api_v1.list_namespaced_config_map(namespace)
    return [cm.metadata.name for cm in configmaps.items]


def list_all_resources(namespace: str = "default") -> dict:
    """
    List all resources in a specific namespace.

    Args:
        namespace (str): The namespace to list resources from. Defaults to "default".

    Returns:
        dict: A dictionary containing lists of deployments, pods, services, secrets, daemonsets, and configmaps for a specific namespace.
    """
    resources = {
        "deployments": list_deployments_from_namespace(namespace),
        "pods": list_pods_from_namespace(namespace),
        "services": list_services_from_namespace(namespace),
        "secrets": list_secrets_from_namespace(namespace),
        "daemonsets": list_daemonsets_from_namespace(namespace),
        "configmaps": list_configmaps_from_namespace(namespace),
    }
    return resources


def get_deployment_details(deployment_name: str, namespace: str = "default") -> Dict:
    """
    Get detailed information about a specific deployment.

    Args:
        deployment_name (str): The name of the deployment.
        namespace (str): The namespace of the deployment. Defaults to "default".

    Returns:
        Dict: Detailed information about the deployment.
    """
    try:
        deployment = apps_v1.read_namespaced_deployment(deployment_name, namespace)
        return {
            "name": deployment.metadata.name,
            "namespace": deployment.metadata.namespace,
            "replicas": deployment.spec.replicas,
            "available_replicas": deployment.status.available_replicas,
            "strategy": deployment.spec.strategy.type,
            "containers": [
                container.name for container in deployment.spec.template.spec.containers
            ],
        }
    except ApiException as e:
        return {"error": f"Failed to get deployment details: {str(e)}"}


def get_pod_details(pod_name: str, namespace: str = "default") -> Dict:
    """
    Get detailed information about a specific pod.

    Args:
        pod_name (str): The name of the pod.
        namespace (str): The namespace of the pod. Defaults to "default".

    Returns:
        Dict: Detailed information about the pod.
    """
    try:
        pod = api_v1.read_namespaced_pod(pod_name, namespace)
        return {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "status": pod.status.phase,
            "node": pod.spec.node_name,
            "containers": [container.name for container in pod.spec.containers],
            "start_time": pod.status.start_time,
            "ip": pod.status.pod_ip,
        }
    except ApiException as e:
        return {"error": f"Failed to get pod details: {str(e)}"}


def scale_deployment(
    deployment_name: str, replicas: int, namespace: str = "default"
) -> Dict:
    """
    Scale a deployment to a specific number of replicas.

    Args:
        deployment_name (str): The name of the deployment.
        replicas (int): The desired number of replicas.
        namespace (str): The namespace of the deployment. Defaults to "default".

    Returns:
        Dict: Status of the scaling operation.
    """
    try:
        body = {"spec": {"replicas": replicas}}
        apps_v1.patch_namespaced_deployment_scale(deployment_name, namespace, body)
        return {
            "status": "success",
            "message": f"Scaled deployment {deployment_name} in namespace {namespace} to {replicas} replicas",
        }
    except ApiException as e:
        return {"status": "error", "message": f"Failed to scale deployment: {str(e)}"}


def get_pod_logs(
    pod_name: str,
    namespace: str = "default",
    container: Optional[str] = None,
    tail_lines: int = 100,
) -> str:
    """
    Get logs from a specific pod.

    Args:
        pod_name (str): The name of the pod.
        namespace (str): The namespace of the pod. Defaults to "default".
        container (str, optional): The name of the container to get logs from.
        tail_lines (int): Number of lines to return from the end of the logs.

    Returns:
        str: The pod logs.
    """
    try:
        return api_v1.read_namespaced_pod_log(
            pod_name, namespace, container=container, tail_lines=tail_lines
        )
    except ApiException as e:
        return f"Failed to get pod logs: {str(e)}"


def get_resource_health(
    resource_name: str, resource_type: str, namespace: str = "default"
) -> Dict:
    """
    Get health status of a specific resource.

    Args:
        resource_name (str): Name of the resource.
        resource_type (str): Type of resource (pod, deployment, service).
        namespace (str): The namespace of the resource. Defaults to "default".

    Returns:
        Dict: Health status of the resource.
    """
    try:
        if resource_type == "pod":
            pod = api_v1.read_namespaced_pod(resource_name, namespace)
            # Check if container_statuses is None before summing restart counts
            restart_count = (
                sum(cs.restart_count for cs in pod.status.container_statuses)
                if pod.status.container_statuses
                else 0
            )
            return {
                "status": pod.status.phase,
                "ready": all(
                    condition.status == "True"
                    for condition in pod.status.conditions
                    if pod.status.conditions
                ),
                "restart_count": restart_count,
            }
        elif resource_type == "deployment":
            deployment = apps_v1.read_namespaced_deployment(resource_name, namespace)
            return {
                "status": "Healthy"
                if deployment.status.available_replicas == deployment.spec.replicas
                else "Unhealthy",
                "available_replicas": deployment.status.available_replicas,
                "desired_replicas": deployment.spec.replicas,
            }
        else:
            return {"error": f"Unsupported resource type: {resource_type}"}
    except ApiException as e:
        return {"error": f"Failed to get resource health: {str(e)}"}


def _format_k8s_events(events_items: List) -> List[Dict]:
    """Internal helper to format Kubernetes event objects."""
    formatted_events = []
    for event in events_items:
        formatted_events.append(
            {
                "name": event.metadata.name,
                "namespace": event.metadata.namespace,
                "type": event.type,
                "reason": event.reason,
                "message": event.message,
                "source": {
                    "component": event.source.component if event.source else None,
                    "host": event.source.host if event.source else None,
                },
                "first_seen": event.first_timestamp.isoformat()
                if event.first_timestamp
                else None,
                "last_seen": event.last_timestamp.isoformat()
                if event.last_timestamp
                else None,
                "count": event.count,
                "involved_object": {
                    "kind": event.involved_object.kind,
                    "name": event.involved_object.name,
                    "namespace": event.involved_object.namespace,
                }
                if event.involved_object
                else None,
            }
        )
    return formatted_events


def get_events(
    namespace: str = "default",
    limit: int = 200,
    time_window_minutes: Optional[int] = None,
) -> List[Dict]:
    """
    Get Kubernetes events for a specific namespace with a configurable limit and time window.

    Args:
        namespace (str): The namespace to get events from. Defaults to "default".
        limit (int): Maximum number of events to return. Default is 200.
        time_window_minutes (Optional[int]): If provided, only return events from the last N minutes.
                                           Can be used to specify minutes or hours (e.g., 60 for last hour,
                                           1440 for last day).

    Returns:
        List[Dict]: List of events with their details.
    """
    try:
        events = api_v1.list_namespaced_event(namespace, limit=limit)
        formatted_events = _format_k8s_events(events.items)

        # Filter by time window if specified
        if time_window_minutes is not None:
            # Create timezone-aware datetime in UTC
            cutoff_time = datetime.now(timezone.utc) - timedelta(
                minutes=time_window_minutes
            )
            formatted_events = [
                event
                for event in formatted_events
                if event["last_seen"] is not None
                and datetime.fromisoformat(event["last_seen"]) >= cutoff_time
            ]

        return formatted_events
    except ApiException as e:
        return [{"error": f"Failed to get events for namespace {namespace}: {str(e)}"}]


def get_events_all_namespaces(
    limit: int = 200, time_window_minutes: Optional[int] = None
) -> List[Dict]:
    """
    Get Kubernetes events across all namespaces with a configurable limit and time window.

    Args:
        limit (int): Maximum number of events to return. Default is 200.
        time_window_minutes (Optional[int]): If provided, only return events from the last N minutes.
                                           Can be used to specify minutes or hours (e.g., 60 for last hour,
                                           1440 for last day).

    Returns:
        List[Dict]: List of events from all namespaces with their details.
    """
    try:
        events = api_v1.list_event_for_all_namespaces(limit=limit)
        formatted_events = _format_k8s_events(events.items)

        # Filter by time window if specified
        if time_window_minutes is not None:
            # Create timezone-aware datetime in UTC
            cutoff_time = datetime.now(timezone.utc) - timedelta(
                minutes=time_window_minutes
            )
            formatted_events = [
                event
                for event in formatted_events
                if event["last_seen"] is not None
                and datetime.fromisoformat(event["last_seen"]) >= cutoff_time
            ]

        return formatted_events
    except ApiException as e:
        return [{"error": f"Failed to get events across all namespaces: {str(e)}"}]


__all__ = [
    "list_namespaces",
    "list_deployments_from_namespace",
    "list_deployments_all_namespaces",
    "list_pods_from_namespace",
    "list_pods_all_namespaces",
    "list_services_from_namespace",
    "list_secrets_from_namespace",
    "list_daemonsets_from_namespace",
    "list_configmaps_from_namespace",
    "list_all_resources",
    "get_deployment_details",
    "get_pod_details",
    "scale_deployment",
    "get_pod_logs",
    "get_resource_health",
    "get_events",
    "get_events_all_namespaces",
]
