from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Job:
    source: str
    source_job_id: str
    title: str
    company: str | None = None
    location: str | None = None
    work_arrangement: str | None = None
    employment_type: str | None = None
    salary_text: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_period: str | None = None
    url: str | None = None
    apply_url: str | None = None
    posted_at: str | None = None
    valid_through: str | None = None
    description: str | None = None
    teaser: str | None = None
    bullet_points: list[str] = field(default_factory=list)
    is_live: bool | None = None
    is_expired: bool | None = None
    status: str | None = None
    verified_at: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_job_id}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("raw", None)
        return data
