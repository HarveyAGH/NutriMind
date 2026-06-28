import os
import json
import requests
from datetime import date, timedelta

from langchain_core.tools import tool
from langchain_aws import ChatBedrockConverse

from langchain_core.messages import HumanMessage
import os
import agent.db as db
from dotenv import load_dotenv



load_dotenv()
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")
client = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION)






RDA = {
    "protein":   {"rda": 50,   "unit": "g"},
    "carbs":     {"rda": 300,  "unit": "g"},
    "fat":       {"rda": 65,   "unit": "g"},
    "iron":      {"rda": 18,   "unit": "mg"},
    "calcium":   {"rda": 1000, "unit": "mg"},
    "vitamin_d": {"rda": 600,  "unit": "IU"},
    "fiber":     {"rda": 25,   "unit": "g"},
}



# Nutrient IDs used by USDA FoodData Central ──────────────────────────────────
USDA_NUTRIENT_MAP = {
    1008: "calories",   # Energy (kcal)
    1003: "protein_g",  # Protien
    1004: "fat_g",      # Total fat
    1005: "carbs_g",    # Carbohydrates
    1079: "fiber_g",   # Dietary Fibre
    1089: "iron_mg",    # Iron (Fe)
    1087: "calcium_mg", # Calcium
    1093: "sodium_mg"   # Sodium
}


# ── MEMORY AGENT TOOLS ────────────────────────────────────────────────────────

@tool
def get_user_profile(user_id: str) -> dict:
    """Retrieve a user's profile (age, weight, height, goal, restrictions) from the database."""
    result = db.get_user_profile(user_id)
    return result if result else {"error": "Profile not found. Ask the user to set up their profile first."}


@tool
def upsert_user_profile(
    user_id: str,
    age: int,
    weight: float,
    height: float,
    goal: str,
    restrictions: str = ""
) -> dict:
    """
    Create or update a user's profile.
    goal: one of 'weight_loss', 'muscle_gain', 'maintenance', 'general_health'
    restrictions: comma-separated dietary restrictions e.g. 'gluten-free, vegetarian'
    """
    success = db.upsert_user_profile(user_id, {
        "age": age,
        "weight": weight,
        "height": height,
        "goal": goal,
        "restrictions": restrictions,
    })
    return {"success": success, "user_id": user_id}


@tool
def get_meal_history(user_id: str, days: int = 7) -> list:
    """Retrieve the user's meal log for the last N days, ordered by most recent."""
    return db.get_meal_history(user_id, days)


# ── NUTRITION RAG AGENT TOOLS ─────────────────────────────────────────────────

@tool
def search_nutrition_kb(query: str) -> str:
    """
    Search the internal nutrition knowledge base for evidence-based guidelines.
    Use for questions about macros, micronutrients, dietary science, or food categories.
    """
    # TODO: Replace with ChromaDB or Pinecone retrieval once KB is built.
    # For now, returns a stub so agent routing works end-to-end.
    return (
        f"[KB stub] Query: '{query}'. "
        "Replace this with actual RAG retrieval. "
        "Build ChromaDB collection from nutrition literature PDFs."
    )


@tool
def get_nutrition_info(food_item: str) -> dict:
    """
    Look up full nutrition data for a food item via the USDA FoodData Central API.
    Returns Calories, macros and key micronutrients (iron, fiber, calcium).
    Always call this tool before log_meal so iron_mg and fiber_mg values are accurate.
    """
    api_key = os.getenv('USDA_FDC_API_KEY')
    if not api_key:
        return{"error": "Please ensure that the USDA_FDC_API_KEY has been configured properly inside your .env"}
    try:
        # Step 1: search for the food, get its FDC ID
        search = requests.get(
            "https://api.nal.usda.gov/fdc/v1/foods/search",
            params={
                "query": food_item,
                "dataType": ["SR Legacy", "Foundation"],
                "pageSize": 1,
                "api_key": api_key,
                
            },
            timeout=10
        )
        search.raise_for_status()
        foods = search.json().get("foods", [])
        
        if not foods:
            return {"error": f"No USDA data found for '{food_item}'."}
        
        fdc_id = foods[0]["fdcId"]
        food_name = foods[0].get("description", food_item)
        
        # Step 2: fetch full nutrient detail by FDC ID
        detail = requests.get(
            f"https://api.nal.usda.gov/fdc/v1/food/{fdc_id}",
            params={"api_key": api_key},
            timeout=10,
        )
        detail.raise_for_status()
        food_data = detail.json()
        
    
        # Detail endpoint structure: foodNutrients[].nutrient.id + .amount
        nutrients_raw = {}
        for n in food_data.get("foodNutrients", []):
            nutrient = n.get("nutrient", {})
            nid = nutrient.get("id")
            amount = n.get("amount", 0) or 0
            if nid:
                nutrients_raw[nid] = amount

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


