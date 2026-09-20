"""Bounded GPT-to-Gemini review orchestration for the ArchForge AI contract.

This module is optional infrastructure. LangGraph coordinates reasoning; it is
not a second geometry/model layer. Exactly one semantic ArchForge action is
approved and executed per graph invocation so a failed multi-action plan cannot
leave a partially applied transaction.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Protocol, TypedDict

from archforge.architecture.ai_commands import ArchForgeAIClient


class AgentProtocol(Protocol):
    """Minimal provider-neutral interface required by the graph."""

    def invoke(self, prompt: str) -> Any:
        ...


class OrchestrationState(TypedDict, total=False):
    request: str
    proposal: dict[str, Any] | None
    review: dict[str, Any] | None
    feedback: str
    review_round: int
    max_review_rounds: int
    status: str
    error: str | None
    execution_results: list[dict[str, Any]]


class ProposalValidationError(ValueError):
    """The proposing model returned data outside the ArchForge action contract."""


class ReviewValidationError(ValueError):
    """The reviewing model returned an invalid review decision."""


def _response_text(response: Any) -> str:
    """Normalize strings and LangChain chat-message content to plain text."""

    if isinstance(response, str):
        return response

    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, Mapping) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "".join(parts)

    raise TypeError(
        "Agent response must be a string or expose textual '.content'; "
        f"received {type(response).__name__}"
    )


def _parse_json_object(raw: str, *, label: str) -> dict[str, Any]:
    """Parse one JSON object, allowing only an optional Markdown JSON fence."""

    text = raw.strip()
    fence = chr(96) * 3
    if text.startswith(fence):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == fence:
            lines = lines[1:-1]
            text = "\n".join(lines).strip()

    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} did not return valid JSON: {exc.msg}") from exc

    if not isinstance(value, dict):
        raise ValueError(f"{label} must return one JSON object")
    return value


class LangGraphArchForgeOrchestrator:
    """Coordinate proposal/review while preserving ArchForge as model truth.

    A run approves at most one semantic action. Long design sessions call the
    graph repeatedly while reusing the same ArchForgeAIClient instance.
    """

    def __init__(
        self,
        proposer: AgentProtocol,
        reviewer: AgentProtocol,
        *,
        client: ArchForgeAIClient | None = None,
        max_review_rounds: int = 3,
    ):
        if max_review_rounds < 1:
            raise ValueError("max_review_rounds must be >= 1")

        self.proposer = proposer
        self.reviewer = reviewer
        self.client = client if client is not None else ArchForgeAIClient()
        self.max_review_rounds = int(max_review_rounds)
        self._manifest = self.client.get_action_manifest()
        self.graph = self._build_graph()

    def _build_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise RuntimeError(
                "LangGraph orchestration is optional. Install requirements-agents.txt "
                "before constructing LangGraphArchForgeOrchestrator."
            ) from exc

        builder = StateGraph(OrchestrationState)
        builder.add_node("propose", self._propose)
        builder.add_node("review", self._review)
        builder.add_node("execute", self._execute)
        builder.add_node("max_rounds", self._max_rounds)

        builder.add_edge(START, "propose")
        builder.add_conditional_edges(
            "propose",
            self._route_after_proposal,
            {"review": "review", "end": END},
        )
        builder.add_conditional_edges(
            "review",
            self._route_after_review,
            {
                "propose": "propose",
                "execute": "execute",
                "max_rounds": "max_rounds",
                "end": END,
            },
        )
        builder.add_edge("execute", END)
        builder.add_edge("max_rounds", END)
        return builder.compile()

    def _model_snapshot(self) -> dict[str, Any]:
        return self.client.list_entities().to_dict()

    def _proposal_prompt(self, state: OrchestrationState) -> str:
        feedback = state.get("feedback", "")
        feedback_block = (
            f"\nReviewer feedback from the previous round:\n{feedback}\n"
            if feedback
            else ""
        )
        return (
            "You are the ArchForge proposing engineer. ArchForge, not the LLM, owns "
            "geometric and semantic truth. Propose exactly ONE next semantic action "
            "that advances the user's request. Never invent entity IDs and never "
            "claim engineering/fabrication validity. Use only an action present in "
            "the manifest. Return JSON only, with exactly this shape: "
            '{"action":"<manifest action>","params":{},"reason":"<brief reason>"}.'
            f"\n\nUSER REQUEST:\n{state['request']}"
            f"{feedback_block}"
            "\nCURRENT MODEL SNAPSHOT:\n"
            + json.dumps(self._model_snapshot(), sort_keys=True)
            + "\nACTION MANIFEST:\n"
            + json.dumps(self._manifest, sort_keys=True)
        )

    def _review_prompt(self, state: OrchestrationState) -> str:
        return (
            "You are the independent ArchForge reviewer. Review the proposed single "
            "semantic action against the user request and the ArchForge action "
            "manifest. Check IDs, parameter intent, model coherence, and truth "
            "boundaries. Do not execute anything. Return JSON only with exactly this "
            'shape: {"decision":"approve|revise|reject","feedback":"<brief concrete feedback>"}.'
            f"\n\nUSER REQUEST:\n{state['request']}"
            "\nPROPOSAL:\n"
            + json.dumps(state.get("proposal"), sort_keys=True)
            + "\nCURRENT MODEL SNAPSHOT:\n"
            + json.dumps(self._model_snapshot(), sort_keys=True)
            + "\nACTION MANIFEST:\n"
            + json.dumps(self._manifest, sort_keys=True)
        )

    def _validate_proposal(self, value: Mapping[str, Any]) -> dict[str, Any]:
        action = value.get("action")
        params = value.get("params", {})
        reason = value.get("reason", "")

        if not isinstance(action, str) or not action:
            raise ProposalValidationError("proposal.action must be a non-empty string")
        if action not in self._manifest["actions"]:
            raise ProposalValidationError(f"unsupported action: {action}")
        if not isinstance(params, Mapping):
            raise ProposalValidationError("proposal.params must be a JSON object")
        if not isinstance(reason, str):
            raise ProposalValidationError("proposal.reason must be a string")

        return {"action": action, "params": dict(params), "reason": reason}

    @staticmethod
    def _validate_review(value: Mapping[str, Any]) -> dict[str, str]:
        decision = value.get("decision")
        feedback = value.get("feedback", "")
        if decision not in {"approve", "revise", "reject"}:
            raise ReviewValidationError(
                "review.decision must be one of: approve, revise, reject"
            )
        if not isinstance(feedback, str):
            raise ReviewValidationError("review.feedback must be a string")
        return {"decision": str(decision), "feedback": feedback}

    def _propose(self, state: OrchestrationState) -> dict[str, Any]:
        try:
            raw = _response_text(self.proposer.invoke(self._proposal_prompt(state)))
            parsed = _parse_json_object(raw, label="proposer")
            proposal = self._validate_proposal(parsed)
        except Exception as exc:
            return {"proposal": None, "status": "invalid_proposal", "error": str(exc)}

        return {"proposal": proposal, "status": "proposal_ready", "error": None}

    @staticmethod
    def _route_after_proposal(state: OrchestrationState) -> str:
        return "review" if state.get("status") == "proposal_ready" else "end"

    def _review(self, state: OrchestrationState) -> dict[str, Any]:
        review_round = int(state.get("review_round", 0)) + 1
        try:
            raw = _response_text(self.reviewer.invoke(self._review_prompt(state)))
            parsed = _parse_json_object(raw, label="reviewer")
            review = self._validate_review(parsed)
        except Exception as exc:
            return {
                "review": None,
                "review_round": review_round,
                "status": "invalid_review",
                "error": str(exc),
            }

        status = {
            "approve": "approved",
            "revise": "revision_requested",
            "reject": "rejected",
        }[review["decision"]]
        return {
            "review": review,
            "feedback": review["feedback"],
            "review_round": review_round,
            "status": status,
            "error": None,
        }

    @staticmethod
    def _route_after_review(state: OrchestrationState) -> str:
        status = state.get("status")
        if status == "approved":
            return "execute"
        if status == "revision_requested":
            if int(state.get("review_round", 0)) >= int(
                state.get("max_review_rounds", 1)
            ):
                return "max_rounds"
            return "propose"
        return "end"

    def _execute(self, state: OrchestrationState) -> dict[str, Any]:
        proposal = state.get("proposal")
        if not proposal:
            return {
                "status": "invalid_proposal",
                "error": "execution reached without a validated proposal",
            }

        result = self.client.execute_action(
            proposal["action"],
            dict(proposal.get("params", {})),
        )
        record = result.to_dict()
        if result.success:
            return {
                "execution_results": [record],
                "status": "executed",
                "error": None,
            }

        error_text = "; ".join(error.message for error in result.errors)
        return {
            "execution_results": [record],
            "status": "execution_failed",
            "error": error_text or "ArchForge rejected the approved action",
        }

    @staticmethod
    def _max_rounds(state: OrchestrationState) -> dict[str, Any]:
        return {
            "status": "max_review_rounds",
            "error": (
                "reviewer requested another revision after the configured maximum "
                f"of {state.get('max_review_rounds', 1)} review rounds"
            ),
        }

    def run(self, request: str) -> OrchestrationState:
        if not isinstance(request, str) or not request.strip():
            raise ValueError("request must be a non-empty string")

        initial: OrchestrationState = {
            "request": request.strip(),
            "proposal": None,
            "review": None,
            "feedback": "",
            "review_round": 0,
            "max_review_rounds": self.max_review_rounds,
            "status": "started",
            "error": None,
            "execution_results": [],
        }
        recursion_limit = max(25, self.max_review_rounds * 3 + 5)
        result = self.graph.invoke(
            initial,
            config={"recursion_limit": recursion_limit},
        )
        return dict(result)
