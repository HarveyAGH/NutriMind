import os
import sys
import json
import requests
from pathlib import Path
from datetime import date, timedelta

sys.path.append(str(Path(__file__).resolve().parent.parent / "rag"))

from vector_store import FaissVectorStore
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
import db
from dotenv import load_dotenv

load_dotenv()

_vector_store = FaissVectorStore(persist_dir="faiss_store")
_vector_store.load()

RDA = {
    "protein": {"rda": 50, "unit": "g"},
    "carbs": {"rda": 300, "unit": "g"},
    "fat": {"rda": 65, "unit": "g"},
    "iron": {"rda": 18, "unit": "mg"},
    "calcium": {"rda": 1000, "unit": "mg"},
    "vitamin_d": {"rda": 600, "unit": "IU"},
    "fiber": {"rda": 25, "unit": "g"},
}

USDA_NUTRIENT_MAP = {
    1008: "calories",
    1003: "protein_g",
    1004: "fat_g",
    1005: "carbs_g",
    1079: "fiber_g",
    1089: "iron_mg",
    1087: "calcium_mg",
    1093: "sodium_mg",
}


def _check_rda(nutrient: str, daily_amount: float) -> dict:
    key = nutrient.lower()
    if key not in RDA:
        return {"error": f"Unknown nutrient '{nutrient}'. Valid: {list(RDA.keys())}"}
    rda_val = RDA[key]["rda"]
    pct = round((daily_amount / rda_val) * 100, 1) if rda_val else 0
    status = "adequate" if pct >= 80 else ("low" if pct >= 50 else "deficient")
    return {
        "nutrient": key,
        "daily_amount": daily_amount,
        "rda": rda_val,
        "unit": RDA[key]["unit"],
        "percentage_of_rda": pct,
        "status": status,
    }


@tool
def get_user_profile(user_id: str) -> dict:
    """Retrieve a user's profile (age, weight, height, goal, restrictions) from the database."""
    result = db.get_user_profile(user_id)
    return (
        result
        if result
        else {"error": "Profile not found. Ask the user to set up their profile first."}
    )


@tool
def upsert_user_profile(
    user_id: str,
    age: int,
    weight: float,
    height: float,
    goal: str,
    restrictions: str = "",
) -> dict:
    """
    Create or update a user's profile.
    goal: one of 'weight_loss', 'muscle_gain', 'maintenance', 'general_health'
    restrictions: comma-separated dietary restrictions e.g. 'gluten-free, vegetarian'
    """
    success = db.upsert_user_profile(
        user_id,
        {
            "age": age,
            "weight": weight,
            "height": height,
            "goal": goal,
            "restrictions": restrictions,
        },
    )
    return {"success": success, "user_id": user_id}


@tool
def get_meal_history(user_id: str, days: int = 7) -> list:
    """Retrieve the user's meal log for the last N days, ordered by most recent."""
    return db.get_meal_history(user_id, days)


@tool
def search_nutrition_kb(query: str) -> str:
    """
    Search the internal nutrition knowledge base for evidence-based guidelines.
    Use for questions about macros, micronutrients, dietary science, or food categories.
    """
    results = _vector_store.query(query, top_k=5)
    if not results:
        return "No relevant information found."

    texts = [r["metadata"]["text"] for r in results if r.get("metadata")]
    if not texts:
        return "No relevant information found."

    return "\n\n".join(f"[{i + 1}] {t}" for i, t in enumerate(texts))


