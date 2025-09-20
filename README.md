# SRE Assistant Agent

A powerful Site Reliability Engineering (SRE) assistant built with Google's Agent Development Kit (ADK), featuring specialized agents for AWS cost analysis, Kubernetes operations, and operational best practices.

![Cost Reporting Demo](https://github.com/serkanh/static-files/blob/main/gifs/cost-reporting-demo.gif?raw=true)

![Kubernetes Demo](https://github.com/serkanh/static-files/blob/main/gifs/eks-cluster-demo.gif?raw=true)

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Google API key for Gemini access ([Get one here](https://aistudio.google.com/apikey))
- (Optional) AWS credentials and Kubernetes config for respective features

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd sre-bot

# Copy environment files and customize
cp .env.example .env
cp agents/.env.example agents/.env
cp slack_bot/.env.example slack_bot/.env
```

### 2. Configure Environment

Edit `.env` and `agents/.env` with your settings:

```bash
# Required: Google API key for Gemini models
GOOGLE_API_KEY=your_google_api_key_here

# AI Model Configuration (default: gemini-2.0-flash)
GOOGLE_AI_MODEL=gemini-2.0-flash

# Optional: AWS and Kubernetes configurations
AWS_PROFILE=your_aws_profile
KUBE_CONTEXT=your_kube_context
```

### 3. Start the Agent

```bash
# Build and start all services
docker compose build
docker compose up -d

# Check if services are running
docker compose ps
```

### 4. Access the Interface

- **Web Interface**: <http://localhost:8000>
- **API Server**: <http://localhost:8001>
- **Health Check**: <http://localhost:8000/health>

## 🏗️ Architecture

### Clean Modular Design

The SRE bot follows an ultra-clean, modular architecture:

```
agents/sre_agent/
├── agent.py              # Main SRE agent (50 lines - ultra-clean!)
├── serve.py              # FastAPI server with health checks
├── utils.py              # Shared utilities (logging, file loading)
└── sub_agents/
    └── aws_cost/         # Self-contained AWS cost analysis
        ├── agent.py      # AWS cost agent configuration
        ├── tools/        # AWS cost analysis tools
        └── prompts/      # Agent-specific instructions
```

### Multi-Agent System

- **Main SRE Agent**: Orchestrates and delegates to specialized sub-agents
- **AWS Cost Agent**: Dedicated AWS cost analysis and optimization
- **Environment-Driven**: Model selection via `GOOGLE_AI_MODEL` environment variable
- **Proper ADK Patterns**: Follows Google ADK best practices for sub-agent hierarchies

## 🛠️ Features

### AWS Cost Analysis

- Retrieve and analyze AWS cost data for specific time periods
- Filter costs by services, tags, or accounts
- Calculate cost trends over time
- Provide average daily costs (including or excluding weekends)
- Identify the most expensive AWS accounts
- Compare costs across different time periods
- Generate cost optimization recommendations

### Kubernetes Operations

- List and manage resources (Namespaces, Deployments, Pods, Services)
- Get detailed resource information
- Scale deployments
- Retrieve pod logs
- Monitor resource health
- Fetch cluster events

### Operational Excellence

- Infrastructure monitoring and troubleshooting
- Operational best practices and recommendations
- Performance optimization guidance
- Natural language interaction with technical systems

## 🔧 Development

### Code Quality

```bash
# Run linting and formatting
ruff check .
ruff format .
ruff check . --fix

# Run pre-commit hooks manually
pre-commit run --all-files
```

### Local Development (Optional)

For rapid development and testing:

```bash
# Install dependencies
pip install -r agents/sre_agent/requirements.txt
pip install -r requirements-dev.txt

# Use built-in ADK web interface for rapid bot testing
adk web --session_service_uri=postgresql://postgres:password@localhost:5432/srebot

# Or use custom serve.py for API-only development
cd agents/sre_agent
python serve.py
```

## 📊 Docker Services

### Available Services

- **sre-bot-web**: Web interface using ADK's built-in UI (port 8000)
- **sre-bot-api**: API-only server using custom `serve.py` (port 8001)
- **slack-bot**: Slack integration service (port 8002)
- **postgres**: PostgreSQL database for session persistence

### Service Management

```bash
# Start specific services
docker compose up -d sre-bot-web    # Web interface
docker compose up -d sre-bot-api    # API server
docker compose up -d slack-bot      # Slack bot

# View logs
docker compose logs [service-name]

# Stop services
docker compose down
```

## 🔌 API Usage

### Create a Session

```bash
curl -X POST http://localhost:8001/apps/sre_agent/users/u_123/sessions/s_123 \
  -H "Content-Type: application/json" \
  -d '{"state": {"key1": "value1"}}'
```

### Send a Message

```bash
curl -X POST http://localhost:8001/run \
  -H "Content-Type: application/json" \
  -d '{
    "app_name": "sre_agent",
    "user_id": "u_123",
    "session_id": "s_123",
    "new_message": {
      "role": "user",
      "parts": [{"text": "How many pods are running in the default namespace?"}]
    }
  }'
```

## 💬 Slack Integration

### Setup Slack Bot

1. **Configure Slack App** (see detailed instructions below)
2. **Set environment variables** in `slack_bot/.env`:

   ```bash
   SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
   SLACK_SIGNING_SECRET=your-slack-signing-secret
   SLACK_APP_TOKEN=xapp-your-slack-app-token
   ```

3. **Start the Slack bot**:

   ```bash
   docker compose up -d slack-bot
   ```

### Creating the Slack App

1. Go to <https://api.slack.com/apps> and click "Create New App"
2. Name it and choose a workspace
3. **Add Bot Token Scopes**:
   - `app_mentions:read` - View messages that mention the bot
   - `chat:write` - Send messages
   - `channels:join` - Join channels
   - `chat:write.public` - Send messages to channels the bot isn't in
4. **Install App to Workspace** and get approval if needed
5. **Set up Event Subscriptions** pointing to your ngrok URL
6. **Configure Slash Commands** if desired

### Example App Manifest

```yaml
display_information:
  name: sre-bot
features:
  bot_user:
    display_name: sre-bot
    always_online: false
oauth_config:
  scopes:
    bot:
      - app_mentions:read
      - channels:join
      - channels:history
      - chat:write
      - chat:write.public
      - commands
      - reactions:read
settings:
  event_subscriptions:
    request_url: https://your-ngrok-url.ngrok-free.app/slack/events
    bot_events:
      - app_mention
  org_deploy_enabled: false
  socket_mode_enabled: false
```

## 📁 Environment Configuration

### Service-Specific Environment Files

The SRE bot uses separate environment files for better organization:

- **`.env`**: Main Docker Compose configuration
- **`agents/.env`**: SRE Agent specific settings
- **`slack_bot/.env`**: Slack Bot configuration

### Key Environment Variables

```bash
# Main Configuration (.env)
GOOGLE_API_KEY=your_google_api_key
GOOGLE_AI_MODEL=gemini-2.0-flash
POSTGRES_PASSWORD=postgres
LOG_LEVEL=INFO

# Agent Configuration (agents/.env)
PORT=8000
DB_HOST=localhost
DB_PORT=5432

# Slack Bot Configuration (slack_bot/.env)
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_SIGNING_SECRET=your-secret
SRE_AGENT_API_URL=http://sre-bot-api:8001
```

## 🔒 Security

- Store sensitive credentials in environment variables
- Use separate credentials for production vs development
- Follow principle of least privilege for AWS and Kubernetes access
- Never commit actual `.env` files to version control
- Review audit logs periodically

## 🐛 Troubleshooting

### Common Issues

1. **Service Communication Issues**:

   ```bash
   docker compose ps                    # Check if all containers are running
   docker compose logs [service-name]  # Check specific service logs
   ```

2. **Database Connection Issues**:

   ```bash
   docker compose logs postgres         # Check PostgreSQL logs
   ```

3. **Model Configuration Issues**:
   - Verify `GOOGLE_API_KEY` is set correctly
   - Check `GOOGLE_AI_MODEL` is a valid Gemini model name
   - Review agent logs for model initialization errors

### Health Checks

```bash
# Check overall health
curl http://localhost:8000/health

# Kubernetes readiness/liveness probes
curl http://localhost:8000/health/readiness
curl http://localhost:8000/health/liveness
```

## 🧪 Testing

### Manual Testing

```bash
# Test AWS cost functionality (requires AWS credentials)
curl -X POST http://localhost:8001/run \
  -H "Content-Type: application/json" \
  -d '{
    "app_name": "sre_agent",
    "user_id": "test_user",
    "session_id": "test_session",
    "new_message": {
      "role": "user",
      "parts": [{"text": "What was my AWS cost last month?"}]
    }
  }'

# Test Kubernetes functionality (requires kubectl access)
curl -X POST http://localhost:8001/run \
  -H "Content-Type: application/json" \
  -d '{
    "app_name": "sre_agent",
    "user_id": "test_user",
    "session_id": "test_session",
    "new_message": {
      "role": "user",
      "parts": [{"text": "List all pods in the default namespace"}]
    }
  }'
```

## 📚 Available Tools and Functions

### AWS Cost Analysis Tools

- `get_cost_for_period` - Get costs for specific date ranges
- `get_monthly_cost` - Monthly cost summaries
- `get_cost_trend` - Cost trend analysis
- `get_cost_by_service` - Service-level cost breakdown
- `get_cost_by_tag` - Tag-based cost analysis
- `get_most_expensive_account` - Identify highest-cost accounts

## 🤝 Contributing

1. Follow the established code structure and patterns
2. Use shared utilities from `agents/sre_agent/utils.py`
3. Run code quality checks before committing:

   ```bash
   ruff check . --fix
   ruff format .
   pre-commit run --all-files
   ```

4. Test your changes with Docker Compose
5. Update documentation as needed

## 📄 License

[Add your license here]

---

**Need help?** Check the troubleshooting section above or review the service logs with `docker compose logs [service-name]`.
