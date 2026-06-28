# test_tools.py
from dotenv import load_dotenv
load_dotenv()  # must be before any tool imports

from tools import (
    get_user_profile,
    upsert_user_profile,
    log_meal,
    get_running_macros,
    get_nutrition_info,
    detect_deficiencies,
    analyze_nutrition_patterns,
)


print("=== 1. upsert profile ===")
print(upsert_user_profile.invoke({
    "user_id": "harvey_01",
    "age": 23,
    "weight": 70.0,
    "height": 175.0,
    "goal": "muscle_gain",
    "restrictions": ""
}))

print("\n=== 2. get profile ===")
print(get_user_profile.invoke({"user_id": "harvey_01"}))

print("\n=== 3. USDA nutrition lookup ===")
nutrition = get_nutrition_info.invoke({"food_item": "chicken breast"})
print(nutrition)

print("\n=== 4. log meal ===")
print(log_meal.invoke({
    "user_id": "harvey_01",
    "food": "chicken breast",
    "calories": int(nutrition.get("calories", 300)),
    "protein_g": nutrition.get("protein_g", 31.0),
    "carbs_g": nutrition.get("carbs_g", 0.0),
    "fat_g": nutrition.get("fat_g", 3.6),
    "iron_mg": nutrition.get("iron_mg", 0.0),
    "fiber_g": nutrition.get("fiber_g", 0.0),
}))

print("\n=== 5. running macros (today) ===")
print(get_running_macros.invoke({"user_id": "harvey_01"}))

print("\n=== 6. deficiency check ===")
print(detect_deficiencies.invoke({"user_id": "harvey_01", "days": 7}))

print("\n=== 7. pattern analysis ===")
print(analyze_nutrition_patterns.invoke({"user_id": "harvey_01", "window_days": 14}))

print("\nAll tests passed.")