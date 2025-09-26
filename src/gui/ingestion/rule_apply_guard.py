"""Safe Execution Guard (Milestone 7.10.30)

Provides a protective layer ensuring no rule-driven ingestion writes reach the
main application database until an explicit successful simulation step has
been performed and validated.

Initial Scope:
- Simulation aggregates extracted rows (using adapter), field coverage, and
  quality gates (if configured under `quality_gates` in the rule document).
- Apply step is only allowed if the latest simulation passed all validation
  criteria. For now criteria are:
    * All quality gates (if any) passed
    * No resources extracted with zero rows when quality gates reference them
- Actual ingestion into domain tables is deferred; we record an audit entry
  in a lightweight `rule_apply_audit` table capturing resource row counts to
  provide a stable, testable side effect.

Future extensions (later milestones):
- Mapping to real schema + transactional upsert pipeline
- Provenance version tagging per applied rule set
- Emission of INGEST_RULES_APPLIED event with detailed counts

The guard is intentionally stateless beyond retaining recent simulations,
allowing tests to operate deterministically.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Any, Optional
import hashlib
import sqlite3
from .rule_schema import RuleSet
from .rule_adapter import adapt_ruleset_over_files

try:  # optional imports for validation enrichment
    from .rule_field_coverage import compute_field_coverage, FieldCoverageReport  # type: ignore
except Exception:  # pragma: no cover
    compute_field_coverage = None  # type: ignore
    FieldCoverageReport = None  # type: ignore

try:
    from .rule_quality_gates import evaluate_quality_gates, QualityGateReport  # type: ignore
except Exception:  # pragma: no cover
    evaluate_quality_gates = None  # type: ignore
    QualityGateReport = None  # type: ignore

__all__ = [
    "SimulationResult",
    "ApplyResult",
    "SafeApplyGuard",
]


def _hash_rules_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha1(repr(sorted(payload.items())).encode("utf-8", "ignore")).hexdigest()[:12]


@dataclass
class SimulationResult:
    sim_id: int
    passed: bool
    reasons: List[str]
    rules_hash: str
    adapter_rows: Dict[str, int]
    coverage_overall: Optional[float] = None
    failed_gates: int = 0
    gate_report: Any | None = None  # avoid tight coupling in signature

    def to_mapping(self) -> Mapping[str, Any]:  # pragma: no cover - trivial
        return {
            "sim_id": self.sim_id,
            "passed": self.passed,
            "reasons": list(self.reasons),
            "rules_hash": self.rules_hash,
            "adapter_rows": dict(self.adapter_rows),
            "coverage_overall": self.coverage_overall,
            "failed_gates": self.failed_gates,
        }


@dataclass
class ApplyResult:
    sim_id: int
    applied: bool
    rows_by_resource: Dict[str, int]


class SafeApplyGuard:
    """Coordinates rule simulation followed by controlled apply.

    Usage pattern:
        guard = SafeApplyGuard()
        sim = guard.simulate(rule_set, html_map, raw_rules_payload)
        if sim.passed:
            res = guard.apply(rule_set, html_map, conn, raw_rules_payload)
    """

    def __init__(self) -> None:
        self._next_id = 1
        self._sims: Dict[int, SimulationResult] = {}

    # ------------------------------------------------------------------
    def simulate(
        self,
        rule_set: RuleSet,
        html_by_file: Mapping[str, str],
        raw_rules_payload: Mapping[str, Any],
    ) -> SimulationResult:
        reasons: List[str] = []
        # Enforce safety flag (settings service) to optionally reject custom python transforms
        try:
            from gui.services.settings_service import SettingsService  # type: ignore
            if getattr(SettingsService.instance, "ingestion_disallow_custom_python", False):
                # Heuristic 1 (legacy): any top-level mapping containing a key with 'python'
                for k, v in raw_rules_payload.items():  # type: ignore[assignment]
                    if isinstance(v, dict) and any("python" in str(x).lower() for x in v.keys()):
                        raise ValueError("custom python expressions disallowed by settings")

                # Heuristic 2 (new): detect nested transform specs of kind == 'expr'.
                # We traverse the raw payload rather than the parsed RuleSet to avoid
                # any future normalisation hiding original intent.
                def _contains_expr(obj: Any) -> bool:  # nested helper
                    if isinstance(obj, Mapping):
                        # typical transform spec: {kind: 'expr', code: '...'}
                        if obj.get("kind") == "expr" and "code" in obj:
                            return True
                        for vv in obj.values():
                            if _contains_expr(vv):
                                return True
                        return False
                    if isinstance(obj, list):
                        return any(_contains_expr(it) for it in obj)
                    return False

                if _contains_expr(raw_rules_payload):
                    raise ValueError(
                        "custom python expressions disallowed by settings (expr transform)"
                    )
        except ValueError:
            # Propagate explicit security block errors
            raise
        except Exception:  # pragma: no cover - defensive import/attr errors only
            pass

        bundle = adapt_ruleset_over_files(rule_set, html_by_file)
        adapter_rows = {r: len(res.rows) for r, res in bundle.resources.items()}
        cov_ratio = None
        failed_gates = 0
        # Field coverage (if backend available)
        if compute_field_coverage is not None:
            try:
                cov_report = compute_field_coverage(rule_set, html_by_file)
                cov_ratio = cov_report.overall_ratio
            except Exception as e:  # pragma: no cover
                reasons.append(f"coverage error: {e}")
        # Quality gates (if config & backend available)
        gate_report = None
        if evaluate_quality_gates is not None:
            qcfg = (
                raw_rules_payload.get("quality_gates")
                if isinstance(raw_rules_payload, Mapping)
                else None
            )
            if isinstance(qcfg, Mapping) and qcfg:
                try:
                    gate_report = evaluate_quality_gates(rule_set, html_by_file, qcfg)  # type: ignore[arg-type]
                    failed_gates = gate_report.failed_count
                    if failed_gates:
                        reasons.append(f"{failed_gates} quality gates failed")
                except Exception as e:  # pragma: no cover
                    reasons.append(f"quality gates error: {e}")
        # Simple validation: if any gate references a resource with zero rows
        # (adapter rows) note that as a reason (helps catch selector drift).
        if isinstance(raw_rules_payload, Mapping):
            qcfg = raw_rules_payload.get("quality_gates")
            if isinstance(qcfg, Mapping):
                for key in qcfg.keys():  # resource.field style
                    res_name = key.split(".", 1)[0]
                    if adapter_rows.get(res_name, 0) == 0:
                        reasons.append(f"referenced resource '{res_name}' produced 0 rows")
        passed = not reasons
        sim_id = self._next_id
        self._next_id += 1
        sim = SimulationResult(
            sim_id=sim_id,
            passed=passed,
            reasons=reasons,
            rules_hash=_hash_rules_payload(raw_rules_payload),
            adapter_rows=adapter_rows,
            coverage_overall=cov_ratio,
            failed_gates=failed_gates,
            gate_report=gate_report,
        )
        self._sims[sim_id] = sim
        return sim

    # ------------------------------------------------------------------
    def apply(
        self,
        sim_id: int,
        rule_set: RuleSet,
        html_by_file: Mapping[str, str],
        raw_rules_payload: Mapping[str, Any],
        conn: sqlite3.Connection,
    ) -> ApplyResult:
        sim = self._sims.get(sim_id)
        if sim is None:
            raise ValueError("Unknown simulation id")
        if not sim.passed:
            raise RuntimeError("Cannot apply: simulation failed validation")
        # Ensure audit table exists
        conn.execute(
            "CREATE TABLE IF NOT EXISTS rule_apply_audit("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
            "sim_id INTEGER,"
            "rules_hash TEXT,"
            "resource TEXT,"
            "row_count INTEGER)"
        )
        for r, count in sim.adapter_rows.items():
            conn.execute(
                "INSERT INTO rule_apply_audit(sim_id, rules_hash, resource, row_count) VALUES(?,?,?,?)",
                (sim.sim_id, sim.rules_hash, r, count),
            )
        conn.commit()
        return ApplyResult(sim_id=sim_id, applied=True, rows_by_resource=dict(sim.adapter_rows))
