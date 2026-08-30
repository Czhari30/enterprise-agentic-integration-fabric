from __future__ import annotations

import os

from .connectors import build_default_registry
from .journal import WorkflowJournal
from .model_gateway import OpenAICompatibleGateway
from .orchestrator import AgenticOrchestrator
from .planner import BoundedPlanner
from .policy import PolicyEngine
from .retrieval import HybridRetriever, sample_knowledge_base
from .telemetry import Telemetry


class EnterpriseFabric:
    """Composition root for the reference platform."""

    def __init__(self, database_path: str = ":memory:") -> None:
        self.policy = PolicyEngine()
        self.registry = build_default_registry()
        self.retriever = HybridRetriever(sample_knowledge_base(), self.policy)
        gateway = None
        if os.getenv("MODEL_BASE_URL") and os.getenv("MODEL_API_KEY") and os.getenv("MODEL_NAME"):
            gateway = OpenAICompatibleGateway(
                base_url=os.environ["MODEL_BASE_URL"],
                api_key=os.environ["MODEL_API_KEY"],
                model=os.environ["MODEL_NAME"],
            )
        self.planner = BoundedPlanner(self.registry, gateway)
        self.journal = WorkflowJournal(database_path)
        self.telemetry = Telemetry()
        self.orchestrator = AgenticOrchestrator(
            registry=self.registry,
            retriever=self.retriever,
            policy=self.policy,
            planner=self.planner,
            journal=self.journal,
            telemetry=self.telemetry,
        )
