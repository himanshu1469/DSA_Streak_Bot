from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import discord
import os
import pytz

IST = pytz.timezone("Asia/Kolkata")
REMINDER_CHANNEL_ID = int(os.getenv("REMINDER_CHANNEL_ID", 0))


def setup_scheduler(bot, db):
    scheduler = AsyncIOScheduler(timezone=IST)

    # ── Daily reminder at 9 PM IST ──────────────────────────────────────────
    @scheduler.scheduled_job(CronTrigger(hour=21, minute=0, timezone=IST))
    async def send_daily_reminders():
        channel = bot.get_channel(REMINDER_CHANNEL_ID)

        # DM reminders (opt-in)
        user_ids = await db.get_reminder_users()
        for uid in user_ids:
            try:
                user = await bot.fetch_user(int(uid))
                await user.send(
                    "🔔 **Daily Reminder!**\n\n"
                    "You haven't logged your study session today yet.\n"
                    "Head back to the server and use `/log` to keep your streak alive! 🔥"
                )
            except Exception:
                pass  # User has DMs closed

        # Channel ping for everyone
        if channel:
            missed = await db.get_missed_today()
            if missed:
                mentions = " ".join([f"<@{uid}>" for uid in missed])
                await channel.send(
                    f"⏰ **9 PM Check-in!**\n\n"
                    f"{mentions}\n\n"
                    f"You haven't logged today! Use `/log` before midnight to keep your streak. 🔥"
                )
            else:
                await channel.send(
                    "✅ **Everyone has logged today! Amazing group consistency!** 🎉\n"
                    "Keep it up tomorrow too! 💪"
                )

    # ── Weekly digest every Sunday at 8 PM IST ───────────────────────────────
    @scheduler.scheduled_job(CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=IST))
    async def send_weekly_digest():
        channel = bot.get_channel(REMINDER_CHANNEL_ID)
        if not channel:
            return

        data = await db.get_weekly_digest()
        top_q = data["top_questions"]
        top_s = data["top_streaks"]

        embed = discord.Embed(
            title="📊 Weekly Digest — How Did We Do?",
            description="Here's how the grind went this week 👇",
            color=discord.Color.gold()
        )

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        q_lines = []
        for i, row in enumerate(top_q):
            if row["value"] > 0:
                q_lines.append(f"{medals[i]} **{row['username']}** — {row['value']} questions")
        if q_lines:
            embed.add_field(name="🔝 Top Question Solvers", value="\n".join(q_lines), inline=False)

        s_lines = []
        for i, row in enumerate(top_s[:3]):
            s_lines.append(f"{medals[i]} **{row['username']}** — 🔥 {row['streak']} day streak")
        if s_lines:
            embed.add_field(name="🔥 Top Streaks", value="\n".join(s_lines), inline=False)

        embed.set_footer(text="New week, new grind. Use /log every day! 💪")
        await channel.send(content="📢 **Weekly Digest is here!**", embed=embed)

    scheduler.start()
    print("✅ Scheduler started (IST timezone).")