# ── PLANNING AGENT TOOLS ──────────────────────────────────────────────────────

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
            flags.append(f"Avg calories ({avg_calories:.0f}) too high for weight loss goal.")
        if avg_protein < 80:
            flags.append(f"Avg protein ({avg_protein:.0f}g) too low — risks muscle loss during deficit.")

    elif "muscle" in goal or "bulk" in goal or "gain" in goal:
        if avg_protein < 120:
            flags.append(f"Avg protein ({avg_protein:.0f}g) too low for muscle gain goal (target: 120g+).")
        if avg_calories < 2400:
            flags.append(f"Avg calories ({avg_calories:.0f}) too low for a caloric surplus.")

    elif "maintenance" in goal:
        if avg_calories < 1600 or avg_calories > 2800:
            flags.append(f"Avg calories ({avg_calories:.0f}) outside healthy maintenance range.")

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
    judge = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION)

    system = "You are a certified registered dietitian evaluating meal plans. Be strict and precise."
    prompt = f"""Evaluate this meal plan for a user with goal: '{user_goal}' and restrictions: '{restrictions or "none"}'.

MEAL PLAN:
{meal_plan}

Score on these four criteria and respond ONLY in valid JSON — no markdown, no explanation outside the JSON:
{{
  "macro_balance": <0-3, does it hit appropriate macros for the goal?>,
  "variety": <0-3, nutritional diversity across food groups?>,
  "feasibility": <0-2, are these realistic meals a real person would make?>,
  "safety": <0-2, does it meet minimum daily calorie and nutrient thresholds?>,
  "score": <sum of all four, 0-10>,
  "reasoning": "<one sentence on the biggest strength or weakness>",
  "pass": <true if score >= 7, false otherwise>
}}"""

    try:
        response = judge.invoke([HumanMessage(content=prompt)], config={"system": system})
        return json.loads(response.content)
    except json.JSONDecodeError:
        return {"error": "Judge returned invalid JSON", "score": 0, "pass": False}
    except Exception as e:
        return {"error": f"Eval failed: {str(e)}", "score": 0, "pass": False}


# ── INTAKE AGENT TOOLS ────────────────────────────────────────────────────────

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
    Log a meal to the database. For best deficiency tracking, call get_nutrition_info
    first to get iron_mg and fiber_g values — don't guess them.
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
    Returns a list of deficient nutrients with percentage of RDA and recommendations.
    """
    patterns = db.get_nutrition_patterns(user_id, window_days=days)
    if not patterns:
        return {"deficiencies": [], "reason": "No meal data found in the given window."}

    n = len(patterns)
    avg_protein = sum(r["daily_protein"] or 0 for r in patterns) / n
    avg_iron = sum(r["daily_iron"] or 0 for r in patterns) / n

    deficiencies = []

    for nutrient, avg_val in [("protein", avg_protein), ("iron", avg_iron)]:
        check = validate_against_rda.invoke({"nutrient": nutrient, "daily_amount": avg_val})
        if check.get("status") in ("low", "deficient"):
            deficiencies.append({
                "nutrient": nutrient,
                "status": check["status"],
                "percentage_of_rda": check["percentage_of_rda"],
                "avg_daily": round(avg_val, 2),
                "rda_target": check["rda"],
                "unit": check["unit"],
            })

    return {
        "deficiencies": deficiencies,
        "deficiency_detected": len(deficiencies) > 0,
        "days_analyzed": n,
    }


# ── INSIGHT AGENT TOOLS ───────────────────────────────────────────────────────

@tool
def analyze_nutrition_patterns(user_id: str, window_days: int = 14) -> dict:
    """
    Longitudinal analysis of the user's nutrition over N days.
    Detects low-calorie streaks, iron concerns, and sets medical_flag if needed.
    The supervisor checks this on every turn to decide if insight_agent should intervene.
    """
    patterns = db.get_nutrition_patterns(user_id, window_days=window_days)
    if not patterns:
        return {"has_data": False, "reason": "No meal data in the analysis window."}

    n = len(patterns)
    calorie_series = [r["daily_calories"] or 0 for r in patterns]
    avg_cal = sum(calorie_series) / n
    avg_iron = sum(r["daily_iron"] or 0 for r in patterns) / n

    # Count consecutive low-calorie days starting from most recent
    low_cal_streak = 0
    for cal in calorie_series:  # ordered DESC from db
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
        # Flags that insight_agent uses to decide whether to intervene
        "medical_flag": low_cal_streak >= 3,       # 3+ days under 1200 kcal
        "iron_concern": avg_iron < 9.0,             # below 50% of RDA
        "calorie_concern": avg_cal < 1400,
    }


@tool
def track_streaks(user_id: str) -> dict:
    """
    Track the user's logging streak and 30-day adherence rate.
    Used by insight_agent to motivate consistent tracking.
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
    
    
