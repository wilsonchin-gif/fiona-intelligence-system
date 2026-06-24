from __future__ import annotations

from app.fiona_classifier import classify_event
from app.fiona_lifecycle import LifecycleManager
from app.fiona_scoring import score_event
from app.fiona_types import FionaEvent


class FionaAlertEngine:
    def __init__(self, lifecycle_manager: LifecycleManager | None = None) -> None:
        self.lifecycle_manager = lifecycle_manager or LifecycleManager()

    def process(self, event: FionaEvent) -> FionaEvent:
        repeated = event.event_family_id in self.lifecycle_manager.records
        score_event(event, repeated=repeated)
        classify_event(event)
        self.lifecycle_manager.apply(event)
        return event
