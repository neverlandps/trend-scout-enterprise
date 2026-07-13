"""Unit tests for scoring service."""

import pytest

from trend_scout_enterprise.models.models import RawItem
from trend_scout_enterprise.schemas.schemas import ScoringDimension
from trend_scout_enterprise.services.scoring_service import (
    calculate_composite_score,
    get_default_dimensions,
    validate_dimensions,
)


def test_get_default_dimensions():
    dims = get_default_dimensions()
    assert len(dims) == 5
    names = {d.name for d in dims}
    assert names == {
        "signal_strength",
        "cross_domain_impact",
        "investment_velocity",
        "technical_feasibility",
        "strategic_fit",
    }


def test_validate_dimensions_pass():
    dims = [
        ScoringDimension(name="a", weight=0.5, enabled=True),
        ScoringDimension(name="b", weight=0.5, enabled=True),
    ]
    validate_dimensions(dims)  # should not raise


def test_validate_dimensions_fail():
    dims = [
        ScoringDimension(name="a", weight=0.3, enabled=True),
        ScoringDimension(name="b", weight=0.3, enabled=True),
    ]
    with pytest.raises(ValueError) as exc_info:
        validate_dimensions(dims)
    assert "1.0" in str(exc_info.value)


def test_calculate_composite_score():
    item = RawItem(
        id="i1",
        source_id="s1",
        url="http://example.com",
        signal_strength=0.8,
        cross_domain_impact=0.6,
        investment_velocity=0.7,
        technical_feasibility=0.9,
        strategic_fit=0.5,
    )
    score = calculate_composite_score(item)
    assert 0.0 <= score <= 1.0


def test_calculate_composite_score_with_disabled():
    item = RawItem(
        id="i2",
        source_id="s1",
        url="http://example.com",
        signal_strength=1.0,
        cross_domain_impact=0.0,
    )
    dims = [
        ScoringDimension(name="signal_strength", weight=1.0, enabled=True),
        ScoringDimension(name="cross_domain_impact", weight=0.0, enabled=False),
    ]
    score = calculate_composite_score(item, dims)
    assert score == 1.0


def test_calculate_composite_score_no_scores():
    item = RawItem(id="i3", source_id="s1", url="http://example.com")
    score = calculate_composite_score(item)
    assert score == 0.0
