from __future__ import annotations

import json
from datetime import date
from typing import Any


TERMINAL_STATUSES = {"REJECTED", "CLOSED", "EXPIRED"}
PROTECTED_FROM_EXPIRY = {"APPLIED", "INTERVIEW"}


def role_key(source: str, job_id: str) -> str:
    return f"{source}:{job_id}"


def get_status(ledger: dict[str, Any], source: str, job_id: str) -> str | None:
    return (ledger.get("roles", {}).get(role_key(source, job_id)) or {}).get("status")


def should_suppress_as_new(ledger: dict[str, Any], source: str, job_id: str) -> bool:
    status = get_status(ledger, source, job_id)
    return bool(status and status in set(ledger.get("suppress_as_new", [])))


def apply_transition(
    ledger: dict[str, Any],
    source: str,
    job_id: str,
    status: str,
    *,
    title: str | None = None,
    company: str | None = None,
    notes: str | None = None,
    allow_regression: bool = False,
) -> bool:
    statuses = set(ledger.get("statuses", []))
    if statuses and status not in statuses:
        raise ValueError(f"Unsupported role status: {status}")

    key = role_key(source, job_id)
    roles = ledger.setdefault("roles", {})
    current = roles.get(key, {})
    current_status = current.get("status")
    if current_status == status:
        return False

    if current_status and not allow_regression:
        allowed = set(ledger.get("allowed_transitions", {}).get(current_status, []))
        if status not in allowed:
            return False

    record = dict(current)
    record.update({
        "source": source,
        "job_id": str(job_id),
        "status": status,
        "status_date": date.today().isoformat(),
    })
    if title:
        record["title"] = title
    if company:
        record["company"] = company
    if notes:
        record["notes"] = notes
    roles[key] = record
    ledger["updated_at"] = date.today().isoformat()
    return True


def mark_verified_expired(
    ledger: dict[str, Any],
    source: str,
    job_id: str,
    *,
    title: str | None = None,
    company: str | None = None,
) -> bool:
    current = get_status(ledger, source, job_id)
    if current in PROTECTED_FROM_EXPIRY:
        return False
    return apply_transition(
        ledger,
        source,
        job_id,
        "EXPIRED",
        title=title,
        company=company,
        notes="Career Scout directly verified that the individual vacancy was no longer advertised.",
    )


def dumps(ledger: dict[str, Any]) -> str:
    return json.dumps(ledger, indent=2, ensure_ascii=False) + "\n"
