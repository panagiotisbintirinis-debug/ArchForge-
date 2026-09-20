"""Regression contracts for the optional LangGraph multi-agent orchestrator."""

import json

from archforge.orchestration.langgraph_flow import LangGraphArchForgeOrchestrator


class FakeAgent:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def invoke(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("fake agent exhausted")
        response = self.responses.pop(0)
        return json.dumps(response) if isinstance(response, dict) else response


def _create_pod_action(name="Agent Pod"):
    return {
        "action": "create_pod",
        "params": {
            "cx": 0.0,
            "cy": 0.0,
            "diameter_x": 6.0,
            "diameter_y": 5.0,
            "height": 3.2,
            "name": name,
        },
        "reason": "Create the requested initial pod.",
    }


def test_approved_action_executes_only_through_archforge_ai_client():
    proposer = FakeAgent([_create_pod_action()])
    reviewer = FakeAgent([{"decision": "approve", "feedback": "Contract-safe."}])
    orchestrator = LangGraphArchForgeOrchestrator(proposer, reviewer, max_review_rounds=2)

    state = orchestrator.run("Create one pod.")

    assert state["status"] == "executed"
    assert state["error"] is None
    assert len(state["execution_results"]) == 1
    result = state["execution_results"][0]
    assert result["success"] is True
    pod_id = result["entity_ids"][0]
    assert orchestrator.client.doc.get(pod_id).kind == "pod"
    assert orchestrator.client.doc.get(pod_id).name == "Agent Pod"


def test_reviewer_can_request_revision_before_execution():
    proposer = FakeAgent([
        _create_pod_action("First Draft"),
        _create_pod_action("Revised Draft"),
    ])
    reviewer = FakeAgent([
        {"decision": "revise", "feedback": "Use a clearer semantic name."},
        {"decision": "approve", "feedback": "Approved."},
    ])
    orchestrator = LangGraphArchForgeOrchestrator(proposer, reviewer, max_review_rounds=3)

    state = orchestrator.run("Create a clearly named pod.")

    assert state["status"] == "executed"
    assert state["review_round"] == 2
    assert len(proposer.prompts) == 2
    assert "Use a clearer semantic name." in proposer.prompts[1]
    pod_id = state["execution_results"][0]["entity_ids"][0]
    assert orchestrator.client.doc.get(pod_id).name == "Revised Draft"


def test_unsupported_action_fails_closed_before_document_mutation():
    proposer = FakeAgent([
        {
            "action": "teleport_pod",
            "params": {"pod_id": "made-up"},
            "reason": "This must be rejected before execution.",
        }
    ])
    reviewer = FakeAgent([{"decision": "approve", "feedback": "Irrelevant because proposal is invalid."}])
    orchestrator = LangGraphArchForgeOrchestrator(proposer, reviewer)

    state = orchestrator.run("Teleport a pod.")

    assert state["status"] == "invalid_proposal"
    assert "unsupported action" in state["error"].lower()
    assert orchestrator.client.doc.entities == {}
    assert reviewer.prompts == []


def test_invalid_json_fails_closed_without_execution():
    proposer = FakeAgent(["not-json"])
    reviewer = FakeAgent([])
    orchestrator = LangGraphArchForgeOrchestrator(proposer, reviewer)

    state = orchestrator.run("Create a pod.")

    assert state["status"] == "invalid_proposal"
    assert state["execution_results"] == []
    assert orchestrator.client.doc.entities == {}


def test_review_loop_stops_at_configured_max_rounds():
    proposer = FakeAgent([
        _create_pod_action("Draft 1"),
        _create_pod_action("Draft 2"),
    ])
    reviewer = FakeAgent([
        {"decision": "revise", "feedback": "Revise once."},
        {"decision": "revise", "feedback": "Revise again."},
    ])
    orchestrator = LangGraphArchForgeOrchestrator(proposer, reviewer, max_review_rounds=2)

    state = orchestrator.run("Create a pod.")

    assert state["status"] == "max_review_rounds"
    assert state["execution_results"] == []
    assert orchestrator.client.doc.entities == {}


def test_reviewer_reject_stops_without_document_mutation():
    proposer = FakeAgent([_create_pod_action()])
    reviewer = FakeAgent([{"decision": "reject", "feedback": "Request conflicts with product scope."}])
    orchestrator = LangGraphArchForgeOrchestrator(proposer, reviewer)

    state = orchestrator.run("Create something out of scope.")

    assert state["status"] == "rejected"
    assert "product scope" in state["feedback"]
    assert orchestrator.client.doc.entities == {}
