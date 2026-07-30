"""Usage metering + subscription plans.

Was **not started** per docs/launch-readiness.md (`commercial-roadmap.md`
claimed a "billing placeholder" existed — it didn't; there was no billing
code anywhere in the repo). This builds the part that's honestly
code-completable without you: usage tracking, plan limits, and a soft quota
gate. It does NOT include a live payment processor integration — that
requires a Stripe (or similar) account and real pricing decisions only you
can make. `app/billing_stripe.py` has the checkout/webhook plumbing ready to
go the moment STRIPE_SECRET_KEY is set; until then it's inert.
"""

from __future__ import annotations

import calendar
import time
from typing import Any

from app.config import settings
from app.db import get_conn, new_id, now

PLANS: dict[str, dict[str, Any]] = {
    "free": {"label": "Community", "messages_per_month": 200, "price_usd": 0},
    "pro": {"label": "Professional", "messages_per_month": 5000, "price_usd": 49},
    "team": {"label": "Business", "messages_per_month": 25_000, "price_usd": 199},
    "enterprise": {"label": "Enterprise", "messages_per_month": None, "price_usd": None},
}


def _month_start_epoch() -> float:
    t = time.gmtime()
    return calendar.timegm((t.tm_year, t.tm_mon, 1, 0, 0, 0, 0, 0, 0))


def record_usage(user_id: str, kind: str = "chat_message", quantity: int = 1) -> None:
    if user_id == "local":
        return  # local/no-auth mode has no per-user billing concept
    c = get_conn()
    c.execute(
        "INSERT INTO usage_events (id, user_id, kind, quantity, created_at) VALUES (?, ?, ?, ?, ?)",
        (new_id(), user_id, kind, quantity, now()),
    )
    c.commit()


def usage_this_month(user_id: str, kind: str = "chat_message") -> int:
    row = get_conn().execute(
        "SELECT COALESCE(SUM(quantity), 0) AS total FROM usage_events "
        "WHERE user_id = ? AND kind = ? AND created_at >= ?",
        (user_id, kind, _month_start_epoch()),
    ).fetchone()
    return int(row["total"] or 0)


def get_user_plan(user_id: str) -> str:
    if user_id == "local":
        return "enterprise"  # unmetered local/dev use
    row = get_conn().execute("SELECT plan FROM users WHERE id = ?", (user_id,)).fetchone()
    plan = (row["plan"] if row else None) or "free"
    return plan if plan in PLANS else "free"


def set_user_plan(user_id: str, plan: str) -> None:
    if plan not in PLANS:
        raise ValueError(f"Unknown plan '{plan}'. Must be one of: {', '.join(PLANS)}")
    c = get_conn()
    c.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))
    c.commit()


def usage_snapshot(user_id: str) -> dict[str, Any]:
    plan = get_user_plan(user_id)
    limits = PLANS[plan]
    used = usage_this_month(user_id, "chat_message")
    limit = limits["messages_per_month"]
    return {
        "plan": plan,
        "plan_label": limits["label"],
        "messages_used_this_month": used,
        "messages_limit": limit,
        "messages_remaining": None if limit is None else max(0, limit - used),
        "over_limit": bool(limit is not None and used >= limit),
        "enforcement_enabled": settings.billing_enforcement_enabled,
    }


def check_quota_ok(user_id: str) -> tuple[bool, str]:
    """Soft gate — returns (ok, reason). Only actually blocks when
    BILLING_ENFORCEMENT_ENABLED=true, so alpha/beta usage is never
    interrupted by an incomplete billing rollout."""
    if not settings.billing_enforcement_enabled:
        return True, ""
    snap = usage_snapshot(user_id)
    if snap["over_limit"]:
        return False, (
            f"Monthly message limit reached for the {snap['plan_label']} plan "
            f"({snap['messages_used_this_month']}/{snap['messages_limit']}). "
            "Upgrade your plan to continue, or wait until next month's reset."
        )
    return True, ""
