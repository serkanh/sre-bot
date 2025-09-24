## FEATURE

You are an experienced Python developer and you are given a task to implement a feature. We ned to implement a feature where will determine how to initate the agents/agent.py with the proper configuration.

## EXAMPLES

 If a user is sets env var Google Gemini with `GOOGLE_API_KEY` the initiation should be like this with GOOGLE_AI_MODEL env var that is set default to 'gemini-2.0-flash'
 ```python
 
 agent = Agent(
        name="sre_agent",
        model='gemini-2.0-flash',
        instruction="""You are an expert Site Reliability Engineer (SRE) assistant specializing in operational tasks,
        infrastructure management, and cost optimization.
```
 
If env var is set to Anthropic with `ANTHROPIC_API_KEY` the initiation should be like this with ANTHROPIC_MODEL env var that is set default to 'claude-3-7-sonnet-20240620'
```
agent = Agent(
        name="sre_agent",
        model=LiteLlm('claude-3-5-sonnet-20240620'),
        instruction="""You are an expert Site Reliability Engineer (SRE) assistant specializing in operational tasks,
        infrastructure management, and cost optimization.
```

if env var is "BEDROCK_INFERENCE_PROFILE" the initiation should be like this:

```python
agent = Agent(
        name="sre_agent",
        model=liteLlm('arn:aws:bedrock:us-west-2:812201244513:inference-profile/us.anthropic.claude-opus-4-1-20250805-v1:0'),
        instruction="""You are an expert Site Reliability Engineer (SRE) assistant specializing in operational tasks,
        infrastructure management, and cost optimization.
```

## DOCUMENTATION

https://google.github.io/adk-docs/agents/models/#method-c-service-account-for-production-automation

## OTHER CONSIDERATIONS


