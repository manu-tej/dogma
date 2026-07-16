# tests/hypothesis/orchestrator/test_chat_graph_context.py
"""The LLM chat services now feed a graph neighborhood, not just the focal element."""

import json

from quration.hypothesis.graph import CausalGraph, Edge, Node, NodeType
from quration.hypothesis.orchestrator.edge_chat import LlmEdgeChatService, LlmNodeChatService


class _Capture:
    def __init__(self):
        self.last_messages = None

    def create_message(self, messages, model, **kwargs):
        self.last_messages = messages
        return json.dumps({"reply": "ok", "edit": None})


def _chain():
    g = CausalGraph(id="g", query="does A drive C?")
    g.add_node(Node(id="A", type=NodeType.TARGET, label="EGFR"))
    g.add_node(Node(id="B", type=NodeType.TARGET, label="KRAS"))
    g.add_node(Node(id="C", type=NodeType.PHENOTYPE, label="resistance"))
    g.add_edge(Edge(id="A-B", source_id="A", target_id="B", relation="activates"))
    g.add_edge(Edge(id="B-C", source_id="B", target_id="C", relation="drives"))
    return g


def test_edge_chat_feeds_neighborhood_and_query():
    cap = _Capture()
    LlmEdgeChatService(provider=cap, model="m").respond(_chain(), "A-B", [], "explain")
    prompt = json.dumps(cap.last_messages)
    assert "[A-B]" in prompt and "FOCUS" in prompt
    assert "[B-C]" in prompt              # the neighbor edge (incident to B) is included
    assert "does A drive C?" in prompt    # the query is threaded into the prompt


def test_node_chat_feeds_incident_edges():
    cap = _Capture()
    LlmNodeChatService(provider=cap, model="m").respond(_chain(), "B", [], "what is this?")
    prompt = json.dumps(cap.last_messages)
    assert "FOCUS [B]" in prompt
    assert "[A-B]" in prompt and "[B-C]" in prompt  # both edges incident to B
