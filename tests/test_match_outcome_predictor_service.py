"""
Unit tests for MatchOutcomePredictorService.
"""

import pytest
from src.services.match_outcome_predictor_service import (
    MatchOutcomePredictorService,
    CalibrationTracker,
)


def test_predict_win():
    service = MatchOutcomePredictorService(top_n=3, win_threshold=50)
    team_a = [1800, 1750, 1700, 1600]
    team_b = [1600, 1550, 1500, 1400]
    assert service.predict_outcome(team_a, team_b) == "win"


def test_predict_lose():
    service = MatchOutcomePredictorService(top_n=2, win_threshold=30)
    team_a = [1500, 1400, 1300]
    team_b = [1600, 1550, 1500]
    assert service.predict_outcome(team_a, team_b) == "lose"


def test_predict_draw():
    service = MatchOutcomePredictorService(top_n=2, win_threshold=50)
    team_a = [1600, 1500]
    team_b = [1600, 1500]
    assert service.predict_outcome(team_a, team_b) == "draw"


def test_missing_livepz():
    service = MatchOutcomePredictorService(top_n=2, win_threshold=50)
    team_a = [None, None]
    team_b = [1600, 1500]
    assert service.predict_outcome(team_a, team_b) == "draw"


def test_partial_roster():
    service = MatchOutcomePredictorService(top_n=3, win_threshold=50)
    team_a = [1800, None, 1700]
    team_b = [1600, 1550, None]
    assert service.predict_outcome(team_a, team_b) == "win"


def test_probability_distribution_sums_to_one():
    service = MatchOutcomePredictorService(top_n=4, win_threshold=60)
    pred = service.predict([1800, 1700, 1650, 1600], [1700, 1650, 1600, 1500])
    total = pred.p_win + pred.p_draw + pred.p_lose
    assert abs(total - 1.0) < 1e-9
    assert 0 <= pred.p_win <= 1
    assert 0 <= pred.p_draw <= 1
    assert 0 <= pred.p_lose <= 1


def test_calibration_tracker_updates_brier():
    tracker = CalibrationTracker()
    service = MatchOutcomePredictorService(calibration_tracker=tracker)
    pred = service.predict([1800, 1750, 1700], [1600, 1550, 1500])
    assert tracker.brier_score is None
    service.record_actual(pred, "win")
    assert tracker.samples == 1
    assert tracker.brier_score is not None
    first_score = tracker.brier_score
    # Add a second outcome
    pred2 = service.predict([1500, 1490, 1480], [1600, 1590, 1580])
    service.record_actual(pred2, "lose")
    assert tracker.samples == 2
    assert tracker.brier_score != first_score
