from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from career_scout.models import Job


class SeekApifyCollector:
    """Managed SEEK discovery with a strict individual-vacancy publication gate.

    Discovery metadata is never authoritative for live state or posting age. Both are
    re-derived from the canonical individual SEEK page immediately before publication.
    """

    ACTOR = "crawlerbros~seek-jobs-scraper"
    API = "https://api.apify.com/v2"
    CLOSED_MARKERS = (
        "this job has expired",
        "job has expired",
        "this job is no longer available",
        "this job is no longer advertised",
        "job is no longer advertised",
        "no longer accepting applications",
        "search for another job",
    )
    APPLY_MARKERS = (
        "quick apply",
        "apply now",
        "apply for this job",
        "apply for job",
    )

    def __init__(self, token: str | None = None, timeout: float = 180.0) -> None:
        self.token = token or os.getenv("APIFY_TOKEN")
        if not self.token:
            raise RuntimeError("APIFY_TOKEN is required for the managed SEEK collector")
        self.client = httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})

    def close(self) -> None:
        self.client.close()

    @staticmethod
    def _seek_url_for_query(keywords: str, where: str) -> str:
        q = re.sub(r"[^a-z0-9]+", "-", keywords.lower()).strip("-")
        loc = where.replace(" ", "-")
        return f"https://www.seek.com.au/{q}-jobs/in-{loc}?sortmode=ListedDate"

    @staticmethod
    def _canonical_url(job_id: str) -> str:
        return f"https://www.seek.com.au/job/{job_id}"

    @staticmethod
    def _job_id(row: dict[str, Any]) -> str:
        value = str(row.get("id") or row.get("jobId") or row.get("job_id") or "")
        if value.isdigit():
            return value
        url = str(row.get("url") or row.get("jobUrl") or row.get("job_url") or row.get("link") or "")
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
    def _extract_page_posted_at(html: str) -> str | None:
        """Extract posting date/age from the canonical page only.

        Prefer structured datePosted when present. Fall back to SEEK's rendered
        relative labels such as 'Posted 12d ago' / 'Listed two days ago'. If the
        page does not expose a defensible value, return None rather than trusting
        discovery metadata.
        """
        # JSON-LD / embedded structured data.
        for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.I | re.S):
            try:
                payload = json.loads(m.group(1).strip())
            except (json.JSONDecodeError, TypeError):
                continue
            nodes = payload if isinstance(payload, list) else [payload]
            for node in nodes:
                if isinstance(node, dict) and isinstance(node.get("datePosted"), str):
                    return node["datePosted"].strip()

        # Other embedded application state commonly exposes datePosted/listingDate.
        m = re.search(r'["\'](?:datePosted|listingDate)["\']\s*:\s*["\']([^"\']+)["\']', html, re.I)
        if m:
            return m.group(1).strip()

        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).lower()
        now = datetime.now(timezone.utc)

        numeric = re.search(r"(?:posted|listed)\s+(\d+)\s*(?:d|day|days)\s+ago", text)
        if numeric:
            return (now - timedelta(days=int(numeric.group(1)))).date().isoformat()

        words = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
            "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
            "nineteen": 19, "twenty": 20, "twenty one": 21, "twenty-one": 21,
            "twenty two": 22, "twenty-two": 22, "twenty three": 23,
            "twenty-three": 23, "twenty four": 24, "twenty-four": 24,
            "twenty five": 25, "twenty-five": 25, "twenty six": 26,
            "twenty-six": 26, "twenty seven": 27, "twenty-seven": 27,
            "twenty eight": 28, "twenty-eight": 28, "twenty nine": 29,
            "twenty-nine": 29, "thirty": 30,
        }
        word_match = re.search(r"(?:posted|listed)\s+([a-z-]+(?:\s+[a-z-]+)?)\s+days?\s+ago", text)
        if word_match and word_match.group(1) in words:
            return (now - timedelta(days=words[word_match.group(1)])).date().isoformat()

        if re.search(r"(?:posted|listed)\s+(?:today|\d+\s*(?:m|min|mins|minute|minutes|h|hr|hrs|hour|hours)\s+ago)", text):
            return now.date().isoformat()
        if re.search(r"(?:posted|listed)\s+(?:yesterday|one\s+day\s+ago|1\s*day\s+ago)", text):
            return (now - timedelta(days=1)).date().isoformat()
        return None

    def search(self, keywords: str, *, where: str = "All Sydney NSW", page: int = 1, sortmode: str = "ListedDate") -> list[Job]:
        endpoint = f"{self.API}/acts/{self.ACTOR}/run-sync-get-dataset-items"
        payload = {
            "searchUrls": [self._seek_url_for_query(keywords, where)],
            "maxItems": 40,
            "proxyConfiguration": {"useApifyProxy": True},
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
            description = self._text(row, "description", "jobDescription", "job_description", "content")
            if not job_id or not title or not description:
                continue
            canonical = self._canonical_url(job_id)
            jobs.append(Job(
                source="seek",
                source_job_id=job_id,
                title=title,
                company=self._text(row, "company", "companyName", "advertiserName", "advertiser"),
                location=self._text(row, "location", "locationName", "where"),
                work_arrangement=self._text(row, "workArrangement", "work_arrangement", "workType"),
                employment_type=self._text(row, "employmentType", "employment_type", "workType"),
                salary_text=self._text(row, "salary", "salaryText", "salaryLabel"),
                url=canonical,
                canonical_url=canonical,
                apply_url=self._text(row, "applyUrl", "apply_url"),
                # Discovery date is intentionally discarded; canonical page owns freshness.
                posted_at=None,
                valid_through=self._text(row, "validThrough", "expiresAt"),
                description=description,
                teaser=self._text(row, "teaser", "abstract", "summary"),
                is_live=None,
                is_expired=None,
                status="DISCOVERED_UNVERIFIED",
                raw=row,
            ))
        return jobs

    def verify_and_enrich(self, job: Job) -> Job:
        job.canonical_url = self._canonical_url(job.source_job_id)
        job.url = job.canonical_url
        job.verified_at = datetime.now(timezone.utc).isoformat()
        job.verification_method = "canonical_seek_job_page_status_and_freshness"
        job.posted_at = None
        try:
            response = self.client.get(job.canonical_url)
        except httpx.HTTPError:
            job.is_live = False
            job.status = "VERIFICATION_REQUEST_FAILED"
            return job

        final_url = str(response.url)
        body = response.text.lower()
        exact_job = re.search(rf"/job/{re.escape(job.source_job_id)}(?:\D|$)", final_url) is not None or job.source_job_id in response.text
        closed = any(marker in body for marker in self.CLOSED_MARKERS)
        redirected_to_search = "/job/" not in final_url
        has_apply_surface = any(marker in body for marker in self.APPLY_MARKERS)

        # A 200 page is not sufficient: SEEK serves a normal 200 HTML page for jobs
        # that say 'This job is no longer advertised'. Closed copy always wins.
        if response.status_code != 200 or not exact_job or redirected_to_search or closed or not has_apply_surface:
            job.is_live = False
            job.is_expired = closed
            if closed:
                job.status = "CLOSED_PAGE_MARKER"
            elif not has_apply_surface:
                job.status = "NO_ACTIVE_APPLY_SURFACE"
            else:
                job.status = "UNVERIFIED_CANONICAL_JOB"
            return job

        job.posted_at = self._extract_page_posted_at(response.text)
        job.is_live = True
        job.is_expired = False
        job.status = "VERIFIED_LIVE_CANONICAL"
        return job
