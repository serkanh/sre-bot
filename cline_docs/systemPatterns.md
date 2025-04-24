# System Patterns for SRE Assistant Agent

## How the System is Built

The SRE Assistant Agent is built using a modular architecture with the following components:

1. **Agent Framework**: Uses Google's Agent Development Kit (ADK) to handle the conversational interface and natural language processing.

2. **Agent Hierarchy**:
   - `root_agent`: The entry point for all interactions
   - `sre_agent`: A LLM-based agent that handles general SRE queries
   - `kubernetes_agent`: A specialized agent for Kubernetes operations

3. **Tools System**: Functionality is organized into tool modules that implement specific operations:
   - `kube_tools.py`: Contains functions for interacting with Kubernetes clusters

4. **Utility Functions**: Common helper functions are organized in `utils.py`

## Key Technical Decisions

1. **Google ADK**: The project uses Google's Agent Development Kit for building the conversational agent, leveraging the Gemini model for natural language understanding.

2. **Kubernetes Client**: The official Kubernetes Python client is used for interacting with Kubernetes clusters, providing a reliable and well-maintained interface.

3. **Modular Tool Design**: Tools are organized into separate modules based on functionality, making the codebase easier to maintain and extend.

4. **Sub-agent Architecture**: The use of specialized sub-agents allows for domain-specific handling of different types of queries.

## Architecture Patterns

1. **Tool-based Agent Pattern**: The agent exposes functionality through a set of tools that are registered with the agent framework.

2. **Hierarchical Agent Structure**: A main agent delegates to specialized sub-agents based on the query type.

3. **Functional API Design**: Kubernetes operations are exposed as pure functions with clear inputs and outputs.

4. **Configuration Loading**: Kubernetes configuration is loaded from the default location, allowing the agent to use the same authentication as the user.

5. **Error Handling**: API exceptions are caught and formatted into user-friendly error messages.

6. **Resource Abstraction**: Kubernetes resources are abstracted into simple data structures (dictionaries and lists) for easier consumption by the agent and presentation to the user.
