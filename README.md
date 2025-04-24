# SRE Assistant Agent

A Google Agent Development Kit (ADK) powered assistant designed to help Site Reliability Engineers (SREs) with operational tasks and monitoring.

## Overview

This repository contains an SRE Assistant Agent built with Google's Agent Development Kit (ADK). It aims to assist SREs by automating common tasks, providing system insights, and streamlining incident response through natural language conversations. The agent leverages the Google Gemini model to understand user queries and interacts with various monitoring and operational tools via defined functions.

## Features (Potential - To be updated)

The SRE Assistant could potentially:

- []  Check the status of services and infrastructure components.
- Retrieve metrics from monitoring systems (e.g., Prometheus, Datadog).
- Fetch logs for specific services or applications.
- Provide summaries of ongoing alerts or incidents.
- Assist with deployment rollbacks or status checks.
- Manage on-call schedules or escalations (if integrated).
- Retrieve system configuration details.
- Perform health checks on demand.
- Answer questions based on runbooks or internal documentation.

*(Please update this section with the actual implemented features)*

## Prerequisites

- Python 3.10+
- Google API key for Gemini access (https://aistudio.google.com/apikey)
- Access credentials/configurations for any systems the bot needs to interact with (e.g., monitoring APIs, cloud providers, incident management tools).
- Required Python packages (see `requirements.txt`):
  - `google-adk`
  - `kubernetes>=28.1.0` *(If Kubernetes interaction is needed)*
  - `python-dateutil>=2.8.2` *(If date/time manipulation is needed)*
  *(Add other necessary packages)*

## Installation

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
    pip install -r requirements.txt
    ```

4.  Set up your Google API key:
    ```bash
    export GOOGLE_API_KEY="your-api-key"
    ```

5.  Ensure any necessary configurations for target systems (monitoring, cloud, etc.) are properly set up and accessible by the environment where the agent runs.

## Usage

Run the agent using the following command for a web interface:

```bash
# Assuming 'sre' is your app name defined in the ADK setup
adk web --app-name sre
```

This will start the agent in web mode, typically accessible at `http://localhost:8000`.

To run the agent in API mode:

```bash
# Assuming 'sre' is your app name defined in the ADK setup
adk api --app-name sre
```

To test the agent in API mode, first create a new session:

```bash
# Replace 'sre' if your app name is different
curl -X POST http://0.0.0.0:8000/apps/sre/users/u_123/sessions/s_123 -H "Content-Type: application/json" -d '{"state": {"example_key": "example_value"}}'
```

Then, send a message to the agent:

```bash
# Replace 'sre' if your app name is different
curl -X POST http://0.0.0.0:8000/apps/sre/users/u_123/sessions/s_123/messages -H "Content-Type: application/json" -d '{"message": "What is the status of the login service?"}'
```

## Structure (Assumed - Please update)

- `sre/`
  - `agent.py`: Contains the main agent logic (ADK application).
  - `tools/`
    - `__init__.py`
    - `tools.py`: Contains functions for interacting with external systems (monitoring, logging, etc.).
  - `__init__.py`: Package initialization file.
- `requirements.txt`: Lists all required Python packages.
- `.gitignore`: Specifies intentionally untracked files that Git should ignore.
- `README.md`: This documentation file.

## Available Functions (Potential - To be updated)

*(List the actual functions implemented in `sre/tools/tools.py` once defined)*

### Monitoring & Health Checks
- `get_service_status(service_name)`
- `get_system_metrics(metric_query, time_range)`
- `check_endpoint_health(url)`

### Logging
- `get_service_logs(service_name, time_range, filter_pattern=None)`

### Incident Management
- `get_active_alerts()`
- `acknowledge_alert(alert_id)`

### Deployment
- `get_deployment_status(deployment_name, environment)`

*(Add detailed descriptions for each function)*

## Security Note

This agent may require access to sensitive systems and data. Ensure that:
1.  Appropriate credentials and API keys are securely managed (e.g., using environment variables, secrets management tools).
2.  The principle of least privilege is followed – the agent should only have the permissions necessary to perform its defined tasks.
3.  Network access and configurations are secure.
4.  Audit logs are reviewed periodically. 
