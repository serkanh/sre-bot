# SRE Assistant Agent

A Google Agent Development Kit (ADK) powered assistant designed to help Site Reliability Engineers (SREs) with operational tasks and monitoring, particularly focused on Kubernetes interactions.

![Cost Reporting Demo](https://github.com/serkanh/static-files/blob/main/gifs/cost-reporting-demo.gif?raw=true)

![Kubernetes Demo](https://github.com/serkanh/static-files/blob/main/gifs/eks-cluster-demo.gif?raw=true)

## Overview

This repository contains an SRE Assistant Agent built with Google's Agent Development Kit (ADK). It aims to assist SREs by automating common tasks, providing system insights, and streamlining incident response through natural language conversations. The agent leverages Google's large language models to understand user queries and interacts with various monitoring, operational, and cloud service tools via defined functions and sub-agents.

## Features

The SRE Assistant includes tools and sub-agents for interacting with:

- **Kubernetes Clusters:**
  - List resources (Namespaces, Deployments, Pods, Services, Secrets, DaemonSets, ConfigMaps) across all namespaces or within a specific namespace.
  - Get detailed information about specific Deployments and Pods.
  - Scale Deployments.
  - Retrieve logs from Pods.
  - Get resource health information.
  - Fetch cluster events.
- **AWS Services & Cost Management:**
  - **AWS Core MCP Agent**: Provides capabilities for general interactions with core AWS services (details on specific tools to be added as developed).
  - **AWS Cost Analysis MCP Agent**: Offers tools and functions for querying and analyzing AWS cost and usage data (details on specific tools to be added as developed).
  - **AWS Cost Agent**: A specialized sub-agent dedicated to in-depth AWS cost analysis, reporting, and providing insights.

## Prerequisites

- Python 3.10+ (as defined in `Dockerfile`)
- Docker and Docker Compose
- Google API key for Gemini access (https://aistudio.google.com/apikey)
- Access credentials/configurations for any systems the bot needs to interact with:
    - Configured `kubectl` access to your Kubernetes cluster (`~/.kube/config`).
    - *(Optional)* Configured AWS credentials (`~/.aws/credentials` and `~/.aws/config`) if using AWS tools.
- Required Python packages (see `agent_root/requirements.txt`):
    - `google-adk`
    - `kubernetes>=28.1.0`
    - `python-dateutil>=2.8.2`
    - `litellm>=1.63.11` (required for proprietary model integration)
    - `boto3==1.38.7` (required for AWS services and Bedrock models)
    - `ruff` (for formatting and linting)
    - `aiohttp>=3,<4`
    *(Add other necessary packages)*
- For development:
    - `pre-commit` (for running pre-commit hooks)

## Installation (Local Development - Optional)

While running via Docker is recommended, you can set up a local environment:

1.  Clone this repository:
    ```bash
    # Replace with your actual repository URL
    git clone https://github.com/your-username/sre-bot.git
    cd sre-bot
    ```
2.  Create a virtual environment and activate it:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3.  Install the required dependencies:
    ```bash
    pip install -r agent_root/requirements.txt
    ```

4.  For development, install additional dependencies:
    ```bash
    pip install -r requirements-dev.txt
    ```

5.  Set up pre-commit hooks:
    ```bash
    pre-commit install
    ```

6.  Set up your Google API key:
    ```bash
    export GOOGLE_API_KEY="your-api-key"
    ```

7.  Ensure `kubectl` is configured correctly and any necessary AWS profiles are set up.

## Usage (Docker Recommended)

### Running with Docker

The application is designed to run using Docker and Docker Compose, simplifying dependency management and environment setup.

1. Set required environment variables:
    ```bash
    # Mandatory
    export GOOGLE_API_KEY="your-api-key"
    
    # Optional: For Anthropic Claude model access
    export ANTHROPIC_API_KEY="your-anthropic-api-key"

    # Optional: Specify the Kubernetes context to use (if different from default)
    # Note: The application code must explicitly use this variable.
    export KUBE_CONTEXT="your-kube-context-name"

    # Optional: Specify the AWS profile to use (if using AWS tools)
    # Note: The application code must explicitly use this variable or AWS SDK defaults apply.
    export AWS_PROFILE="your-aws-profile-name"
    ```

2. Build and start the container(s):
    ```bash
    docker-compose build
    docker-compose up -d
    ```
    This will start the `sre-bot` service (web interface) by default.

3. Access the web interface at `http://localhost:8000`. The application name identified by ADK might correspond to the `agent_root` directory.

4. The `docker-compose.yml` file mounts:
    - `~/.kube` to `/home/root/.kube` (read-only) inside the container, allowing `kubectl` access. The `KUBECONFIG` environment variable inside the container is set to `/home/root/.kube/config`.
    - `~/.aws` to `/home/root/.aws` (read-only) inside the container, allowing AWS tool access.

5. To stop the containers:
    ```bash
    docker-compose down
    ```

6. To run the API server instead of the web UI:
    ```bash
    # Ensure the 'sre-bot-api' service is defined in docker-compose.yml
    docker-compose up -d sre-bot-api
    ```
    The API will be accessible at `http://localhost:8001`. Refer to ADK documentation or the previous `Usage` section for example `curl` commands (adjusting the app name path if necessary, e.g., `/apps/agent_root/...`).


To run the agent in API mode, use the following command:

```bash
adk api
```

To test the agent in API mode, use the following command first create a new session by issuing the following command:

```
curl -X POST http://0.0.0.0:8001/apps/agent_root/users/u_123/sessions/s_123 -H "Content-Type: application/json" -d '{"state": {"key1": "value1", "key2": 42}}'
```
Followed by issuing the following command to send a message to the agent:

```
curl -X POST http://0.0.0.0:8001/run \
-H "Content-Type: application/json" \
-d '{
"app_name": "agent_root",
"user_id": "u_123",
"session_id": "s_123",
"new_message": {
    "role": "user",
    "parts": [{
    "text": "How many pods are running in the default namespace?"
    }]
}
}'
```

### Running the Slack Bot

The repository also includes a Slack bot integration that allows users to interact with the agent directly from Slack:

1. Ensure you have set up the Slack app as described in the "Creating the Slack app" section below.

2. Configure the `.env` file in the `slack_bot` directory with your Slack credentials:
   ```
   SLACK_BOT_TOKEN=xoxb-your-token
   SLACK_SIGNING_SECRET=your-signing-secret
   BOT_PREFIX=your-bot-name
   ```

3. Start the Slack bot container:
   ```bash
   docker-compose up -d slack-bot
   ```

4. The Slack bot will be accessible at `http://localhost:8002`.

5. For external access, set up ngrok as described in the Setup section.

### Troubleshooting

If you encounter communication timeouts between services (for example, between slack-bot and sre-bot-api):

1. Check that all containers are running:
   ```bash
   docker-compose ps
   ```
   
2. Verify the network connectivity between containers:
   ```bash
   docker network inspect $(docker network ls --filter name=sre-bot --format "{{.Name}}")
   ```

3. Check the logs for specific containers:
   ```bash
   docker-compose logs slack-bot
   docker-compose logs sre-bot-api
   ```

4. Ensure the API endpoints are correctly configured in the Slack bot code.

### Running Locally (If Installation steps were followed)

You might be able to run the agent locally using the ADK CLI. The application name might be derived from the directory structure (`agent_root`).

```bash
# From the project root directory
adk web agent_root
# or potentially
adk web
```

*Local execution might be less reliable due to potential path and discovery issues experienced previously.*

## Code Formatting and Linting (Ruff)

This project uses Ruff for code formatting and linting (following PEP 8).

1. Ensure Ruff is installed (via `pip install -r requirements-dev.txt`).
2. Check for issues:
   ```bash
   ruff check .
   ```
3. Format code:
   ```bash
   ruff format .
   ```
4. Check and automatically fix issues:
   ```bash
   ruff check . --fix
   ```

Run these commands from the project's root directory. Configuration is in `pyproject.toml`.

### Pre-commit Hooks

This project uses pre-commit hooks to ensure code quality before committing changes. The hooks are configured in `.pre-commit-config.yaml`.

1. Install pre-commit if you haven't already:
   ```bash
   pip install pre-commit
   ```

2. Set up the hooks:
   ```bash
   pre-commit install
   ```

3. The hooks will automatically run when you commit changes. Currently, the hooks include:
   - Ruff format: automatically formats your code
   - Ruff linting: checks for code issues and fixes them when possible

4. To run the hooks manually on all files:
   ```bash
   pre-commit run --all-files
   ```

5. To run a specific hook:
   ```bash
   pre-commit run ruff-format
   ```

## Structure

- `agents/`
  - `sre_agent/`
    - `agent.py`: Contains the main SRE agent logic (ADK application definition, `root_agent`) and initialization of sub-agents.
    - `kube_agent.py`: Defines the Kubernetes sub-agent and its tools.
    - `aws_mcps.py`: (Assumed location) Defines the AWS Core MCP and AWS Cost Analysis MCP agents/tools.
    - `aws_cost_agent.py`: (Assumed location) Defines the specialized AWS Cost Agent.
    - `settings.py`: Configuration settings (e.g., `DB_URL`).
    - `json_utils.py`: Custom JSON utilities.
    - `__init__.py`
  - `__init__.py`
- `slack_bot/`
  - `main.py`: The main Slack bot implementation.
  - `modules/`: Helper modules for the Slack bot (e.g., `health.py`).
  - `requirements.txt`: Python dependencies for the Slack bot.
  - `Dockerfile`: Instructions for building the Slack bot container.
  - `.env.example`: Example environment variables for the Slack bot.
- `docker-compose.yml`: Docker Compose configuration for running services.
- `Dockerfile`: Instructions for building the SRE Bot API Docker image.
- `requirements-dev.txt`: Development-specific Python dependencies.
- `pyproject.toml`: Configuration for Ruff (linting/formatting) and other Python tools.
- `.pre-commit-config.yaml`: Configuration for pre-commit hooks.
- `.gitignore`: Specifies intentionally untracked files that Git should ignore.
- `README.md`: This documentation file.

## Available Functions and Capabilities

### Kubernetes Tools

The following functions are defined in `agents/sre_agent/kube_agent.py` (or similar) and are available via the `kubernetes_agent`:

- `list_namespaces()`
- `list_deployments_from_namespace(namespace: str)`
- `list_deployments_all_namespaces()`
- `list_pods_from_namespace(namespace: str)`
- `list_pods_all_namespaces()`
- `list_services_from_namespace(namespace: str)`
- `list_secrets_from_namespace(namespace: str)`
- `list_daemonsets_from_namespace(namespace: str)`
- `list_configmaps_from_namespace(namespace: str)`
- `list_all_resources(namespace: str)`
- `get_deployment_details(namespace: str, deployment_name: str)`
- `get_pod_details(namespace: str, pod_name: str)`
- `scale_deployment(namespace: str, deployment_name: str, replicas: int)`
- `get_pod_logs(namespace: str, pod_name: str, tail_lines: int = 50)`
- `get_resource_health(namespace: str, resource_type: str, resource_name: str)`
- `get_events(namespace: str)`
- `get_events_all_namespaces()`

### AWS Core MCP Capabilities (Illustrative)

*(Tools provided by the `aws_core_mcp_agent` for interacting with various AWS services. Specific functions will be listed here as they are developed and exposed. Examples might include interacting with EC2, S3, IAM, etc.)*

### AWS Cost Analysis MCP & Agent Capabilities (Illustrative)

*(Tools and capabilities provided by the `aws_cost_analysis_mcp_agent` and the `aws_cost_agent` for querying AWS cost and usage, generating reports, and providing cost optimization insights. Specific functions/capabilities will be listed here, e.g., `get_monthly_cost_summary`, `analyze_service_costs_by_tag`.)*

# Creating the Slack app:
1. Go to https://api.slack.com/apps and click Create New App
2. Name it and choose a workspace
3. Add Scopes
    - Go to OAuth & Permissions
    - Under Bot Token Scopes, add permissions. For this app, we at least need `app_mentions:read`, which allows our app to view messages that directly mention our bot, and `chat:write`, which allows our app to send messages
4. Scroll to the top of the OAuth & Permissions page and click Install App to Workspace
5. App needs to be approved by workspace owner.


Example app manifest:

```yaml
display_information:
  name: sre-bot
features:
  bot_user:
    display_name: sre-bot
    always_online: false
  slash_commands:
    - command: /sre-bot:scale
      url: http://<ngrok-url>.ngrok-free.app/slack/events
      description: "sre-bot scale "
      should_escape: false
oauth_config:
  scopes:
    user:
      - reactions:read
    bot:
      - app_mentions:read
      - channels:join
      - channels:history
      - chat:write
      - chat:write.customize
      - commands
      - groups:history
      - im:write
      - chat:write.public
      - reactions:read
      - mpim:history
      - im:history
settings:
  event_subscriptions:
    request_url: http://<ngrok-url>.ngrok-free.app/slack/events
    bot_events:
      - reaction_added
  interactivity:
    is_enabled: true
    request_url: http://<ngrok-url>.ngrok-free.app/slack/events
  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false


```

# Setup

Install [ngrok](https://ngrok.com)

Start the application via docker-compose while inside the app folder.
`docker compose up`

Port exposed locally is port 80 so we will have ngrok point to that port

`ngrok http 80`

## Security Note

This agent may require access to sensitive systems and data (Kubernetes cluster, potentially AWS). Ensure that:
1.  Appropriate credentials and API keys are securely managed (e.g., using environment variables like `GOOGLE_API_KEY`, relying on mounted `~/.kube/config` and `~/.aws/credentials`).
2.  The principle of least privilege is followed – the agent should only have the permissions necessary to perform its defined tasks within Kubernetes and/or AWS.
3.  Network access and configurations are secure.
4.  Audit logs are reviewed periodically.

## Session and User ID Management

This system handles user sessions and IDs differently depending on how users interact with the SRE Bot. All session data is ultimately stored in the PostgreSQL database configured for the `sre-agent`.

### 1. Interactions via Slack

When a user interacts with the SRE Bot through Slack:

1.  **Initial Message**: The `slack_bot` (specifically `slack_bot/main.py`) receives the message.
2.  **Session Creation (Slack Bot Side)**:
    *   The `SessionManager` in `slack_bot/main.py` creates or retrieves a `ConversationSession`.
    *   A `user_id` is generated uniquely for the Slack user (e.g., `u_{slack_user_id}`).
    *   A `session_id` is generated based on the Slack channel and thread timestamp (e.g., `s_{channel_id}_{thread_ts_or_timestamp}`). This ensures conversation continuity within Slack threads.
3.  **API Session Creation (SRE Agent)**:
    *   Before processing the user's query, the `slack_bot` makes a `POST` request to an endpoint like `http://sre-bot-api:8000/apps/sre_agent/users/{session.user_id}/sessions/{session.session_id}`.
    *   This request explicitly creates a session record in the PostgreSQL database via the `DatabaseSessionService` in `agents/sre_agent/agent.py`. The payload includes an initial state containing Slack-specific context (channel, thread, Slack user).
    *   If the session already exists in the database, this step confirms its availability.
4.  **Query Processing**:
    *   The `slack_bot` then sends the user's message to the `http://sre-bot-api:8000/run` endpoint.
    *   The payload to this `/run` endpoint includes:
        *   `app_name`: "sre_agent"
        *   `user_id`: The `user_id` generated by the Slack bot (e.g., `u_{slack_user_id}`).
        *   `session_id`: The `session_id` generated by the Slack bot (e.g., `s_{channel_id}_{thread_ts_or_timestamp}`).
        *   `new_message`: The user's query.
5.  **SRE Agent Processing (ADK)**:
    *   The ADK framework powering `agents/sre_agent/agent.py` receives these parameters.
    *   The `DatabaseSessionService` uses the `app_name`, `user_id`, and `session_id` *provided in the API request* to load the relevant session data from the database for this interaction. Any state changes or conversation history updates are saved back to this specific session record.

### 2. Interactions via Local Web UI / Direct API Calls

When interacting with the SRE Bot locally (e.g., through a development Web UI or direct API calls, not via the Slack bot):

1.  **API Request**: The client (Web UI or tool) is expected to make requests to the SRE Bot API (e.g., the `/run` endpoint).
    *   **Recommended**: The client should manage its own user and session identifiers and include `app_name`, `user_id`, and `session_id` in the API payload, similar to how the Slack bot does.
        *   If these are provided, the `DatabaseSessionService` in `agents/sre_agent/agent.py` will use them to create or retrieve the session from the database. The client would also be responsible for an initial call to create the session if it doesn't exist (e.g., `/apps/{app_name}/users/{user_id}/sessions/{session_id}`).
    *   **Fallback / `agent.py` Direct Execution**:
        *   If `agents/sre_agent/agent.py` is run directly (e.g., `python agents/sre_agent/agent.py` which triggers the `if __name__ == "__main__":` block) or if an API call to `/run` somehow doesn't provide specific user/session IDs and the system falls back to defaults within `get_or_create_session`:
            *   The default `APP_NAME = "sre_agent"` and `USER_ID = "test_user"` defined at the top of `agents/sre_agent/agent.py` are used.
            *   The `get_or_create_session()` function in `agents/sre_agent/agent.py` is invoked.
            *   It uses these default `APP_NAME` and `USER_ID` with the `DatabaseSessionService`.
            *   If no session exists in the database for this default `APP_NAME`/`USER_ID`, a new session is created with a new UUID-based `session_id` automatically generated by the `DatabaseSessionService`. The initial state is generic.
            *   Subsequent interactions using these defaults will reuse this session.

In essence, the `user_id` and `session_id` from the API request payload take precedence. The defaults in `agents/sre_agent/agent.py` are primarily for scenarios where the script is run in a context that doesn't involve an incoming API request with these parameters (like direct script execution or certain ADK CLI interactions).
