"""Récupération des matchs de Ligue 1 via l'API football-data.org."""
from __future__ import annotations

from typing import Any

import requests

from src import config


class FootballDataError(RuntimeError):
    """Erreur levée quand l'API football-data.org répond avec un problème."""


class FootballDataClient:
    """Client minimal pour l'API football-data.org, limité à la Ligue 1."""

    def __init__(self, token: str | None = None, base_url: str | None = None) -> None:
        self.token = token or config.FOOTBALL_DATA_API_TOKEN
        self.base_url = base_url or config.API_BASE_URL

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise FootballDataError(
                "Aucun jeton API configuré. Définissez FOOTBALL_DATA_API_TOKEN "
                "dans votre fichier .env (voir .env.example)."
            )
        return {"X-Auth-Token": self.token}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = requests.get(url, headers=self._headers(), params=params, timeout=15)
        if response.status_code != 200:
            raise FootballDataError(
                f"Erreur API ({response.status_code}) sur {url}: {response.text}"
            )
        return response.json()

    def get_matches(
        self,
        status: str | None = None,
        matchday: int | None = None,
        season: int | None = None,
    ) -> list[dict[str, Any]]:
        """Récupère les matchs de Ligue 1, éventuellement filtrés par statut/journée/saison."""
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        if matchday:
            params["matchday"] = matchday
        if season:
            params["season"] = season
        data = self._get(f"/competitions/{config.COMPETITION_CODE}/matches", params=params)
        return data.get("matches", [])

    def fetch_finished_matches(self, season: int | None = None) -> list[dict[str, Any]]:
        """Récupère tous les matchs déjà joués de la saison indiquée (par défaut la saison en cours)."""
        return self.get_matches(status="FINISHED", season=season)

    def fetch_scheduled_matches(self, matchday: int | None = None) -> list[dict[str, Any]]:
        """Récupère les matchs programmés (à venir), éventuellement pour une journée précise."""
        return self.get_matches(status="SCHEDULED", matchday=matchday)

    def fetch_next_matchday(self) -> tuple[int | None, list[dict[str, Any]]]:
        """Récupère la prochaine journée qui contient des matchs programmés."""
        scheduled = self.fetch_scheduled_matches()
        if not scheduled:
            return None, []
        next_matchday = min(m["matchday"] for m in scheduled if m.get("matchday") is not None)
        matches = [m for m in scheduled if m.get("matchday") == next_matchday]
        return next_matchday, matches
