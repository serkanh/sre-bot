# SRE Assistant Agent

A powerful Site Reliability Engineering (SRE) assistant built with Google's Agent Development Kit (ADK), featuring specialized agents for AWS cost analysis, Kubernetes operations, and operational best practices.

![Cost Reporting Demo](https://github.com/serkanh/static-files/blob/main/gifs/cost-reporting-demo.gif?raw=true)

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- AI Provider API key (see [AI Model Configuration](#-ai-model-configuration) below)
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

Edit `agents/.env` with your AI provider credentials (see [AI Model Configuration](#-ai-model-configuration) for details):

```bash
# Option 1: Google Gemini (Recommended)
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_AI_MODEL=gemini-2.0-flash  # optional

# Option 2: Anthropic Claude
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-20240620  # optional

# Option 3: AWS Bedrock (requires AWS credentials)
BEDROCK_INFERENCE_PROFILE=arn:aws:bedrock:us-west-2:812201244513:inference-profile/us.anthropic.claude-opus-4-1-20250805-v1:0

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

The SRE bot follows a modular architecture with specialized sub-agents:

```
agents/sre_agent/
├── agent.py              # Main SRE agent orchestrator
├── serve.py              # FastAPI server with health checks
├── utils.py              # Shared utilities
└── sub_agents/
    └── aws_cost/         # AWS cost analysis module
        ├── agent.py      # Agent configuration
        ├── tools/        # Cost analysis tools
        └── prompts/      # Agent instructions
```

## 🛠️ Features

### AWS Cost Analysis

- Retrieve and analyze AWS cost data for specific time periods
- Filter costs by services, tags, or accounts
- Calculate cost trends over time
- Provide average daily costs (including or excluding weekends)
- Identify the most expensive AWS accounts
- Compare costs across different time periods
- Generate cost optimization recommendations

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

## 🤖 AI Model Configuration

The SRE bot supports multiple AI providers with automatic provider detection based on your environment variables. The system checks for API keys in priority order and configures the appropriate model.

### Supported Providers

#### 1. Google Gemini (Recommended)

**Best for**: Google Cloud users, fastest setup, most reliable

```bash
# Required
GOOGLE_API_KEY=your_google_api_key_here

# Optional (defaults shown)
GOOGLE_AI_MODEL=gemini-2.0-flash
```

**Get API Key**: [Google AI Studio](https://aistudio.google.com/apikey)

#### 2. Anthropic Claude

**Best for**: Advanced reasoning tasks, detailed analysis

```bash
# Required
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional (defaults shown)
ANTHROPIC_MODEL=claude-3-5-sonnet-20240620
```

**Get API Key**: [Anthropic Console](https://console.anthropic.com/)

#### 3. AWS Bedrock

**Best for**: AWS-native deployments, enterprise compliance

```bash
# Required
BEDROCK_INFERENCE_PROFILE=arn:aws:bedrock:us-west-2:812201244513:inference-profile/us.anthropic.claude-opus-4-1-20250805-v1:0

# AWS credentials also required (one of the following):
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
# OR
AWS_PROFILE=your_aws_profile
```

**Setup**: Configure AWS Bedrock access in your AWS account

### Provider Selection Priority

The system automatically selects providers in this order:

1. **Google Gemini** (if `GOOGLE_API_KEY` is set)
2. **Anthropic Claude** (if `ANTHROPIC_API_KEY` is set)
3. **AWS Bedrock** (if `BEDROCK_INFERENCE_PROFILE` is set)

### Configuration Examples

#### Minimal Google Setup
```bash
# agents/.env
GOOGLE_API_KEY=AIzaSyD4R5T6Y7U8I9O0P1A2S3D4F5G6H7J8K9L0
```

#### Anthropic with Custom Model
```bash
# agents/.env
ANTHROPIC_API_KEY=sk-ant-api03-A1B2C3D4E5F6G7H8I9J0
ANTHROPIC_MODEL=claude-3-opus-20240229
```

#### Bedrock with Named Profile
```bash
# agents/.env
BEDROCK_INFERENCE_PROFILE=arn:aws:bedrock:us-east-1:123456789012:inference-profile/us.anthropic.claude-3-5-sonnet-20240620-v1:0
AWS_PROFILE=bedrock-user
AWS_REGION=us-east-1
```

### Troubleshooting AI Configuration

#### No Provider Configured
```
ERROR: No AI provider configured!
Please configure one of the following providers...
```
**Solution**: Set at least one API key as shown above.

#### AWS Bedrock Credentials Missing
```
ERROR: BEDROCK_INFERENCE_PROFILE is set but AWS credentials are not configured
```
**Solution**: Configure AWS credentials via environment variables or AWS profiles.

#### Invalid API Key
```
ERROR: Authentication failed with provider
```
**Solution**: Verify your API key is correct and has necessary permissions.

### Model Recommendations

| Use Case | Recommended Provider | Model | Why |
|----------|---------------------|--------|------|
| General SRE Tasks | Google Gemini | `gemini-2.0-flash` | Fast, reliable, good for operations |
| Complex Analysis | Anthropic Claude | `claude-3-5-sonnet-20240620` | Superior reasoning for complex problems |
| Enterprise/AWS | AWS Bedrock | `claude-3-opus-*` | Enterprise compliance, AWS integration |
| Cost-Sensitive | Google Gemini | `gemini-2.0-flash` | Most cost-effective for high-volume usage |

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

3. **AI Model Configuration Issues**:

   ```bash
   docker compose logs sre-bot-api | grep -E "(ERROR|model|provider)"
   ```

   **Common errors**:
   - `No AI provider configured!` → Set at least one API key
   - `Bedrock requires valid AWS credentials` → Configure AWS access
   - `Authentication failed` → Verify API key is valid
   - See [AI Model Configuration](#-ai-model-configuration) for detailed setup

### Health Checks

```bash
# Check overall health
curl http://localhost:8000/health

# Kubernetes readiness/liveness probes
curl http://localhost:8000/health/readiness
curl http://localhost:8000/health/liveness
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
