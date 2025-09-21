# CLAUDE.md

### 🔄 Project Awareness & Context

- **Always read `PLANNING.md`** at the start of a new conversation to understand the project's architecture, goals, style, and constraints.
- **Check `TASK.md`** before starting a new task. If the task isn’t listed, add it with a brief description and today's date.
- **Use consistent naming conventions, file structure, and architecture patterns** as described in `PLANNING.md`.
- **Use venv_linux** (the virtual environment) whenever executing Python commands, including for unit tests.

### 🧱 Code Structure & Modularity

- **Never create a file longer than 500 lines of code.** If a file approaches this limit, refactor by splitting it into modules or helper files.
- **Organize code into clearly separated modules**, grouped by feature or responsibility.
  For agents this looks like:
  - `agent.py` - Main agent definition and execution logic
  - `tools.py` - Tool functions used by the agent
  - `prompts.py` - System prompts
- **Use clear, consistent imports** (prefer relative imports within packages).
- **Use clear, consistent imports** (prefer relative imports within packages).
- **Use python_dotenv and load_env()** for environment variables.

### 🧪 Testing & Reliability

- **Always create Pytest unit tests for new features** (functions, classes, routes, etc).
- **After updating any logic**, check whether existing unit tests need to be updated. If so, do it.
- **Tests should live in a `/tests` folder** mirroring the main app structure.
  - Include at least:
    - 1 test for expected use
    - 1 edge case
    - 1 failure case

### ✅ Task Completion

- **Mark completed tasks in `TASK.md`** immediately after finishing them.
- Add new sub-tasks or TODOs discovered during development to `TASK.md` under a “Discovered During Work” section.

### 📎 Style & Conventions

- **Use Python** as the primary language.
- **Follow PEP8**, use type hints, and format with `black`.
- **Use `pydantic` for data validation**.
- Use `FastAPI` for APIs and `SQLAlchemy` or `SQLModel` for ORM if applicable.
- Write **docstrings for every function** using the Google style:

  ```python
  def example():
      """
      Brief summary.

      Args:
          param1 (type): Description.

      Returns:
          type: Description.
      """
  ```

### 📚 Documentation & Explainability

- **Update `README.md`** when new features are added, dependencies change, or setup steps are modified.
- **Comment non-obvious code** and ensure everything is understandable to a mid-level developer.
- When writing complex logic, **add an inline `# Reason:` comment** explaining the why, not just the what.

### 🧠 AI Behavior Rules

- **Never assume missing context. Ask questions if uncertain.**
- **Never hallucinate libraries or functions** – only use known, verified Python packages.
- **Always confirm file paths and module names** exist before referencing them in code or tests.
- **Never delete or overwrite existing code** unless explicitly instructed to or if part of a task from `TASK.md`.

## Project Overview

This is an SRE Assistant Agent built with Google's Agent Development Kit (ADK) for helping Site Reliability Engineers with operational tasks, particularly focused AWS interactions. The system includes a web interface, API, and Slack bot integration.

## Development Commands

### Docker (Recommended)

```bash
# Build and start all services
docker-compose build
docker-compose up -d

# Start specific services
docker-compose up -d sre-bot-web    # Web interface on port 8000
docker-compose up -d sre-bot-api    # API server on port 8001
docker-compose up -d slack-bot      # Slack bot on port 8002

# View logs
docker-compose logs [service-name]

# Stop services
docker-compose down
```

### Code Quality

```bash
# Run linting and formatting
ruff check .
ruff format .
ruff check . --fix

# Run pre-commit hooks manually
pre-commit run --all-files
pre-commit run ruff-format
```

### Local Development (Optional)

**For Bot Testing and Development:**

```bash
# Install dependencies
pip install -r agents/sre_agent/requirements.txt
pip install -r requirements-dev.txt

# Use built-in ADK web interface for rapid bot testing
adk web --session_service_uri=postgresql://postgres:password@localhost:5432/srebot
```

**For API Server Development:**

```bash
# Use custom serve.py for API-only development with health checks
cd agents/sre_agent
python serve.py
```

## Architecture

### Core Components

