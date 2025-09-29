"""Dead Field Pruner logic (Milestone 7.10.A24).

Provides data collection, history tracking and suggestion generation for the
"dead field" pruning feature. A *dead field* is a list field (or table column)
that produced zero non-empty values across the most recent preview window. The
module keeps the surface purely logic-focused so it can be unit tested without
PyQt dependencies. UI layers (dialogs, panels) can import the dataclasses and
helpers defined here to present suggestions and apply user-selected actions to
rule documents.

Overview
--------
* ``DeadFieldHistory`` stores the last *N* preview observations.
* ``compute_dead_field_suggestions`` inspects the history and emits
  ``DeadFieldSuggestion`` entries for fields that have remained empty.
* ``apply_dead_field_actions`` mutates a rule document mapping to comment out or
  delete selected fields (list resources only). Comment-out moves field specs to
  an ``inactive_fields`` stash so they can be restored manually later.

The helpers intentionally treat table columns conservatively; suggestion
computation will include them only when explicitly requested (``include_tables``
flag). The default window size is left to callers so the UI can respect user or
environment configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Deque, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple
from collections import deque
import time

from .rule_schema import ListRule, RuleResource, RuleSet, TableRule
from .rule_parse_preview import ParsePreview

__all__ = [
    "FieldUsageSample",
    "DeadFieldObservation",
    "FieldObservation",
    "DeadFieldSuggestion",
    "DeadFieldAction",
    "DeadFieldHistory",
    "build_dead_field_observation",
    "compute_dead_field_suggestions",
    "apply_dead_field_actions",
]


@dataclass
class FieldUsageSample:
    """Per-field usage statistics captured from a preview run."""

    resource: str
    field: str
    kind: str  # "list" or "table"
    non_empty: int
    total: int

    def has_rows(self) -> bool:
        return self.total > 0


@dataclass
class DeadFieldObservation:
    """Collection of field usage samples for a single preview run."""

    file_label: str
    timestamp: float
    samples: List[FieldUsageSample]


@dataclass
class FieldObservation:
    """Aggregated observation for a single field within the suggestion window."""

    file_label: str
    timestamp: float
    non_empty: int
    total: int

    @property
    def has_rows(self) -> bool:
        return self.total > 0


@dataclass
class DeadFieldSuggestion:
    """Suggestion to comment out or delete a persistently empty field."""

    resource: str
    field: str
    kind: str
    window: int
    observations: List[FieldObservation]

    def preview_count(self) -> int:
        return len(self.observations)

    def evidence_count(self) -> int:
        return sum(1 for obs in self.observations if obs.has_rows)

    def sample_files(self) -> List[str]:
        return [obs.file_label for obs in self.observations]

    def evidence_files(self) -> List[str]:
        return [obs.file_label for obs in self.observations if obs.has_rows]

    def total_rows(self) -> int:
        return sum(obs.total for obs in self.observations if obs.has_rows)

    def reason(self) -> str:
        evidence = self.evidence_count()
        if evidence == 0:
            return "No records produced across preview window"
        return f"0 populated values across {evidence} preview(s) with records"


@dataclass
class DeadFieldAction:
    """User-selected action for a dead field suggestion."""

    resource: str
    field: str
    mode: str  # "comment" or "delete"

    def normalized_mode(self) -> str:
        mode = (self.mode or "").strip().lower()
        if mode not in {"comment", "delete"}:
            raise ValueError(f"Unsupported dead field action: {self.mode}")
        return mode


class DeadFieldHistory:
    """Fixed-size ring buffer storing recent preview observations."""

    def __init__(self, capacity: int = 5):
        if capacity <= 0:
            raise ValueError("capacity must be >= 1")
        self._capacity = int(capacity)
        self._samples: Deque[DeadFieldObservation] = deque(maxlen=self._capacity)

    @property
    def capacity(self) -> int:
        return self._capacity

    def set_capacity(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be >= 1")
        if capacity == self._capacity:
            return
        old_samples = list(self._samples)
        self._capacity = int(capacity)
        self._samples = deque(old_samples[-self._capacity :], maxlen=self._capacity)

    def record(self, observation: DeadFieldObservation) -> None:
        self._samples.append(observation)

    def recent(self, window: int | None = None) -> List[DeadFieldObservation]:
        if window is None or window >= self._capacity:
            return list(self._samples)
        if window <= 0:
            return []
        return list(self._samples)[-window:]

    def clear(self) -> None:
        self._samples.clear()

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._samples)


def _is_non_empty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _collect_samples_for_resource(
    resource_name: str,
    resource: RuleResource,
    preview: ParsePreview,
) -> Iterable[FieldUsageSample]:
    if isinstance(resource, ListRule):
        rows = preview.extracted_records.get(resource_name, [])
        total = len(rows)
        for field_name in resource.fields.keys():
            non_empty = sum(1 for row in rows if _is_non_empty(row.get(field_name)))
            yield FieldUsageSample(
                resource=resource_name,
                field=field_name,
                kind="list",
                non_empty=non_empty,
                total=total,
            )
    elif isinstance(resource, TableRule):
        rows = preview.flattened_tables.get(resource_name, [])
        total = len(rows)
        for column in resource.columns:
            non_empty = sum(1 for row in rows if _is_non_empty(row.get(column)))
            yield FieldUsageSample(
                resource=resource_name,
                field=column,
                kind="table",
                non_empty=non_empty,
                total=total,
            )


def build_dead_field_observation(
    rule_set: RuleSet,
    preview: ParsePreview,
    *,
    file_label: str,
    timestamp: float | None = None,
) -> DeadFieldObservation:
    """Create a ``DeadFieldObservation`` from a preview result."""

    ts = timestamp if timestamp is not None else time.time()
    samples: List[FieldUsageSample] = []
    for resource_name, resource in rule_set.resources.items():
        samples.extend(_collect_samples_for_resource(resource_name, resource, preview))
    return DeadFieldObservation(file_label=file_label, timestamp=ts, samples=samples)


def compute_dead_field_suggestions(
    history: DeadFieldHistory,
    *,
    window: int | None = None,
    include_tables: bool = False,
) -> List[DeadFieldSuggestion]:
    """Return suggestions for fields that stayed empty across the window."""

    snapshots = history.recent(window)
    if not snapshots:
        return []
    target_window = min(len(snapshots), window or history.capacity)
    field_map: Dict[Tuple[str, str, str], List[FieldObservation]] = {}
    for obs in snapshots:
        for sample in obs.samples:
            if sample.kind == "table" and not include_tables:
                continue
            key = (sample.kind, sample.resource, sample.field)
            field_map.setdefault(key, []).append(
                FieldObservation(
                    file_label=obs.file_label,
                    timestamp=obs.timestamp,
                    non_empty=sample.non_empty,
                    total=sample.total,
                )
            )
    suggestions: List[DeadFieldSuggestion] = []
    for (kind, resource, field), observations in field_map.items():
        if len(observations) < target_window:
            continue
        observations.sort(key=lambda ob: ob.timestamp)
        evidence = [ob for ob in observations if ob.has_rows]
        if not evidence:
            continue
        if any(ob.non_empty > 0 for ob in evidence):
            continue
        suggestions.append(
            DeadFieldSuggestion(
                resource=resource,
                field=field,
                kind=kind,
                window=target_window,
                observations=observations[-target_window:],
            )
        )
    suggestions.sort(key=lambda s: (s.resource.lower(), s.field.lower()))
    return suggestions


def apply_dead_field_actions(
    rules_doc: MutableMapping[str, object],
    actions: Sequence[DeadFieldAction],
) -> Tuple[int, int]:
    """Apply dead-field actions to the provided rule document mapping.

    Returns ``(commented, deleted)`` counts for reporting.
    """

    if not actions:
        return 0, 0
    resources = rules_doc.get("resources")
    if not isinstance(resources, MutableMapping):
        raise ValueError("rules_doc missing 'resources' mapping")
    inactive = rules_doc.get("inactive_fields")
    if not isinstance(inactive, MutableMapping):
        inactive = {}
        rules_doc["inactive_fields"] = inactive
    commented = 0
    deleted = 0
    for action in actions:
        mode = action.normalized_mode()
        res_payload = resources.get(action.resource)
        if not isinstance(res_payload, MutableMapping):
            continue
        if res_payload.get("kind") != "list":
            continue
        fields = res_payload.get("fields")
        if not isinstance(fields, MutableMapping):
            continue
        if action.field not in fields:
            continue
        spec = fields.pop(action.field)
        if mode == "comment":
            res_archive = inactive.get(action.resource)
            if not isinstance(res_archive, MutableMapping):
                res_archive = {}
                inactive[action.resource] = res_archive
            res_archive[action.field] = spec
            commented += 1
        else:
            deleted += 1
    return commented, deleted
