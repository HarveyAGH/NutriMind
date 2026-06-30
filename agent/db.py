import os
import logging

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

DB_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/nutrimind"
)
_checkpoint_pool = None
_checkpointer = None
_data_pool = None

logger = logging.getLogger(__name__)


def _get_data_pool():
    global _data_pool
    if _data_pool is None:
        _data_pool = ConnectionPool(DB_URL, max_size=10, kwargs={"autocommit": True})
    return _data_pool


def get_connection():
    return _get_data_pool().connection()


def get_checkpointer() -> PostgresSaver:
    global _checkpoint_pool, _checkpointer

    if _checkpoint_pool is None:
        _checkpoint_pool = ConnectionPool(
            DB_URL,
            max_size=20,
            kwargs={"autocommit": True},
        )

    if _checkpointer is None:
        _checkpointer = PostgresSaver(_checkpoint_pool)
        _checkpointer.setup()

    return _checkpointer


def setup_tables():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        user_id TEXT PRIMARY KEY,
                        age INT,
                        weight FLOAT,
                        height FLOAT,
                        goal TEXT,
                        restrictions TEXT,
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS meal_logs (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT,
                        food TEXT,
                        calories INT,
                        macros JSONB,
                        logged_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                conn.commit()
        logger.info("Database tables ready.")
    except Exception as e:
        logger.error("Failed to set up tables: %s", e)
        raise


def get_user_profile(user_id: str) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM user_profiles WHERE user_id = %s", (user_id,))
            result = cur.fetchone()
            return result if result else {}


def upsert_user_profile(user_id: str, data: dict) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_profiles (user_id, age, weight, height, goal, restrictions, updated_at)
                VALUES (%(user_id)s, %(age)s, %(weight)s, %(height)s, %(goal)s, %(restrictions)s, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    age = EXCLUDED.age,
                    weight = EXCLUDED.weight,
                    height = EXCLUDED.height,
                    goal = EXCLUDED.goal,
                    restrictions = EXCLUDED.restrictions,
                    updated_at = NOW()
            """,
                {**data, "user_id": user_id},
            )
            conn.commit()
            return True


def log_meal(user_id: str, food: str, calories: int, macros: dict) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO meal_logs (user_id, food, calories, macros)
                VALUES (%s, %s, %s, %s)
            """,
                (user_id, food, calories, psycopg.types.json.Jsonb(macros)),
            )
            conn.commit()
            return True


def get_meal_history(user_id: str, days: int = 7) -> list:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT food, calories, macros, logged_at
                FROM meal_logs
                WHERE user_id = %s
                AND logged_at >= NOW() - (INTERVAL '1 day' * %s)
                ORDER BY logged_at DESC
            """,
                (user_id, days),
            )
            return cur.fetchall()


def calculate_running_macros(user_id: str) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    COALESCE(SUM(calories), 0) as total_calories,
                    COALESCE(SUM((macros->>'protein')::float), 0) as total_protein,
                    COALESCE(SUM((macros->>'carbs')::float), 0) as total_carbs,
                    COALESCE(SUM((macros->>'fat')::float), 0) as total_fat
                FROM meal_logs
                WHERE user_id = %s
                AND logged_at::date = CURRENT_DATE
            """,
                (user_id,),
            )
            return cur.fetchone() or {}


def get_nutrition_patterns(user_id: str, window_days: int = 14) -> list:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    logged_at::date as date,
                    SUM(calories) as daily_calories,
                    SUM((macros->>'protein')::float) as daily_protein,
                    SUM((macros->>'iron')::float) as daily_iron
                FROM meal_logs
                WHERE user_id = %s
                AND logged_at >= NOW() - (INTERVAL '1 day' * %s)
                GROUP BY logged_at::date
                ORDER BY date DESC
            """,
                (user_id, window_days),
            )
            return cur.fetchall()


if __name__ == "__main__":
    setup_tables()
