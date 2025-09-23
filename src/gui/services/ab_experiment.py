"""A/B Experiment Harness (Milestone 5.10.54)

Provides a lightweight, deterministic experiment assignment service with:
 - Explicit experiment registration (id -> variants + weights)
 - Deterministic per-user assignment using SHA1 hashing
 - Optional environment variable overrides (RP_EXPERIMENT_FORCE_<EXPERIMENT>)
 - Persistent assignment storage (JSON) to keep variant stable across sessions
 - JSONL event logging (assignment + override) for later analysis

Design choices:
 - Pure-Python; avoids external deps for portability/testability.
 - Hash-based deterministic mapping ensures reproducibility without storing
   large random seeds. User identity is an arbitrary string provided by caller.
 - Weights are normalized automatically; omitted weights imply equal split.

Future extensions:
 - Namespace segmentation (e.g., theme vs feature experiments)
 - Exposure tracking hooks (log when experiment actually influences UI)
 - Batched export / analytics adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
import hashlib
import json
import os
import time
import threading

__all__ = ["ABExperimentService", "ExperimentDefinition", "ExperimentAssignment"]


@dataclass
class ExperimentDefinition:
    """Definition of a single experiment.

    Attributes
    ----------
    experiment_id: str
        Unique identifier (snake_case recommended).
    variants: Sequence[str]
        Variant labels.
    weights: Optional[Sequence[float]]
        Relative weights. If None, all variants are equally weighted.
    """

    experiment_id: str
    variants: Sequence[str]
    weights: Optional[Sequence[float]] = None

    def normalized_weights(self) -> List[float]:
        if not self.weights:
            n = len(self.variants)
            return [1 / n] * n
        total = float(sum(self.weights))
        if total <= 0:
            raise ValueError("Experiment weights must sum to > 0")
        return [w / total for w in self.weights]


@dataclass
class ExperimentAssignment:
    """Represents a resolved assignment for a user in an experiment."""

    experiment_id: str
    user_id: str
    variant: str
    assigned_at: float
    source: str  # 'fresh', 'cached', 'override'


class ABExperimentService:
    """Service managing simple deterministic A/B experiment assignments.

    Thread-safe for concurrent lookups via an internal lock.
    """

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self._defs: Dict[str, ExperimentDefinition] = {}
        self._assignments: Dict[Tuple[str, str], ExperimentAssignment] = {}
        self._lock = threading.Lock()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._assign_path = self.base_dir / "experiment_assignments.json"
        self._events_path = self.base_dir / "experiment_events.jsonl"
        self._load_existing_assignments()

    # Public API -------------------------------------------------------
    def register(self, definition: ExperimentDefinition) -> None:
        """Register (or replace) an experiment definition."""
        if not definition.variants:
            raise ValueError("Experiment must define at least one variant")
        if definition.experiment_id in self._defs:
            # Replacement allowed for test dynamism; real usage might forbid.
            pass
        self._defs[definition.experiment_id] = definition

    def assign(self, experiment_id: str, user_id: str) -> ExperimentAssignment:
        """Return the variant assignment for a user, creating it if needed.

        Environment variable override: RP_EXPERIMENT_FORCE_<EXPERIMENT_UPPER>
        When set, always returns the forced variant (still cached locally) and
        logs an override event.
        """
        with self._lock:
            key = (experiment_id, user_id)
            # Cached
            if key in self._assignments:
                return self._assignments[key]
            definition = self._defs.get(experiment_id)
            if not definition:
                raise KeyError(f"Experiment '{experiment_id}' not registered")
            forced = self._env_override(experiment_id)
            if forced is not None:
                if forced not in definition.variants:
                    raise ValueError(
                        f"Forced variant '{forced}' not in variants {definition.variants}"
                    )
                assignment = ExperimentAssignment(
                    experiment_id=experiment_id,
                    user_id=user_id,
                    variant=forced,
                    assigned_at=time.time(),
                    source="override",
                )
            else:
                variant = self._deterministic_variant(definition, user_id)
                assignment = ExperimentAssignment(
                    experiment_id=experiment_id,
                    user_id=user_id,
                    variant=variant,
                    assigned_at=time.time(),
                    source="fresh",
                )
            self._assignments[key] = assignment
            self._persist_assignment(assignment)
            self._log_event(assignment)
            return assignment

    def get_cached(self, experiment_id: str, user_id: str) -> Optional[ExperimentAssignment]:
        return self._assignments.get((experiment_id, user_id))

    # Internal helpers -------------------------------------------------
    def _env_override(self, experiment_id: str) -> Optional[str]:
        env_key = f"RP_EXPERIMENT_FORCE_{experiment_id.upper()}"
        return os.environ.get(env_key)

    def _deterministic_variant(self, definition: ExperimentDefinition, user_id: str) -> str:
        weights = definition.normalized_weights()
        # Hash = uniform float in [0,1)
        h = hashlib.sha1(f"{definition.experiment_id}:{user_id}".encode("utf-8")).digest()
        bucket = int.from_bytes(h[:8], "big") / 2 ** 64
        cumulative = 0.0
        for variant, w in zip(definition.variants, weights):
            cumulative += w
            if bucket < cumulative:
                return variant
        return definition.variants[-1]

    # Persistence / Logging -------------------------------------------
    def _load_existing_assignments(self) -> None:
        if not self._assign_path.exists():
            return
        try:
            data = json.loads(self._assign_path.read_text(encoding="utf-8"))
            for exp_id, user_map in data.items():
                for user_id, payload in user_map.items():
                    self._assignments[(exp_id, user_id)] = ExperimentAssignment(
                        experiment_id=exp_id,
                        user_id=user_id,
                        variant=payload["variant"],
                        assigned_at=payload.get("assigned_at", 0.0),
                        source=payload.get("source", "cached"),
                    )
        except Exception:  # pragma: no cover - defensive
            pass

    def _persist_assignment(self, assignment: ExperimentAssignment) -> None:
        # Reconstruct nested mapping structure for disk
        nested: Dict[str, Dict[str, Dict[str, object]]] = {}
        if self._assign_path.exists():
            try:
                nested = json.loads(self._assign_path.read_text(encoding="utf-8"))
            except Exception:
                nested = {}
        exp_map = nested.setdefault(assignment.experiment_id, {})
        exp_map[assignment.user_id] = {
            "variant": assignment.variant,
            "assigned_at": assignment.assigned_at,
            "source": assignment.source,
        }
        try:
            self._assign_path.write_text(json.dumps(nested, indent=2), encoding="utf-8")
        except Exception:  # pragma: no cover
            pass

    def _log_event(self, assignment: ExperimentAssignment) -> None:
        event = {
            "type": "experiment.assignment",
            "ts": time.time(),
            **asdict(assignment),
        }
        try:
            with self._events_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception:  # pragma: no cover
            pass


# Convenience factory (optional future registration via service locator)
def create_ab_experiment_service(base_dir: str) -> ABExperimentService:  # pragma: no cover - thin
    return ABExperimentService(base_dir)
