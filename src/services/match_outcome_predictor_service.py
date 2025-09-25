"""Match outcome prediction service (baseline heuristic).

Provides a simple probability model based on the average LivePZ of the top N
players on each team. Also exposes a lightweight calibration tracker that can
compute an incremental Brier score (placeholder for later persistence /
reporting). No external dependencies are introduced to keep the analytics
engine lightweight and easily testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple
import math


@dataclass
class PredictionResult:
    """Container for a single prediction.

    Attributes:
        outcome: Categorical prediction from the perspective of team A ('win', 'draw', 'lose').
        p_win: Estimated probability team A wins.
        p_draw: Estimated probability of draw (may be low / heuristic in table tennis context).
        p_lose: Estimated probability team A loses.
        avg_a: Average LivePZ (top N) for team A or None if insufficient data.
        avg_b: Average LivePZ (top N) for team B or None if insufficient data.
        diff: Difference (avg_a - avg_b) or None.
    """

    outcome: str
    p_win: float
    p_draw: float
    p_lose: float
    avg_a: Optional[float]
    avg_b: Optional[float]
    diff: Optional[float]

    def as_tuple(self) -> Tuple[str, float, float, float]:
        return self.outcome, self.p_win, self.p_draw, self.p_lose


class CalibrationTracker:
    """Incrementally tracks Brier score for binary win/loss (draw merged) predictions.

    For early simplicity we treat draw outcomes as 0.5 target (symmetric
    uncertainty). This can be refined later with a proper multi-class Brier
    implementation if draws become meaningful in domain logic.
    """

    def __init__(self) -> None:
        self._count = 0
        self._brier_sum = 0.0

    def update(self, predicted_p_win: float, actual_outcome: str) -> None:
        target = 1.0 if actual_outcome == "win" else (0.0 if actual_outcome == "lose" else 0.5)
        self._brier_sum += (predicted_p_win - target) ** 2
        self._count += 1

    @property
    def samples(self) -> int:
        return self._count

    @property
    def brier_score(self) -> Optional[float]:
        if self._count == 0:
            return None
        return self._brier_sum / self._count


class MatchOutcomePredictorService:
    """Predicts match outcome using average LivePZ of top N players.

    Probability model:
        We map rating difference (diff = avg_a - avg_b) to win probability via
        a logistic curve with a scale derived from the configured win_threshold
        (i.e. the diff at which p_win ~= 0.75). Draw probability is currently
        a small constant taper near parity; remaining mass assigned to lose.
    """

    def __init__(
        self,
        top_n: int = 4,
        win_threshold: float = 50.0,
        logistic_scale: Optional[float] = None,
        base_draw_prob: float = 0.05,
        calibration_tracker: Optional[CalibrationTracker] = None,
    ) -> None:
        """Initialize predictor.

        Args:
            top_n: Number of top players to consider per team.
            win_threshold: Difference regarded as a clear edge (used for legacy categorical fallback).
            logistic_scale: If provided, overrides automatic scale for logistic; if None uses win_threshold / 1.1.
            base_draw_prob: Baseline draw probability mass near parity (decays with |diff|).
            calibration_tracker: Optional externally managed calibration tracker to record outcomes.
        """
        self.top_n = top_n
        self.win_threshold = win_threshold
        self.logistic_scale = logistic_scale or (win_threshold / 1.1)
        self.base_draw_prob = base_draw_prob
        self.calibration_tracker = calibration_tracker or CalibrationTracker()

    # --- Public API -----------------------------------------------------------------
    def predict(
        self, team_a_livepz: List[Optional[float]], team_b_livepz: List[Optional[float]]
    ) -> PredictionResult:
        """Return probability distribution + categorical outcome.

        If insufficient data for either side, returns a neutral distribution
        (all averages None, outcome 'draw').
        """
        avg_a = self._average_top_n(team_a_livepz)
        avg_b = self._average_top_n(team_b_livepz)
        if avg_a is None or avg_b is None:
            return PredictionResult(
                outcome="draw",
                p_win=0.33,
                p_draw=0.34,
                p_lose=0.33,
                avg_a=avg_a,
                avg_b=avg_b,
                diff=None,
            )
        diff = avg_a - avg_b
        p_win = self._logistic(diff)
        # Draw probability high only when diff near 0, decays with squared diff.
        draw_factor = math.exp(-((diff / (self.win_threshold or 1.0)) ** 2))
        p_draw = self.base_draw_prob * draw_factor
        # Ensure probabilities sum to 1
        p_lose = max(0.0, 1.0 - p_win - p_draw)
        # Normalize (floating rounding protection)
        total = p_win + p_draw + p_lose
        if total > 0:
            p_win, p_draw, p_lose = (p_win / total, p_draw / total, p_lose / total)
        # Categorical outcome aligned with original threshold heuristic
        outcome = (
            "win"
            if diff > self.win_threshold
            else (
                "lose"
                if diff < -self.win_threshold
                else ("win" if p_win > 0.5 else "lose" if p_win < 0.5 else "draw")
            )
        )
        # If within threshold band and p_win near 0.5, allow draw override
        if abs(diff) < self.win_threshold * 0.2 and p_draw > 0.08:
            outcome = "draw"
        return PredictionResult(outcome, p_win, p_draw, p_lose, avg_a, avg_b, diff)

    def predict_outcome(
        self, team_a_livepz: List[Optional[float]], team_b_livepz: List[Optional[float]]
    ) -> str:  # Backwards compatibility
        return self.predict(team_a_livepz, team_b_livepz).outcome

    def record_actual(self, prediction: PredictionResult, actual_outcome: str) -> None:
        """Record actual outcome to update calibration metrics.

        Args:
            prediction: The prediction result previously returned.
            actual_outcome: Observed outcome ('win', 'lose', or 'draw').
        """
        self.calibration_tracker.update(prediction.p_win, actual_outcome)

    # --- Internal helpers -----------------------------------------------------------
    def _average_top_n(self, livepz_list: Iterable[Optional[float]]) -> Optional[float]:
        filtered = [x for x in livepz_list if x is not None]
        if not filtered:
            return None
        top_n = sorted(filtered, reverse=True)[: self.top_n]
        if not top_n:
            return None
        return sum(top_n) / len(top_n)

    def _logistic(self, diff: float) -> float:
        # Logistic centered at 0; scale controls steepness
        return 1.0 / (1.0 + math.exp(-(diff / (self.logistic_scale or 1.0))))

    # Expose calibration metrics
    @property
    def brier_score(self) -> Optional[float]:
        return self.calibration_tracker.brier_score

    @property
    def calibration_samples(self) -> int:
        return self.calibration_tracker.samples