@tool
def get_nutrition_info(food_item: str) -> dict:
    """
    Look up full nutrition data for a food item via the USDA FoodData Central API.
    Returns calories, macros, and key micronutrients (iron, fiber, calcium).
    Always call this before log_meal so iron_mg and fiber_g values are accurate.
    """
    api_key = os.getenv("USDA_FDC_API_KEY")
    if not api_key:
        return {"error": "Set USDA_FDC_API_KEY in your .env"}

    try:
        search = requests.get(
            "https://api.nal.usda.gov/fdc/v1/foods/search",
            params={
                "query": food_item,
                "dataType": "SR Legacy",
                "pageSize": 1,
                "api_key": api_key,
            },
            timeout=(5, 10),
        )
        search.raise_for_status()
        foods = search.json().get("foods", [])

        if not foods:
            return {"error": f"No USDA data found for '{food_item}'."}

        fdc_id = foods[0]["fdcId"]
        food_name = foods[0].get("description", food_item)

        detail = requests.get(
            f"https://api.nal.usda.gov/fdc/v1/food/{fdc_id}",
            params={"api_key": api_key},
            timeout=(5, 10),
        )
        detail.raise_for_status()
        food_data = detail.json()

        nutrients_raw = {}
        for n in food_data.get("foodNutrients", []):
            nid = n.get("nutrient", {}).get("id") or n.get("nutrientId")
            amount = n.get("amount") or n.get("value") or 0
            if nid:
                nutrients_raw[int(nid)] = amount

        result = {
            "food": food_name,
            "source": "USDA FoodData Central",
            "fdc_id": fdc_id,
            "serving_size_g": food_data.get("servingSize", 100),
        }

        for nid, key in USDA_NUTRIENT_MAP.items():
            result[key] = round(float(nutrients_raw.get(nid, 0)), 2)

        return result

    except requests.RequestException as e:
        return {"error": f"USDA request failed: {str(e)}"}


@tool
def validate_against_rda(nutrient: str, daily_amount: float) -> dict:
    """
    Check if a daily nutrient amount meets the Recommended Daily Allowance.
    Returns percentage, status ('adequate'/'low'/'deficient'), and the RDA target.
    """
    return _check_rda(nutrient, daily_amount)


@tool
def detect_goal_drift(user_id: str) -> dict:
    """
    Compare the user's actual intake over the last 7 days against their stated goal.
    Returns drift flags and average intake stats. Use before generating a meal plan.
    """
    profile = db.get_user_profile(user_id)
    if not profile:
        return {"error": "No profile found for user."}

    patterns = db.get_nutrition_patterns(user_id, window_days=7)
    if not patterns:
        return {"drift_detected": False, "reason": "No meal data in the last 7 days."}

    avg_calories = sum(r["daily_calories"] or 0 for r in patterns) / len(patterns)
    avg_protein = sum(r["daily_protein"] or 0 for r in patterns) / len(patterns)
    goal = (profile.get("goal") or "").lower()
    flags = []

    if "weight_loss" in goal or "lose" in goal:
        if avg_calories > 2100:
            flags.append(
                f"Avg calories ({avg_calories:.0f}) too high for weight loss goal."
            )
        if avg_protein < 80:
            flags.append(
                f"Avg protein ({avg_protein:.0f}g) too low — risks muscle loss during deficit."
            )
    elif "muscle" in goal or "bulk" in goal or "gain" in goal:
        if avg_protein < 120:
            flags.append(
                f"Avg protein ({avg_protein:.0f}g) too low for muscle gain goal (target: 120g+)."
            )
        if avg_calories < 2400:
            flags.append(
                f"Avg calories ({avg_calories:.0f}) too low for a caloric surplus."
            )
    elif "maintenance" in goal:
        if avg_calories < 1600 or avg_calories > 2800:
            flags.append(
                f"Avg calories ({avg_calories:.0f}) outside healthy maintenance range."
            )

    return {
        "drift_detected": len(flags) > 0,
        "flags": flags,
        "avg_daily_calories": round(avg_calories, 1),
        "avg_daily_protein_g": round(avg_protein, 1),
        "days_analyzed": len(patterns),
        "goal": goal,
    }


