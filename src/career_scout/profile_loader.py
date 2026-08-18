from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class ScoutContext:
    profile: dict[str, Any]
    preferences: dict[str, Any]


class VaultLoader:
    """Loads Career Scout source-of-truth JSON from Career Operator Vault.

    In GitHub Actions, set CAREER_OPERATOR_TOKEN to a fine-grained token with
    read access to career-operator-vault. Local runs can alternatively point
    CAREER_SCOUT_PROFILE_FILE and CAREER_SCOUT_PREFERENCES_FILE at JSON files.
    """

    def __init__(self, repo: str = "andrerobertson-bot/career-operator-vault", branch: str = "main"):
        self.repo = repo
        self.branch = branch
        self.token = os.getenv("CAREER_OPERATOR_TOKEN", "")

    def load(self) -> ScoutContext:
        profile_file = os.getenv("CAREER_SCOUT_PROFILE_FILE")
        prefs_file = os.getenv("CAREER_SCOUT_PREFERENCES_FILE")
        if profile_file and prefs_file:
            return ScoutContext(self._read_local(profile_file), self._read_local(prefs_file))
        return ScoutContext(
            self._read_github("10_Job_Scout/MATCHING_PROFILE.json"),
            self._read_github("10_Job_Scout/SCOUT_PREFERENCES.json"),
        )

    @staticmethod
    def _read_local(path: str) -> dict[str, Any]:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _read_github(self, path: str) -> dict[str, Any]:
        if not self.token:
            raise RuntimeError("CAREER_OPERATOR_TOKEN is required to read the private Career Operator Vault")
        url = f"https://api.github.com/repos/{self.repo}/contents/{path}"
        response = requests.get(
            url,
            params={"ref": self.branch},
            headers={
                "Accept": "application/vnd.github.raw+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "Career-Scout-AU/0.2",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
