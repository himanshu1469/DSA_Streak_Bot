# 📚 StudyStreak — Discord Bot for SDE Prep Groups

A Discord bot for tracking daily DSA + System Design study sessions, streaks, leaderboards, and keeping your prep group accountable.

---

## ✨ Features

| Command | Description |
|---|---|
| `/log` | Log your daily study session (questions, topics, difficulty) |
| `/streak [@user]` | Check your or someone's current streak |
| `/stats [@user]` | Detailed personal dashboard |
| `/leaderboard [period]` | Weekly / Monthly / All-time / Streak leaderboard |
| `/goal <n>` | Set your daily question target |
| `/reminder` | Toggle daily DM reminders |
| `/missed` | See who hasn't logged today 👀 |

**Automated:**
- 🔔 Daily reminder ping at **9 PM IST** (channel + DM for opted-in users)
- 📊 **Weekly digest** every Sunday at 8 PM IST
- 🎉 Milestone announcements (7-day, 30-day, 100-day streaks, 100 questions)

---

## 🚀 Setup Guide

### Step 1 — Create the Discord Bot

1. Go to https://discord.com/developers/applications
2. Click **"New Application"** → give it a name (e.g., `StudyStreak`)
3. Go to **Bot** tab → click **"Add Bot"**
4. Under **Token**, click **"Reset Token"** → copy it (this is your `DISCORD_TOKEN`)
5. Enable these **Privileged Gateway Intents**:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
6. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Read Messages/View Channels`, `Embed Links`, `Mention Everyone`
7. Copy the generated URL and open it → add the bot to your server

### Step 2 — Enable Developer Mode in Discord

- Discord Settings → Advanced → **Developer Mode ON**
- Right-click your server → **Copy Server ID** → this is `GUILD_ID`
- Right-click the channel for reminders → **Copy Channel ID** → this is `REMINDER_CHANNEL_ID`

### Step 3 — Set Up PostgreSQL (Free Options)

**Option A: Railway (Recommended — same place you host the bot)**
1. Go to https://railway.app → create account
2. New Project → **Add PostgreSQL**
3. Click the PostgreSQL service → **Variables** tab → copy `DATABASE_URL`

**Option B: Neon (Free tier, generous)**
1. Go to https://neon.tech → create account
2. New Project → copy the connection string

**Option C: Supabase**
1. Go to https://supabase.com → new project
2. Settings → Database → copy the URI (use the "pooled" one)

### Step 4 — Local Setup

```bash
git clone <your-repo>
cd discord_bot

# Create virtual environment
python -m venv venv
source venv/bin/activate       # Mac/Linux
venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Fill in DISCORD_TOKEN, GUILD_ID, REMINDER_CHANNEL_ID, DATABASE_URL

# Run the bot
python bot.py
```

You should see:
```
✅ Database connected and tables ready.
✅ Scheduler started (IST timezone).
✅ StudyStreak#1234 is online!
Synced 7 command(s) to guild.
```

### Step 5 — Deploy to Railway (Free Hosting)

1. Push your code to a **GitHub repo** (don't commit `.env`!)
2. Go to https://railway.app → New Project → **Deploy from GitHub**
3. Select your repo
4. Add environment variables: `DISCORD_TOKEN`, `GUILD_ID`, `REMINDER_CHANNEL_ID`, `DATABASE_URL`
5. Railway will auto-detect `Procfile` and run `python bot.py`

✅ Bot stays online 24/7 for free.

---

## 📁 Project Structure

```
discord_bot/
├── bot.py           # Main bot file — all slash commands
├── database.py      # All PostgreSQL queries (asyncpg)
├── scheduler.py     # Daily reminders + weekly digest (APScheduler)
├── requirements.txt
├── Procfile         # For Railway deployment
├── .env.example     # Copy to .env and fill in values
└── README.md
```

---

## 🛠️ Customization Tips

- **Change reminder time**: Edit `hour=21` in `scheduler.py` (24h IST format)
- **Add platforms** (LeetCode, GFG, etc.): Add a `platform` field to `/log` and `study_logs` table
- **Add topic autocomplete**: Use `@app_commands.autocomplete` for the `topics` field
- **Role rewards**: Use `guild.get_member(user_id).add_roles(...)` to assign roles at streak milestones

---

## 🗄️ Database Schema

```sql
-- Users table (one row per person)
users (user_id, username, streak, best_streak, total_questions, total_days, last_log_date, goal_per_day, reminder_on)

-- Daily logs (one row per person per day, upsertable)
study_logs (id, user_id, log_date, category, questions, topics, difficulty, notes, logged_at)
```