@tool
def score_meal_plan(meal_plan: str, user_goal: str, restrictions: str = "") -> dict:
    """
    LLM-as-judge eval gate. Score a generated meal plan before returning it to the user.
    Returns a score out of 10 and a pass/fail flag. Reject plans that score below 7.
    """
    from langchain_aws import ChatBedrockConverse

    bedrock_model = os.getenv(
        "BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    )
    bedrock_region = os.getenv("BEDROCK_REGION", "us-east-1")
    judge = ChatBedrockConverse(model=bedrock_model, region_name=bedrock_region)

    prompt = f"""Evaluate this meal plan for a user with goal: '{user_goal}' and restrictions: '{restrictions or "none"}'.
MEAL PLAN:
{meal_plan}

Respond ONLY in valid JSON — no markdown, no text outside the JSON:
{{
  "macro_balance": <0-3>,
  "variety": <0-3>,
  "feasibility": <0-2>,
  "safety": <0-2>,
  "score": <0-10>,
  "reasoning": "<one sentence>",
  "pass": <true if score >= 7>
}}"""

    try:
        response = judge.invoke(
            [
                SystemMessage(
                    content="You are a certified registered dietitian. Be strict and precise."
                ),
                HumanMessage(content=prompt),
            ]
        )
        return json.loads(response.content)
    except json.JSONDecodeError:
        return {"error": "Judge returned invalid JSON", "score": 0, "pass": False}
    except Exception as e:
        return {"error": f"Eval failed: {str(e)}", "score": 0, "pass": False}


@tool
def log_meal(
    user_id: str,
    food: str,
    calories: int,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    iron_mg: float = 0.0,
    fiber_g: float = 0.0,
) -> dict:
    """
    Log a meal to the database. Call get_nutrition_info first to get accurate
    iron_mg and fiber_g values.
    """
    macros = {
        "protein": protein_g,
        "carbs": carbs_g,
        "fat": fat_g,
        "iron": iron_mg,
        "fiber": fiber_g,
    }
    success = db.log_meal(user_id, food, calories, macros)
    return {"success": success, "food": food, "calories": calories}


@tool
def get_running_macros(user_id: str) -> dict:
    """Get today's cumulative calorie and macro totals for the user."""
    return db.calculate_running_macros(user_id)


@tool
def detect_deficiencies(user_id: str, days: int = 7) -> dict:
    """
    Analyze the last N days of meals to flag nutritional deficiencies against RDA.
    Returns a list of deficient nutrients with percentage of RDA.
    """
    patterns = db.get_nutrition_patterns(user_id, window_days=days)
    if not patterns:
        return {"deficiencies": [], "reason": "No meal data found in the given window."}

    n = len(patterns)
    avg_protein = sum(r["daily_protein"] or 0 for r in patterns) / n
    avg_iron = sum(r["daily_iron"] or 0 for r in patterns) / n

    deficiencies = []
    for nutrient, avg_val in [("protein", avg_protein), ("iron", avg_iron)]:
        check = _check_rda(nutrient, avg_val)
        if check.get("status") in ("low", "deficient"):
            deficiencies.append(
                {
                    "nutrient": nutrient,
                    "status": check["status"],
                    "percentage_of_rda": check["percentage_of_rda"],
                    "avg_daily": round(avg_val, 2),
                    "rda_target": check["rda"],
                    "unit": check["unit"],
                }
            )

    return {
        "deficiencies": deficiencies,
        "deficiency_detected": len(deficiencies) > 0,
        "days_analyzed": n,
    }


@tool
def analyze_nutrition_patterns(user_id: str, window_days: int = 14) -> dict:
    """
    Longitudinal analysis of the user's nutrition over N days.
    Detects low-calorie streaks, iron concerns, and sets medical_flag if needed.
    """
    patterns = db.get_nutrition_patterns(user_id, window_days=window_days)
    if not patterns:
        return {"has_data": False, "reason": "No meal data in the analysis window."}

    n = len(patterns)
    calorie_series = [r["daily_calories"] or 0 for r in patterns]
    avg_cal = sum(calorie_series) / n
    avg_iron = sum(r["daily_iron"] or 0 for r in patterns) / n

    low_cal_streak = 0
    for cal in calorie_series:
        if cal < 1200:
            low_cal_streak += 1
        else:
            break

    return {
        "has_data": True,
        "days_analyzed": n,
        "avg_daily_calories": round(avg_cal, 1),
        "avg_daily_iron_mg": round(avg_iron, 3),
        "low_calorie_streak": low_cal_streak,
        "medical_flag": low_cal_streak >= 3,
        "iron_concern": avg_iron < 9.0,
        "calorie_concern": avg_cal < 1400,
    }


@tool
def track_streaks(user_id: str) -> dict:
    """
    Track the user's logging streak and 30-day adherence rate.
    """
    patterns = db.get_nutrition_patterns(user_id, window_days=30)
    if not patterns:
        return {"logging_streak": 0, "total_logged_days": 0, "adherence_pct": 0.0}

    logged_dates = {r["date"] for r in patterns}
    streak = 0
    check = date.today()
    while check in logged_dates:
        streak += 1
        check -= timedelta(days=1)

    return {
        "logging_streak": streak,
        "total_logged_days": len(logged_dates),
        "adherence_pct": round(len(logged_dates) / 30 * 100, 1),
    }
