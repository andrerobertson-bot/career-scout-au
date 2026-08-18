from __future__ import annotations

import os
import re
from typing import Any

import httpx

from career_scout.models import Job


class SeekApifyCollector:
    """Fresh SEEK discovery constrained to the last day.

    Discovery data is used for title/JD/salary/work arrangement only. Live status
    and displayed posting age are always re-checked later in a rendered browser.
    """

    ACTOR = "scrapersdelight~seek-jobs-scraper"
    API = "https://api.apify.com/v2"

    def __init__(self, token: str | None = None, timeout: float = 180.0) -> None:
        self.token = token or os.getenv("APIFY_TOKEN")
        if not self.token:
            raise RuntimeError("APIFY_TOKEN is required for the managed SEEK collector")
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)

    def close(self) -> None:
        self.client.close()

    @staticmethod
    def _canonical_url(job_id: str) -> str:
        return f"https://www.seek.com.au/job/{job_id}"

    @staticmethod
    def _job_id(row: dict[str, Any]) -> str:
        value = str(row.get("id") or row.get("jobId") or row.get("job_id") or "")
        if value.isdigit():
            return value
        url = str(row.get("job_url") or row.get("url") or row.get("jobUrl") or row.get("link") or "")
        m = re.search(r"/job/(\d+)", url)
        return m.group(1) if m else ""

    @staticmethod
    def _text(row: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _list_text(row: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = row.get(key)
            if isinstance(value, list) and value:
                return ", ".join(str(x) for x in value if x is not None)
        return None

    def search(self, keywords: str, *, where: str = "All Sydney NSW", page: int = 1, sortmode: str = "ListedDate") -> list[Job]:
        endpoint = f"{self.API}/acts/{self.ACTOR}/run-sync-get-dataset-items"
        location = "Sydney" if "Sydney" in where else where
        payload = {
            "keywords": keywords,
            "location": location,
            "country": "AU",
            "dateRange": 1,
            "sortMode": "ListedDate",
            "fetchDescriptions": True,
            "maxItems": 100,
        }
        response = self.client.post(endpoint, params={"token": self.token}, json=payload)
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            return []

        jobs: list[Job] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            job_id = self._job_id(row)
            title = self._text(row, "title", "jobTitle", "job_title")
            description = self._text(row, "description_text", "descriptionText", "description", "jobDescription")
            if not job_id or not title or not description:
                continue
            canonical = self._canonical_url(job_id)
            jobs.append(Job(
                source="seek",
                source_job_id=job_id,
                title=title,
                company=self._text(row, "company_name", "companyName", "company", "advertiser_name"),
                location=self._text(row, "location", "locationName", "where"),
                work_arrangement=self._list_text(row, "work_arrangements", "workArrangements") or self._text(row, "workArrangement"),
                employment_type=self._list_text(row, "work_types", "workTypes") or self._text(row, "workType", "employmentType"),
                salary_text=self._text(row, "salary_label", "salaryLabel", "salary", "salaryText"),
                salary_min=row.get("salary_min") if isinstance(row.get("salary_min"), (int, float)) else None,
                salary_max=row.get("salary_max") if isinstance(row.get("salary_max"), (int, float)) else None,
                salary_period=self._text(row, "salary_period", "salaryPeriod"),
                url=canonical,
                canonical_url=canonical,
                posted_at=self._text(row, "listing_date", "listingDate"),
                valid_through=self._text(row, "expires_at", "expiresAt"),
                description=description,
                teaser=self._text(row, "teaser", "abstract", "summary"),
                bullet_points=[str(x) for x in (row.get("bullet_points") or row.get("bulletPoints") or [])],
                is_live=None,
                is_expired=None,
                status="DISCOVERED_PAST_DAY_UNVERIFIED",
                raw=row,
            ))
        return jobs

    def verify_and_enrich(self, job: Job) -> Job:
        # Final status/freshness validation is rendered-browser based in pipeline.
        return job
