# role_manager.py
# Handles all Discord role assignment for streak + question milestones.
# Auto-upgrades: member always holds only their HIGHEST earned tier.

import discord
from roles_config import (
    STREAK_ROLES, QUESTION_ROLES,
    ALL_STREAK_ROLE_NAMES, ALL_QUESTION_ROLE_NAMES
)


def _get_earned_role_name(value: int, tiers: list):
    """Return the highest tier role name the user qualifies for."""
    earned = None
    for threshold, name in tiers:
        if value >= threshold:
            earned = name
    return earned


async def _ensure_role_exists(guild: discord.Guild, role_name: str):
    """Get role by name, create it if missing."""
    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        try:
            role = await guild.create_role(
                name=role_name,
                reason="StudyStreak bot — auto-created milestone role"
            )
        except discord.Forbidden:
            print(f"⚠️  Missing 'Manage Roles' permission — could not create role: {role_name}")
            return None
    return role


async def assign_roles(
    member: discord.Member,
    streak: int,
    total_questions: int,
) -> list[str]:
    """
    Assign/upgrade streak and question milestone roles for a member.
    Returns list of newly earned role names (empty if no change).
    """
    guild = member.guild
    newly_earned = []

    # ── Streak roles ─────────────────────────────────────────────────────────
    earned_streak = _get_earned_role_name(streak, STREAK_ROLES)
    await _handle_role_tier(
        member, guild,
        earned_name=earned_streak,
        all_names=ALL_STREAK_ROLE_NAMES,
        newly_earned=newly_earned
    )

    # ── Question roles ────────────────────────────────────────────────────────
    earned_q = _get_earned_role_name(total_questions, QUESTION_ROLES)
    await _handle_role_tier(
        member, guild,
        earned_name=earned_q,
        all_names=ALL_QUESTION_ROLE_NAMES,
        newly_earned=newly_earned
    )

    return newly_earned


async def _handle_role_tier(
    member: discord.Member,
    guild: discord.Guild,
    earned_name,
    all_names: list[str],
    newly_earned: list[str],
):
    """
    For a given role category:
    - Remove all lower/old tier roles the member already holds
    - Add the highest earned tier if they don't already have it
    """
    if earned_name is None:
        return

    # Roles the member currently holds in this category
    current_category_roles = [r for r in member.roles if r.name in all_names]
    already_has_top = any(r.name == earned_name for r in current_category_roles)

    if already_has_top:
        return  # Nothing to change

    # Remove lower-tier roles they already have
    to_remove = [r for r in current_category_roles if r.name != earned_name]
    if to_remove:
        try:
            await member.remove_roles(*to_remove, reason="StudyStreak role upgrade")
        except discord.Forbidden:
            print(f"⚠️  Can't remove roles from {member.display_name} — check role hierarchy")

    # Add the new top-tier role
    new_role = await _ensure_role_exists(guild, earned_name)
    if new_role:
        try:
            await member.add_roles(new_role, reason="StudyStreak milestone achieved")
            newly_earned.append(earned_name)
        except discord.Forbidden:
            print(f"⚠️  Can't add role {earned_name} to {member.display_name} — check role hierarchy")
