from unittest.mock import patch, MagicMock
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))


@pytest.fixture(autouse=True)
def mock_db():
    """Mock all database calls so tests don't need PostgreSQL."""
    with patch("tools.db") as mock:
        mock.get_user_profile.return_value = {
            "user_id": "USER_#01",
            "age": 30,
            "weight": 70,
            "height": 175,
            "goal": "muscle_gain",
            "restrictions": "",
        }
        mock.upsert_user_profile.return_value = True
        mock.get_meal_history.return_value = []
        mock.log_meal.return_value = True
        mock.calculate_running_macros.return_value = {
            "total_calories": 1500,
            "total_protein": 0.0,
            "total_carbs": 0.0,
            "total_fat": 0.0,
        }
        mock.get_nutrition_patterns.return_value = []
        yield mock


def test_check_rda_adequate():
    from tools import _check_rda

    result = _check_rda("protein", 60)
    assert result["status"] == "adequate"
    assert result["percentage_of_rda"] == 120.0


def test_check_rda_deficient():
    from tools import _check_rda

    result = _check_rda("iron", 5)
    assert result["status"] == "deficient"
    assert result["percentage_of_rda"] == pytest.approx(27.8, rel=0.1)


def test_check_rda_low():
    from tools import _check_rda

    result = _check_rda("protein", 25)
    assert result["status"] == "low"


def test_check_rda_unknown_nutrient():
    from tools import _check_rda

    result = _check_rda("unknown_nutrient", 10)
    assert "error" in result


def test_get_user_profile_not_found():
    from tools import get_user_profile
    import tools

    tools.db.get_user_profile.return_value = {}
    result = get_user_profile.invoke({"user_id": "nonexistent"})
    assert "error" in result


def test_upsert_user_profile():
    from tools import upsert_user_profile

    result = upsert_user_profile.invoke(
        {
            "user_id": "test_01",
            "age": 25,
            "weight": 80,
            "height": 180,
            "goal": "weight_loss",
        }
    )
    assert result["success"] is True
    assert result["user_id"] == "test_01"


def test_detect_goal_drift_no_data():
    from tools import detect_goal_drift

    result = detect_goal_drift.invoke({"user_id": "test_01"})
    assert result.get("drift_detected") is False
    assert "reason" in result


def test_detect_goal_drift_with_data():
    from tools import detect_goal_drift
    import tools

    tools.db.get_nutrition_patterns.return_value = [
        {
            "date": "2024-01-01",
            "daily_calories": 1800,
            "daily_protein": 60,
            "daily_iron": 8,
        },
        {
            "date": "2024-01-02",
            "daily_calories": 2000,
            "daily_protein": 55,
            "daily_iron": 7,
        },
    ]
    result = detect_goal_drift.invoke({"user_id": "test_01"})
    assert result["drift_detected"] is True
    assert len(result["flags"]) > 0


@pytest.mark.parametrize(
    "nutrient,amount,expected_status",
    [
        ("protein", 50, "adequate"),
        ("carbs", 150, "low"),
        ("fat", 30, "deficient"),
        ("fiber", 25, "adequate"),
        ("vitamin_d", 300, "low"),
    ],
)
def test_multiple_rda_checks(nutrient, amount, expected_status):
    from tools import _check_rda

    result = _check_rda(nutrient, amount)
    assert result["status"] == expected_status


def test_track_streaks_no_data():
    from tools import track_streaks

    result = track_streaks.invoke({"user_id": "test_01"})
    assert result["logging_streak"] == 0


def test_validate_against_rda_tool():
    from tools import validate_against_rda

    result = validate_against_rda.invoke({"nutrient": "calcium", "daily_amount": 800})
    assert result["status"] == "adequate"
    assert result["nutrient"] == "calcium"


def test_search_nutrition_kb_empty(mocker):
    mocker.patch("tools._vector_store.query", return_value=[])
    from tools import search_nutrition_kb

    result = search_nutrition_kb.invoke({"query": "something"})
    assert result == "No relevant information found."
