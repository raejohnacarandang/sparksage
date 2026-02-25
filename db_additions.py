# ============================================================
# INSTRUCTIONS: Add the SQL block inside init_db() in db.py,
# after the existing CREATE TABLE statements (before the final
# closing triple-quote). Then append the helper functions below
# to the bottom of db.py.
# ============================================================

# ── 1. ADD THIS SQL INSIDE init_db() ────────────────────────
# Paste this block right before the closing """ of executescript()

SQL_TO_ADD = """
        CREATE TABLE IF NOT EXISTS faqs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            match_keywords TEXT NOT NULL,
            times_used INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS command_permissions (
            command_name TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            role_id TEXT NOT NULL,
            PRIMARY KEY (command_name, guild_id, role_id)
        );

        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            guild_id TEXT,
            channel_id TEXT,
            user_id TEXT,
            provider TEXT,
            tokens_used INTEGER,
            latency_ms INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS channel_prompts (
            channel_id TEXT PRIMARY KEY,
            guild_id TEXT NOT NULL,
            system_prompt TEXT NOT NULL
        );
"""

# ── 2. APPEND THESE HELPER FUNCTIONS TO THE BOTTOM OF db.py ─


# --- FAQ helpers ---

async def get_faqs(guild_id: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM faqs WHERE guild_id = ? ORDER BY id DESC",
        (guild_id,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def add_faq(guild_id: str, question: str, answer: str, keywords: str, created_by: str) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO faqs (guild_id, question, answer, match_keywords, created_by) VALUES (?, ?, ?, ?, ?)",
        (guild_id, question, answer, keywords, created_by),
    )
    await db.commit()
    return cursor.lastrowid


async def delete_faq(faq_id: int, guild_id: str) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM faqs WHERE id = ? AND guild_id = ?",
        (faq_id, guild_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def increment_faq_usage(faq_id: int):
    db = await get_db()
    await db.execute("UPDATE faqs SET times_used = times_used + 1 WHERE id = ?", (faq_id,))
    await db.commit()


# --- Permission helpers ---

async def get_command_permissions(guild_id: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT command_name, role_id FROM command_permissions WHERE guild_id = ? ORDER BY command_name",
        (guild_id,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def add_command_permission(command_name: str, guild_id: str, role_id: str):
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO command_permissions (command_name, guild_id, role_id) VALUES (?, ?, ?)",
        (command_name, guild_id, role_id),
    )
    await db.commit()


async def remove_command_permission(command_name: str, guild_id: str, role_id: str) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM command_permissions WHERE command_name = ? AND guild_id = ? AND role_id = ?",
        (command_name, guild_id, role_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_allowed_roles(command_name: str, guild_id: str) -> list[str]:
    """Return list of role IDs allowed to use this command (empty = unrestricted)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT role_id FROM command_permissions WHERE command_name = ? AND guild_id = ?",
        (command_name, guild_id),
    )
    rows = await cursor.fetchall()
    return [row["role_id"] for row in rows]


# --- Analytics helpers ---

async def log_event(
    event_type: str,
    guild_id: str | None = None,
    channel_id: str | None = None,
    user_id: str | None = None,
    provider: str | None = None,
    tokens_used: int | None = None,
    latency_ms: int | None = None,
):
    db = await get_db()
    await db.execute(
        """INSERT INTO analytics
           (event_type, guild_id, channel_id, user_id, provider, tokens_used, latency_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (event_type, guild_id, channel_id, user_id, provider, tokens_used, latency_ms),
    )
    await db.commit()


async def get_analytics_summary(guild_id: str | None = None) -> dict:
    db = await get_db()
    where = "WHERE guild_id = ?" if guild_id else ""
    params = (guild_id,) if guild_id else ()

    cursor = await db.execute(
        f"SELECT COUNT(*) as total, event_type FROM analytics {where} GROUP BY event_type",
        params,
    )
    rows = await cursor.fetchall()
    by_type = {row["event_type"]: row["total"] for row in rows}

    cursor2 = await db.execute(
        f"""SELECT DATE(created_at) as day, COUNT(*) as count
            FROM analytics {where}
            GROUP BY day ORDER BY day DESC LIMIT 30""",
        params,
    )
    daily = [dict(r) for r in await cursor2.fetchall()]

    cursor3 = await db.execute(
        f"""SELECT provider, COUNT(*) as count
            FROM analytics {where} AND provider IS NOT NULL""".replace(
            "AND", "WHERE" if not guild_id else "AND"
        ),
        params,
    )
    providers = [dict(r) for r in await cursor3.fetchall()]

    return {"by_type": by_type, "daily": daily, "providers": providers}


# --- Channel prompt helpers ---

async def get_channel_prompt(channel_id: str) -> str | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT system_prompt FROM channel_prompts WHERE channel_id = ?",
        (channel_id,),
    )
    row = await cursor.fetchone()
    return row["system_prompt"] if row else None


async def set_channel_prompt(channel_id: str, guild_id: str, system_prompt: str):
    db = await get_db()
    await db.execute(
        """INSERT INTO channel_prompts (channel_id, guild_id, system_prompt) VALUES (?, ?, ?)
           ON CONFLICT(channel_id) DO UPDATE SET system_prompt = excluded.system_prompt""",
        (channel_id, guild_id, system_prompt),
    )
    await db.commit()


async def delete_channel_prompt(channel_id: str):
    db = await get_db()
    await db.execute("DELETE FROM channel_prompts WHERE channel_id = ?", (channel_id,))
    await db.commit()


async def list_channel_prompts(guild_id: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT channel_id, system_prompt FROM channel_prompts WHERE guild_id = ?",
        (guild_id,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]