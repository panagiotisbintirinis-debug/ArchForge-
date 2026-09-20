"""Run one bounded GPT -> Gemini -> ArchForge orchestration cycle."""

from __future__ import annotations

import argparse
import json
import sys

from archforge.architecture.ai_commands import ArchForgeAIClient
from archforge.orchestration.langgraph_flow import LangGraphArchForgeOrchestrator
from archforge.orchestration.providers import create_gemini_agent, create_openai_agent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("request", help="Natural-language ArchForge design request")
    parser.add_argument("--project", help="Optional .archforge project to load and save")
    parser.add_argument("--max-review-rounds", type=int, default=3)
    args = parser.parse_args()

    client = ArchForgeAIClient()
    if args.project:
        from pathlib import Path

        project = Path(args.project)
        if project.exists():
            loaded = client.load(str(project))
            if not loaded.success:
                print(json.dumps(loaded.to_dict(), indent=2), file=sys.stderr)
                return 2

    flow = LangGraphArchForgeOrchestrator(
        proposer=create_openai_agent(),
        reviewer=create_gemini_agent(),
        client=client,
        max_review_rounds=args.max_review_rounds,
    )
    state = flow.run(args.request)

    if args.project and state.get("status") == "executed":
        saved = client.save(args.project)
        if not saved.success:
            state["status"] = "save_failed"
            state["error"] = "; ".join(err.message for err in saved.errors)

    print(json.dumps(state, indent=2, sort_keys=True))
    return 0 if state.get("status") == "executed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
