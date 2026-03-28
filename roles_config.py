# roles_config.py
# ─────────────────────────────────────────────────────────────────────────────
# Central config for streak milestone roles and question milestone roles.
# Each entry maps a threshold → role name shown in Discord.
#
# HOW TO USE:
#   1. Create these roles in your Discord server (Server Settings → Roles)
#      with whatever color/icon you like.
#   2. Make sure the bot's role is positioned ABOVE all these roles in the
#      role hierarchy, otherwise it can't assign them.
#   3. The bot auto-assigns AND auto-upgrades roles — members will only ever
#      hold the highest tier they've earned.
# ─────────────────────────────────────────────────────────────────────────────

# Streak-based roles  (streak days → role name)
STREAK_ROLES = [
    (3,   "🌱 Seedling"),       # 3-day streak
    (7,   "🔥 Week Warrior"),   # 7-day streak
    (14,  "⚡ Fortnight Force"),# 14-day streak
    (30,  "💪 Monthly Grinder"),# 30-day streak
    (60,  "🏆 60-Day Beast"),   # 60-day streak
    (100, "💎 Century Coder"),  # 100-day streak
]

# Question-count roles  (total questions solved → role name)
QUESTION_ROLES = [
    (25,  "🧩 Problem Starter"),
    (50,  "🎯 Fifty Club"),
    (100, "🚀 Century Solver"),
    (250, "🧠 DSA Veteran"),
    (500, "👑 Leetcode Lord"),
]

# All role names flat (used for cleanup — remove lower tiers on upgrade)
ALL_STREAK_ROLE_NAMES  = [r for _, r in STREAK_ROLES]
ALL_QUESTION_ROLE_NAMES = [r for _, r in QUESTION_ROLES]
