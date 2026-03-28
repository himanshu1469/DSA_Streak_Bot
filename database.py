import asyncpg
import os
from datetime import date, timedelta
from collections import Counter


class Database:
    def __init__(self):
        self.pool = None

    async def init(self):
        self.pool = await asyncpg.create_pool(dsn=os.getenv("DATABASE_URL"))
        await self._create_tables()
        print("✅ Database connected and tables ready.")

    async def _create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id     TEXT PRIMARY KEY,
                    username    TEXT NOT NULL,
                    streak      INT DEFAULT 0,
                    best_streak INT DEFAULT 0,
                    total_questions INT DEFAULT 0,
                    total_days  INT DEFAULT 0,
                    last_log_date DATE,
                    goal_per_day INT DEFAULT 0,
                    reminder_on BOOLEAN DEFAULT FALSE
                );

                CREATE TABLE IF NOT EXISTS study_logs (
                    id          SERIAL PRIMARY KEY,
                    user_id     TEXT NOT NULL,
                    log_date    DATE NOT NULL,
                    category    TEXT NOT NULL,
                    questions   INT DEFAULT 0,
                    topics      TEXT DEFAULT '',
                    difficulty  TEXT DEFAULT '',
                    platform    TEXT DEFAULT '',
                    notes       TEXT DEFAULT '',
                    logged_at   TIMESTAMP DEFAULT NOW(),
                    UNIQUE(user_id, log_date)
                );

                -- Migration safety: add platform column if upgrading from older schema
                ALTER TABLE study_logs ADD COLUMN IF NOT EXISTS platform TEXT DEFAULT '';
            """)

    # ─── Logging ──────────────────────────────────────────────────────────────

    async def log_session(self, user_id, username, category, questions, topics, difficulty, platform, notes):
        today = date.today()

        async with self.pool.acquire() as conn:
            # Upsert user
            await conn.execute("""
                INSERT INTO users (user_id, username)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET username = $2
            """, user_id, username)

            # Check if already logged today
            existing = await conn.fetchrow(
                "SELECT id FROM study_logs WHERE user_id=$1 AND log_date=$2",
                user_id, today
            )

            if existing:
                # Update existing log
                await conn.execute("""
                    UPDATE study_logs
                    SET category=$3, questions=$4, topics=$5, difficulty=$6, platform=$7, notes=$8
                    WHERE user_id=$1 AND log_date=$2
                """, user_id, today, category, questions, topics, difficulty, platform, notes)

                user = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
                return {
                    "streak": user["streak"],
                    "total_questions": user["total_questions"],
                    "is_new_log": False
                }

            # Insert new log
            await conn.execute("""
                INSERT INTO study_logs (user_id, log_date, category, questions, topics, difficulty, platform, notes)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, user_id, today, category, questions, topics, difficulty, platform, notes)

            # Recalculate streak
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
            last_date = user["last_log_date"]
            current_streak = user["streak"]
            best_streak = user["best_streak"]

            if last_date is None:
                new_streak = 1
            elif last_date == today - timedelta(days=1):
                new_streak = current_streak + 1
            elif last_date == today:
                new_streak = current_streak  # same day, no change
            else:
                new_streak = 1  # streak broken

            new_best = max(best_streak, new_streak)
            new_total_q = user["total_questions"] + questions
            new_total_days = user["total_days"] + 1

            await conn.execute("""
                UPDATE users
                SET streak=$2, best_streak=$3, total_questions=$4,
                    total_days=$5, last_log_date=$6, username=$7
                WHERE user_id=$1
            """, user_id, new_streak, new_best, new_total_q, new_total_days, today, username)

            return {
                "streak": new_streak,
                "total_questions": new_total_q,
                "is_new_log": True
            }

    # ─── Stats ────────────────────────────────────────────────────────────────

    async def get_user_stats(self, user_id):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
            if not row:
                return None
            return dict(row)

    async def get_detailed_stats(self, user_id):
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
            if not user:
                return None

            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            month_start = today.replace(day=1)

            week_q = await conn.fetchval("""
                SELECT COALESCE(SUM(questions), 0) FROM study_logs
                WHERE user_id=$1 AND log_date >= $2
            """, user_id, week_start)

            month_q = await conn.fetchval("""
                SELECT COALESCE(SUM(questions), 0) FROM study_logs
                WHERE user_id=$1 AND log_date >= $2
            """, user_id, month_start)

            # Top topics
            logs = await conn.fetch(
                "SELECT topics FROM study_logs WHERE user_id=$1 AND topics != ''", user_id
            )
            topic_counter = Counter()
            for log in logs:
                for t in log["topics"].split(","):
                    t = t.strip().lower()
                    if t:
                        topic_counter[t] += 1

            top_topics = ", ".join([f"{t} ({c})" for t, c in topic_counter.most_common(5)]) if topic_counter else None

            return {
                "streak": user["streak"],
                "best_streak": user["best_streak"],
                "total_questions": user["total_questions"],
                "total_days": user["total_days"],
                "last_log_date": user["last_log_date"],
                "week_questions": week_q,
                "month_questions": month_q,
                "top_topics": top_topics,
            }

    async def get_platform_stats(self, user_id):
        """Break down total questions by platform for a user."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT platform, SUM(questions) AS total
                FROM study_logs
                WHERE user_id=$1 AND platform != '' AND questions > 0
                GROUP BY platform
                ORDER BY total DESC
            """, user_id)
            return [dict(r) for r in rows]

    # ─── Leaderboard ─────────────────────────────────────────────────────────

    async def get_leaderboard(self, period: str):
        async with self.pool.acquire() as conn:
            today = date.today()

            if period == "streaks":
                rows = await conn.fetch("""
                    SELECT username, streak AS value
                    FROM users
                    WHERE streak > 0
                    ORDER BY streak DESC
                    LIMIT 10
                """)
            elif period == "weekly":
                week_start = today - timedelta(days=today.weekday())
                rows = await conn.fetch("""
                    SELECT u.username, COALESCE(SUM(s.questions), 0) AS value
                    FROM users u
                    LEFT JOIN study_logs s ON u.user_id = s.user_id AND s.log_date >= $1
                    GROUP BY u.username
                    HAVING COALESCE(SUM(s.questions), 0) > 0
                    ORDER BY value DESC
                    LIMIT 10
                """, week_start)
            elif period == "monthly":
                month_start = today.replace(day=1)
                rows = await conn.fetch("""
                    SELECT u.username, COALESCE(SUM(s.questions), 0) AS value
                    FROM users u
                    LEFT JOIN study_logs s ON u.user_id = s.user_id AND s.log_date >= $1
                    GROUP BY u.username
                    HAVING COALESCE(SUM(s.questions), 0) > 0
                    ORDER BY value DESC
                    LIMIT 10
                """, month_start)
            else:  # alltime
                rows = await conn.fetch("""
                    SELECT username, total_questions AS value
                    FROM users
                    WHERE total_questions > 0
                    ORDER BY total_questions DESC
                    LIMIT 10
                """)

            return [dict(r) for r in rows]

    # ─── Goal ────────────────────────────────────────────────────────────────

    async def set_goal(self, user_id, username, questions_per_day):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username, goal_per_day)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE SET goal_per_day=$3, username=$2
            """, user_id, username, questions_per_day)

    # ─── Reminders ───────────────────────────────────────────────────────────

    async def toggle_reminder(self, user_id, username):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username, reminder_on)
                VALUES ($1, $2, TRUE)
                ON CONFLICT (user_id) DO UPDATE SET username=$2
            """, user_id, username)

            current = await conn.fetchval(
                "SELECT reminder_on FROM users WHERE user_id=$1", user_id
            )
            new_val = not current
            await conn.execute(
                "UPDATE users SET reminder_on=$2 WHERE user_id=$1", user_id, new_val
            )
            return new_val

    async def get_reminder_users(self):
        """Users who opted in to reminders AND haven't logged today."""
        today = date.today()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT u.user_id FROM users u
                WHERE u.reminder_on = TRUE
                AND NOT EXISTS (
                    SELECT 1 FROM study_logs s
                    WHERE s.user_id = u.user_id AND s.log_date = $1
                )
            """, today)
            return [r["user_id"] for r in rows]

    async def get_all_known_users(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id FROM users")
            return [r["user_id"] for r in rows]

    async def get_missed_today(self):
        today = date.today()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id FROM users
                WHERE NOT EXISTS (
                    SELECT 1 FROM study_logs s
                    WHERE s.user_id = users.user_id AND s.log_date = $1
                )
            """, today)
            return [r["user_id"] for r in rows]

    async def get_weekly_digest(self):
        """Top 5 users this week + top streak holders."""
        today = date.today()
        week_start = today - timedelta(days=7)
        async with self.pool.acquire() as conn:
            top_q = await conn.fetch("""
                SELECT u.username, COALESCE(SUM(s.questions), 0) AS value
                FROM users u
                LEFT JOIN study_logs s ON u.user_id = s.user_id AND s.log_date >= $1
                GROUP BY u.username
                ORDER BY value DESC LIMIT 5
            """, week_start)

            top_streak = await conn.fetch("""
                SELECT username, streak FROM users
                WHERE streak > 0
                ORDER BY streak DESC LIMIT 3
            """)

            return {"top_questions": [dict(r) for r in top_q], "top_streaks": [dict(r) for r in top_streak]}
