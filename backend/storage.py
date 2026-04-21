"""PostgreSQL persistence layer using asyncpg."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://loanuser:loanpass@localhost:5432/loandb",
)

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def init_db() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                current_step TEXT NOT NULL DEFAULT 'INTAKE',
                extracted_fields JSONB NOT NULL DEFAULT '{}',
                analysis JSONB NOT NULL DEFAULT '{}',
                tool_results JSONB NOT NULL DEFAULT '{}',
                decision JSONB NOT NULL DEFAULT '{}'
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_events (
                id SERIAL PRIMARY KEY,
                application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                agent_role TEXT NOT NULL,
                input_summary TEXT NOT NULL DEFAULT '',
                output_summary TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


# ------------------------------------------------------------------ Application

async def create_application(applicant_name: Optional[str] = None) -> Dict[str, Any]:
    pool = await get_pool()
    app_id = str(uuid.uuid4())
    extracted = {}
    if applicant_name:
        extracted["applicant_name"] = applicant_name

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO applications (id, extracted_fields, analysis, tool_results, decision)
            VALUES ($1, $2::jsonb, $3::jsonb, $4::jsonb, $5::jsonb)
            RETURNING *
            """,
            app_id,
            json.dumps(extracted),
            json.dumps({}),
            json.dumps({}),
            json.dumps({}),
        )
    return dict(row)


async def get_application(app_id: str) -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM applications WHERE id = $1", app_id
        )
    return dict(row) if row else None


async def update_application(
    app_id: str,
    current_step: str,
    extracted_fields: Dict,
    analysis: Dict,
    tool_results: Dict,
    decision: Dict,
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE applications
            SET current_step = $2,
                extracted_fields = $3::jsonb,
                analysis = $4::jsonb,
                tool_results = $5::jsonb,
                decision = $6::jsonb,
                updated_at = NOW()
            WHERE id = $1
            """,
            app_id,
            current_step,
            json.dumps(extracted_fields),
            json.dumps(analysis),
            json.dumps(tool_results),
            json.dumps(decision),
        )


# -------------------------------------------------------------------- Messages

async def add_message(
    app_id: str, role: str, content: str
) -> Dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO messages (application_id, role, content)
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            app_id, role, content,
        )
    return dict(row)


async def get_messages(app_id: str) -> List[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM messages WHERE application_id = $1 ORDER BY created_at",
            app_id,
        )
    return [dict(r) for r in rows]


# ----------------------------------------------------------------- Agent Events

async def add_agent_event(
    app_id: str,
    agent_role: str,
    input_summary: str,
    output_summary: str,
) -> Dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO agent_events (application_id, agent_role, input_summary, output_summary)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            app_id, agent_role, input_summary, output_summary,
        )
    return dict(row)


async def get_agent_events(app_id: str) -> List[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM agent_events WHERE application_id = $1 ORDER BY created_at",
            app_id,
        )
    return [dict(r) for r in rows]