**agents/sre_agent/**: Main ADK agent implementation

- `serve.py`: FastAPI server with health checks and session management
- `agent.py`: Clean agent definition and orchestration
- `sub_agents/`: Modular sub-agent implementations
  - `aws_cost/`: AWS cost analysis sub-agent
    - `agent.py`: Agent configuration and initialization
    - `tools/`: AWS cost analysis tools
    - `prompts/`: Agent-specific prompts and instructions
- `tools/`: Shared tool implementations
- `utils.py`: Utility functions
- `settings.py`: Configuration settings

**slack_bot/**: Slack integration

- `main.py`: FastAPI-based Slack bot with session management
- Communicates with SRE agent API for processing queries

### Google ADK Best Practices

This project follows Google ADK's latest patterns and best practices:

**Agent Configuration**:

- Uses `LlmAgent` (aliased as `Agent`) with declarative Python configuration
- Each agent has: `name`, `model`, `instruction`, `description`, and `tools`
- Model-agnostic design supporting Gemini, Claude, GPT-4o, and other models via LiteLlm

**Multi-Agent System (MAS)**:

- Structured parent-child relationships with `sub_agents`
- Specialized workflow agents (`SequentialAgent`, `ParallelAgent`, `LoopAgent`)
- Modularity through composition of smaller, specialized agents

**Tool Integration**:

- Tools as Python functions or `BaseTool` classes
- Custom toolsets like `BigQueryToolset` and `VertexAiSearchTool`
- `AgentTool` for delegating to other agents

**Session & State Management**:

- `Session` holds conversation history for continuous dialogue
- `State` acts as scratchpad for data sharing between steps
- `Memory` provides long-term recall across sessions
- Callbacks for dynamic state management via `callback_context.state`

**Code Reuse & Duplication Prevention**:

- Before implementing utility functions, check if similar functionality exists in `agents/sre_agent/utils.py`
- Always prefer using shared utilities over duplicating code across modules
- When creating commonly-needed functions (like file loading, formatting, etc.), add them to the shared utils module
- Example: Use `load_instruction_from_file()` from utils for loading agent prompts from markdown files
- If you find duplicated code patterns, refactor them into shared utilities immediately

**Logging Standards**:

- **Always use shared logging utilities** from `agents/sre_agent/utils` instead of configuring logging directly
- **Standard usage**: `from agents.sre_agent.utils import get_logger` then `logger = get_logger(__name__)`
- **Custom configuration**: Use `setup_logger()` for modules requiring specific log formats or levels
- **Environment control**: Use `LOG_LEVEL` environment variable (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Consistent format**: Shared utilities provide standardized timestamp and module name formatting
- **Examples**:

  ```python
  # Basic logging (recommended for most modules)
  from agents.sre_agent.utils import get_logger
  logger = get_logger(__name__)

  # Custom logging (for servers or special requirements)
  from agents.sre_agent.utils import setup_logger
  logger = setup_logger("SERVICE_NAME", format_string="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
  ```

- **Never use**: `logging.basicConfig()` or `logging.getLogger()` directly in new code

### Slack Bolt Framework Integration

Built using Slack Bolt's async patterns:

**AsyncApp Configuration**:

```python
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

app = AsyncApp(
    signing_secret="your_signing_secret",
    token="your_bot_token"
)

@app.event("app_mention")
async def handle_app_mention(body, say):
    await say("Hello!")
```

**FastAPI Integration**:

- Uses `AsyncSlackRequestHandler` to bridge FastAPI and Bolt
- Async event handling with `@app.event` decorators
- Proper `await` usage for all utility functions (`ack()`, `say()`, `respond()`)

### Session Management Architecture

The system uses different session management approaches:

1. **Slack Interactions**:
   - SessionManager in `slack_bot/main.py` creates sessions with IDs like `u_{slack_user_id}` and `s_{channel_id}_{thread_ts}`
   - Makes API calls to create/retrieve sessions in PostgreSQL via DatabaseSessionService
   - Ensures conversation continuity within Slack threads
   - Follows Slack Bolt's OAuth installation patterns with `AsyncInstallationStore`

2. **Direct API/Web UI**:
   - Uses DatabaseSessionService in `agents/sre_agent/agent.py`
   - Defaults to `APP_NAME="sre_agent"`, `USER_ID="test_user"` if not specified
   - Session data persisted in PostgreSQL database
   - ADK's `Session`, `State`, and `Memory` abstractions

### Agent Architecture

The main agent (`agents/sre_agent/agent.py`) orchestrates multiple specialized sub-agents following ADK's MAS patterns:

- **aws_core_mcp_agent**: General AWS service interactions via MCP
- **aws_cost_analysis_mcp_agent**: AWS cost querying and analysis
- **aws_cost_agent**: Specialized cost analysis sub-agent with dedicated tools

## Environment Configuration

The SRE Bot uses service-specific environment files for better organization and security isolation:

### Environment Files Structure

```
.env.example                    # Main Docker Compose configuration
agents/.env.example            # SRE Agent specific configuration
slack_bot/.env.example         # Slack Bot specific configuration
```

### Main Configuration (.env.example)

- `POSTGRES_PASSWORD`: Database password
- `LOG_LEVEL`: Global logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`: AI model access keys
- `AWS_PROFILE`, `KUBE_CONTEXT`: Infrastructure tool configurations

### SRE Agent Configuration (agents/.env.example)

- AI model API keys with service isolation
- Database connection settings
- Custom logging formats for agent operations
- Server configuration (PORT, ADK_UI_ENABLED)

### Slack Bot Configuration (slack_bot/.env.example)

- Slack app tokens and secrets
- SRE Agent API endpoint configuration
- Session management settings
- Health check intervals

### Setup Instructions

1. Copy each `.env.example` file to `.env` in the same directory
2. Customize values according to your environment
3. Use separate credentials for production vs development
4. Never commit actual `.env` files to version control

## Database

PostgreSQL database for session persistence:

- Host: postgres (in Docker), localhost (local)
- Database: srebot
- User: postgres
- Tables managed by DatabaseSessionService

## AWS Integration

AWS capabilities through MCP agents:

- Core AWS service interactions
- Cost analysis and reporting
- Usage optimization insights

## Docker Configuration

**Production/Containerized Setup:**

- **sre-bot-web**: Web interface using `adk web` with built-in UI (for testing)
- **sre-bot-api**: API-only server using custom `serve.py` (for Slack app integration)
- **slack-bot**: FastAPI Slack integration communicates with sre-bot-api
- **postgres**: Session data persistence

### API Server (serve.py) Features

The custom `serve.py` provides production-ready API server with:

**Health Checks for Monitoring:**

- `/health` - General health check with system info
- `/health/readiness` - Kubernetes readiness probe
- `/health/liveness` - Kubernetes liveness probe

**Production Features:**

- Request logging middleware for debugging
- PostgreSQL session management
- Environment-based configuration
- Optimized for API-only usage (no UI overhead)

**Environment Variables:**

- `PORT`: Server port (default: 8000)
- Database: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

### Development Workflow

- **Local Bot Testing**: Use `adk web` for rapid development with built-in UI
- **API Development**: Use `serve.py` for API-only server features and health checks
- **Production**: Slack app talks to containerized `serve.py` API-only server

Mounts `~/.kube` and `~/.aws` for credential access.

## Slack Bot Setup

Requires Slack app configuration with:

- Bot scopes: `app_mentions:read`, `chat:write`, `channels:join`, etc.
- Event subscriptions pointing to ngrok/external URL
- Environment file at `slack_bot/.env` with tokens

## Agent Development Patterns

### Creating New Agents

Follow ADK's declarative approach for new agents:

```python
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

# Basic agent configuration
my_agent = Agent(
    name="my_specialized_agent",
    model="gemini-2.5-flash",  # or other supported models
    instruction="You are a specialized assistant for...",
    description="Brief description for other agents",
    tools=[tool1, tool2]  # List of tools/functions
)

# Multi-agent system with sub-agents
coordinator_agent = Agent(
    name="coordinator",
    model="gemini-2.5-flash",
    description="Coordinates multiple specialized agents",
    sub_agents=[my_agent, another_agent]
)
```

### Tool Development

Create tools as Python functions or BaseTool classes:

```python
# Function-based tool
async def my_custom_tool(parameter: str) -> str:
    """Tool description for the agent"""
    # Tool implementation
    return result

# Class-based tool
from google.adk.tools import BaseTool

class MyCustomTool(BaseTool):
    def __init__(self, config):
        self.config = config

    async def execute(self, **kwargs):
        # Tool implementation
        return result
```

### Slack Bot Integration Patterns

For new Slack event handlers:

```python
@app.event("message")
async def handle_message(body, say, logger):
    """Handle direct messages"""
    logger.info(f"Message received: {body}")
    # Process with SRE agent
    response = await send_to_sre_agent(body['text'])
    await say(response)

@app.command("/custom-command")
async def handle_custom_command(ack, body, respond):
    """Handle custom slash commands"""
    await ack()
    # Process command
    result = await process_command(body['text'])
    await respond(f"Result: {result}")
```

## Testing API

Create session:

```bash
curl -X POST http://localhost:8001/apps/sre_agent/users/u_123/sessions/s_123 \
  -H "Content-Type: application/json" \
  -d '{"state": {"key1": "value1"}}'
```

Send message:

```bash
curl -X POST http://localhost:8001/run \
  -H "Content-Type: application/json" \
  -d '{
    "app_name": "sre_agent",
    "user_id": "u_123",
    "session_id": "s_123",
    "new_message": {
      "role": "user",
      "parts": [{"text": "How many pods are running?"}]
    }
  }'
```

## Development Workflow

### Adding New Functionality

1. **Create Sub-Agent Module**:
   - Create directory: `agents/sre_agent/sub_agents/[agent_name]/`
   - Add subdirectories: `tools/`, `prompts/`
   - Create `agent.py` with agent configuration
   - Create `__init__.py` with exports

2. **Implement Tools**: Define tools in `sub_agents/[agent_name]/tools/`

3. **Create Prompts**: Add agent instructions in `sub_agents/[agent_name]/prompts/`

4. **Integrate**: Import and add to main agent in `agents/sre_agent/agent.py`

5. **Test**: Use API testing commands above

6. **Slack Integration**: Add handlers in `slack_bot/main.py` if needed

### Modular Sub-Agent Structure

Example structure for a new sub-agent:

```
agents/sre_agent/sub_agents/my_agent/
├── __init__.py              # Exports agent function
├── agent.py                 # Agent configuration and tools
├── tools/
│   ├── __init__.py          # Tool exports
│   └── my_tools.py          # Tool implementations
└── prompts/
    └── system_prompt.md     # Agent instructions
```

### Code Quality Checks

Always run before committing:

```bash
ruff check . --fix
ruff format .
pre-commit run --all-files
```

- 'use docker compose instead of deprecated docker-compose'
