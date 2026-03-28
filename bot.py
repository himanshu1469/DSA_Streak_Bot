import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
from database import Database
from scheduler import setup_scheduler
from role_manager import assign_roles

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 0))

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
db = Database()


@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online!")
    await db.init()
    setup_scheduler(bot, db)
    try:
        guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} command(s) to guild.")
    except Exception as e:
        print(f"Sync error: {e}")


# ─── /log ─────────────────────────────────────────────────────────────────────

@bot.tree.command(
    name="log",
    description="Log your study session for today",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(
    category="What did you study?",
    questions="Number of DSA questions solved (0 if none)",
    platform="Platform you used (LeetCode, GFG, etc.)",
    topics="Topics covered, e.g. 'trees, dp, graphs'",
    difficulty="Difficulty mix, e.g. 'easy:2 medium:3'",
    notes="Optional notes about today's session"
)
@app_commands.choices(
    category=[
        app_commands.Choice(name="DSA",           value="dsa"),
        app_commands.Choice(name="System Design", value="system_design"),
        app_commands.Choice(name="Both",          value="both"),
    ],
    platform=[
        app_commands.Choice(name="LeetCode",       value="LeetCode"),
        app_commands.Choice(name="GeeksForGeeks",  value="GFG"),
        app_commands.Choice(name="HackerRank",     value="HackerRank"),
        app_commands.Choice(name="Codeforces",     value="Codeforces"),
        app_commands.Choice(name="InterviewBit",   value="InterviewBit"),
        app_commands.Choice(name="AlgoExpert",     value="AlgoExpert"),
        app_commands.Choice(name="Neetcode",       value="Neetcode"),
        app_commands.Choice(name="Multiple / Other", value="Multiple"),
    ]
)
async def log_study(
    interaction: discord.Interaction,
    category: app_commands.Choice[str],
    questions: int = 0,
    platform: app_commands.Choice[str] = None,
    topics: str = "",
    difficulty: str = "",
    notes: str = ""
):
    await interaction.response.defer()   # gives us time for DB + role ops

    user_id = str(interaction.user.id)
    username = interaction.user.display_name
    platform_val = platform.value if platform else ""

    result = await db.log_session(
        user_id=user_id,
        username=username,
        category=category.value,
        questions=questions,
        topics=topics,
        difficulty=difficulty,
        platform=platform_val,
        notes=notes
    )

    streak = result["streak"]
    total_questions = result["total_questions"]
    is_new_log = result["is_new_log"]

    if not is_new_log:
        await interaction.followup.send(
            f"📝 Updated your log for today, **{username}**!", ephemeral=True
        )
        return

    # ── Role assignment ───────────────────────────────────────────────────────
    newly_earned_roles = []
    try:
        member = interaction.guild.get_member(int(user_id))
        if member:
            newly_earned_roles = await assign_roles(member, streak, total_questions)
    except Exception as e:
        print(f"Role assignment error for {username}: {e}")

    # ── Build embed ───────────────────────────────────────────────────────────
    embed = discord.Embed(title="📚 Study Session Logged!", color=discord.Color.green())
    embed.set_author(name=username, icon_url=interaction.user.display_avatar.url)

    if category.value in ("dsa", "both") and questions > 0:
        embed.add_field(name="❓ Questions", value=str(questions), inline=True)

    embed.add_field(name="📂 Category", value=category.name, inline=True)

    if platform_val:
        embed.add_field(name="🖥️ Platform", value=platform_val, inline=True)

    if topics:
        embed.add_field(name="🏷️ Topics", value=topics, inline=True)

    if difficulty:
        embed.add_field(name="⚡ Difficulty", value=difficulty, inline=True)

    streak_emoji = "🔥" if streak >= 3 else "✅"
    embed.add_field(
        name=f"{streak_emoji} Streak",
        value=f"**{streak} day{'s' if streak != 1 else ''}**",
        inline=True
    )
    embed.add_field(name="📊 Total Questions", value=str(total_questions), inline=True)

    if notes:
        embed.add_field(name="📝 Notes", value=notes, inline=False)

    # ── Milestone + role messages ─────────────────────────────────────────────
    milestone_lines = []
    if streak == 7:
        milestone_lines.append("🎉 **ONE WEEK STREAK!** Incredible consistency! 🔥")
    elif streak == 14:
        milestone_lines.append("⚡ **TWO WEEK STREAK!** You're unstoppable!")
    elif streak == 30:
        milestone_lines.append("🏆 **30-DAY STREAK!** Absolute beast mode! 👑")
    elif streak == 60:
        milestone_lines.append("🔱 **60 DAYS!** Elite level consistency!")
    elif streak == 100:
        milestone_lines.append("💎 **100 DAYS!** Legendary. Built different. 💪")

    if total_questions == 50:
        milestone_lines.append("🎯 **50 questions solved!** Halfway to the century!")
    elif total_questions == 100:
        milestone_lines.append("🚀 **100 questions solved!** DSA machine!")
    elif total_questions == 250:
        milestone_lines.append("🧠 **250 questions!** DSA Veteran status unlocked!")
    elif total_questions == 500:
        milestone_lines.append("👑 **500 questions!** Absolute Leetcode Lord!")

    for role_name in newly_earned_roles:
        milestone_lines.append(f"🏅 **New role unlocked:** {role_name}")

    embed.set_footer(text="Keep grinding! 💪")

    extra = ("\n\n" + "\n".join(milestone_lines)) if milestone_lines else ""
    content = f"<@{user_id}> logged their session!{extra}"

    await interaction.followup.send(content=content, embed=embed)


# ─── /streak ──────────────────────────────────────────────────────────────────

@bot.tree.command(
    name="streak",
    description="Check your or someone else's current streak",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(user="Leave empty to check your own streak")
async def streak_cmd(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    data = await db.get_user_stats(str(target.id))

    if not data:
        await interaction.response.send_message(
            f"{target.display_name} hasn't logged anything yet!", ephemeral=True
        )
        return

    streak_val = data["streak"]
    fire = "🔥" * min(streak_val // 3 + 1, 5)

    embed = discord.Embed(title=f"{fire} {target.display_name}'s Stats", color=discord.Color.orange())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="🔥 Current Streak", value=f"**{streak_val} day{'s' if streak_val != 1 else ''}**", inline=True)
    embed.add_field(name="❓ Total Questions", value=str(data["total_questions"]), inline=True)
    embed.add_field(name="📅 Active Days",     value=str(data["total_days"]),      inline=True)

    if data.get("last_log_date"):
        embed.set_footer(text=f"Last logged: {data['last_log_date']}")

    await interaction.response.send_message(embed=embed)


# ─── /stats ───────────────────────────────────────────────────────────────────

@bot.tree.command(
    name="stats",
    description="View your detailed study stats",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(user="Leave empty to check your own stats")
async def stats_cmd(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    data = await db.get_detailed_stats(str(target.id))

    if not data:
        await interaction.response.send_message(
            f"{target.display_name} hasn't logged anything yet!", ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"📊 {target.display_name}'s Study Dashboard",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=target.display_avatar.url)

    embed.add_field(name="🔥 Streak",      value=f"**{data['streak']}d**",     inline=True)
    embed.add_field(name="🏅 Best Streak", value=f"{data['best_streak']} days", inline=True)
    embed.add_field(name="❓ Total Q's",   value=str(data['total_questions']),  inline=True)
    embed.add_field(name="📅 Active Days", value=str(data['total_days']),       inline=True)
    embed.add_field(name="📆 This Week",   value=f"{data['week_questions']} Qs",inline=True)
    embed.add_field(name="📆 This Month",  value=f"{data['month_questions']} Qs",inline=True)

    if data.get("top_topics"):
        embed.add_field(name="🔝 Top Topics", value=data["top_topics"], inline=False)

    embed.set_footer(text="Every day counts. 🚀")
    await interaction.response.send_message(embed=embed)


# ─── /platforms ───────────────────────────────────────────────────────────────

@bot.tree.command(
    name="platforms",
    description="See your question breakdown by platform",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(user="Leave empty to check your own platform stats")
async def platforms_cmd(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    rows = await db.get_platform_stats(str(target.id))

    if not rows:
        await interaction.response.send_message(
            f"{target.display_name} hasn't logged any platform data yet!\n"
            f"Use `/log` and pick a platform next time. 🖥️",
            ephemeral=True
        )
        return

    total = sum(r["total"] for r in rows)
    platform_emojis = {
        "LeetCode":    "🟡",
        "GFG":         "🟢",
        "HackerRank":  "🟢",
        "Codeforces":  "🔵",
        "InterviewBit":"🟠",
        "AlgoExpert":  "🔴",
        "Neetcode":    "🟣",
        "Multiple":    "🌐",
    }

    lines = []
    for row in rows:
        pct = round(row["total"] / total * 100) if total else 0
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        emoji = platform_emojis.get(row["platform"], "⚪")
        lines.append(f"{emoji} **{row['platform']}** — {row['total']} Qs ({pct}%)\n`{bar}`")

    embed = discord.Embed(
        title=f"🖥️ {target.display_name}'s Platform Breakdown",
        description="\n\n".join(lines),
        color=discord.Color.teal()
    )
    embed.set_footer(text=f"Total: {total} questions across {len(rows)} platform{'s' if len(rows) != 1 else ''}")
    await interaction.response.send_message(embed=embed)


# ─── /roles ───────────────────────────────────────────────────────────────────

@bot.tree.command(
    name="roles",
    description="See all milestone roles and how to earn them",
    guild=discord.Object(id=GUILD_ID)
)
async def roles_info(interaction: discord.Interaction):
    from roles_config import STREAK_ROLES, QUESTION_ROLES

    member_role_names = [r.name for r in interaction.user.roles]

    embed = discord.Embed(
        title="🏅 Milestone Roles — How to Earn Them",
        description=(
            "Roles are **auto-assigned** when you `/log` and hit a threshold.\n"
            "You'll always hold only your **highest tier** — roles upgrade automatically.\n"
            "✅ = already earned · ⬜ = not yet"
        ),
        color=discord.Color.purple()
    )

    streak_lines = []
    for days, name in STREAK_ROLES:
        tick = "✅" if name in member_role_names else "⬜"
        streak_lines.append(f"{tick} **{name}** — {days}-day streak")
    embed.add_field(name="🔥 Streak Roles", value="\n".join(streak_lines), inline=False)

    q_lines = []
    for count, name in QUESTION_ROLES:
        tick = "✅" if name in member_role_names else "⬜"
        q_lines.append(f"{tick} **{name}** — {count} questions solved")
    embed.add_field(name="❓ Question Roles", value="\n".join(q_lines), inline=False)

    embed.set_footer(text="Roles are checked on every /log entry 🚀")
    await interaction.response.send_message(embed=embed)


# ─── /leaderboard ─────────────────────────────────────────────────────────────

@bot.tree.command(
    name="leaderboard",
    description="View the study leaderboard",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(period="Time period for the leaderboard")
@app_commands.choices(period=[
    app_commands.Choice(name="Weekly",   value="weekly"),
    app_commands.Choice(name="Monthly",  value="monthly"),
    app_commands.Choice(name="All Time", value="alltime"),
    app_commands.Choice(name="Streaks",  value="streaks"),
])
async def leaderboard(interaction: discord.Interaction, period: app_commands.Choice[str] = None):
    period_val  = period.value if period else "weekly"
    period_name = period.name  if period else "Weekly"
    rows = await db.get_leaderboard(period_val)

    if not rows:
        await interaction.response.send_message("No data yet! Start logging with `/log`.", ephemeral=True)
        return

    medals = ["🥇", "🥈", "🥉"]
    embed = discord.Embed(title=f"🏆 {period_name} Leaderboard", color=discord.Color.gold())

    lines = []
    for i, row in enumerate(rows[:10]):
        medal = medals[i] if i < 3 else f"`#{i+1}`"
        value_str = (
            f"🔥 {row['value']} day streak" if period_val == "streaks"
            else f"❓ {row['value']} questions"
        )
        lines.append(f"{medal} **{row['username']}** — {value_str}")

    embed.description = "\n".join(lines)
    embed.set_footer(text="Grind harder! 💪 Use /log to update your stats.")
    await interaction.response.send_message(embed=embed)


# ─── /goal ────────────────────────────────────────────────────────────────────

@bot.tree.command(
    name="goal",
    description="Set your daily question goal",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(questions_per_day="How many questions do you want to solve each day?")
async def set_goal(interaction: discord.Interaction, questions_per_day: int):
    user_id  = str(interaction.user.id)
    username = interaction.user.display_name
    await db.set_goal(user_id, username, questions_per_day)

    embed = discord.Embed(
        title="🎯 Goal Set!",
        description=f"**{username}**, your daily goal is now **{questions_per_day} question{'s' if questions_per_day != 1 else ''}** per day.",
        color=discord.Color.purple()
    )
    embed.set_footer(text="Stay consistent. Track with /log every day!")
    await interaction.response.send_message(embed=embed)


# ─── /reminder ────────────────────────────────────────────────────────────────

@bot.tree.command(
    name="reminder",
    description="Toggle daily DM reminders for yourself",
    guild=discord.Object(id=GUILD_ID)
)
async def toggle_reminder(interaction: discord.Interaction):
    user_id  = str(interaction.user.id)
    username = interaction.user.display_name
    is_on = await db.toggle_reminder(user_id, username)
    status = "✅ enabled" if is_on else "❌ disabled"

    await interaction.response.send_message(
        f"DM reminders **{status}** for you, {username}!\n"
        + ("You'll get a daily ping at 9 PM IST if you haven't logged." if is_on else "No more DM reminders."),
        ephemeral=True
    )


# ─── /missed ──────────────────────────────────────────────────────────────────

@bot.tree.command(
    name="missed",
    description="See who hasn't logged today (gentle accountability 👀)",
    guild=discord.Object(id=GUILD_ID)
)
async def missed(interaction: discord.Interaction):
    missed_users = await db.get_missed_today()

    if not missed_users:
        await interaction.response.send_message("🎉 Everyone has logged today! Amazing group!")
        return

    mentions = ", ".join([f"<@{uid}>" for uid in missed_users])
    embed = discord.Embed(
        title="👀 Slackers Alert",
        description=f"These people haven't logged today yet:\n\n{mentions}\n\nDon't break your streak! Use `/log` now 🔥",
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed)


bot.run(TOKEN)
