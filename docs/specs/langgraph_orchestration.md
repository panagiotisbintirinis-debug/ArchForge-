# LangGraph multi-agent orchestration

This layer coordinates model reasoning around ArchForge. It is deliberately not a
second geometry engine and it never mutates Document directly.

## Execution contract

One graph invocation performs:

1. GPT-side proposer receives the user request, current model snapshot, and the
   machine-readable ArchForge action manifest.
2. The proposer returns exactly one semantic ArchForge action as JSON.
3. Gemini-side reviewer returns approve, revise, or reject.
4. Revise loops back to the proposer, bounded by max_review_rounds.
5. Approve executes the action only through ArchForgeAIClient.execute_action().
6. Invalid JSON, unsupported actions, invalid reviews, execution failures, reject,
   and max-round exhaustion all stop explicitly.

Exactly one ArchForge action is executed per graph invocation. This is intentional:
it prevents an LLM-generated multi-action plan from partially mutating the model if
a later action fails. A long design session repeatedly invokes the graph while
reusing the same ArchForgeAIClient.

## Install

Core ArchForge does not require LangGraph or provider SDKs.

    python -m pip install -r requirements-agents.txt

The pinned versions were selected for the current Python 3.11 agent runner. Update
them only through a tested PR.

## Credentials

Never commit or print credentials. Provider adapters read them from environment
variables.

OpenAI proposer:

    OPENAI_API_KEY
    ARCHFORGE_GPT_MODEL

Gemini reviewer:

    GEMINI_API_KEY

or:

    GOOGLE_API_KEY

and:

    ARCHFORGE_GEMINI_MODEL

ArchForge intentionally does not guess provider model names. Set both model
variables explicitly so a model migration is a configuration change rather than a
silent behavior change.

## Python example

    from archforge.architecture.ai_commands import ArchForgeAIClient
    from archforge.orchestration.langgraph_flow import LangGraphArchForgeOrchestrator
    from archforge.orchestration.providers import create_gemini_agent, create_openai_agent

    client = ArchForgeAIClient()
    flow = LangGraphArchForgeOrchestrator(
        proposer=create_openai_agent(),
        reviewer=create_gemini_agent(),
        client=client,
        max_review_rounds=3,
    )

    result = flow.run("Create one 6 m by 5 m pod at the origin.")
    print(result["status"])

## Relationship to GitHub autonomy

This graph solves model-level proposal/review/execution. It does not itself create a
persistent background scheduler and it does not replace AGENTS.md, GitHub Issues,
branches, pull requests, or CI.

A scheduled GitHub Actions runner can invoke this orchestration layer after repository
secrets are configured. Until then, keep scheduled execution disabled rather than
creating a workflow that predictably fails for missing credentials.

## Truth boundary

A reviewer approval means only that an action may be sent to the ArchForge semantic
execution contract. It does not mean structural, fabrication, environmental,
building-code, cost, or safety verification.
