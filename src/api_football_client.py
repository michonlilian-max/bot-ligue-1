"""Client pour l'API-Football (api-sports.io) : statistiques avancées.

Utilisé pour tout ce que football-data.org ne fournit pas : forme récente
détaillée, cartons jaunes/rouges, confrontations directes, effectifs.
Nécessite une clé API gratuite (100 requêtes/jour) sur
https://dashboard.api-football.com/.

Optionnel : si aucune clé n'est configurée, le bot continue de fonctionner
avec le modèle de base (voir `is_configured`).
"""
from __future__ import annotations

import difflib
from typing import Any

import requests

from src import config
from src.cache import cached_call


class ApiFootballError(RuntimeError):
    """Erreur levée quand l'API-Football répond avec un problème."""


class ApiFootballClient:
    def __init__(
        self,
        api_key: str | None = None,
        league_id: int | None = None,
        season: int | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else config.API_FOOTBALL_TOKEN
        self.league_id = league_id or config.API_FOOTBALL_LEAGUE_ID
        self.season = season or config.API_FOOTBALL_SEASON
        self.base_url = base_url or config.API_FOOTBALL_BASE_URL
        self._team_name_to_id: dict[str, int] | None = None

    @property
    def is_configured(self) -> bool:
        """True si une clé API a été fournie (le bot peut fonctionner sans, en mode dégradé)."""
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ApiFootballError(
                "Aucune clé API-Football configurée. Définissez API_FOOTBALL_TOKEN "
                "dans votre fichier .env (voir .env.example)."
            )
        return {"x-apisports-key": self.api_key}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = requests.get(url, headers=self._headers(), params=params, timeout=15)
        if response.status_code != 200:
            raise ApiFootballError(f"Erreur API-Football ({response.status_code}) sur {url}: {response.text}")

        payload = response.json()
        errors = payload.get("errors")
        if errors:
            raise ApiFootballError(f"Erreur API-Football sur {url}: {errors}")
        return payload

    def _team_name_map(self) -> dict[str, int]:
        """Construit (et met en cache) la correspondance nom d'équipe -> id API-Football."""
        if self._team_name_to_id is not None:
            return self._team_name_to_id

        def fetch() -> list[dict[str, Any]]:
            payload = self._get("/teams", {"league": self.league_id, "season": self.season})
            return [
                {"id": item["team"]["id"], "name": item["team"]["name"]}
                for item in payload.get("response", [])
            ]

        teams = cached_call(f"af:teams:{self.league_id}:{self.season}", fetch)
        self._team_name_to_id = {team["name"]: team["id"] for team in teams}
        return self._team_name_to_id

    def find_team_id(self, team_name: str) -> int | None:
        """Retrouve l'id API-Football d'une équipe à partir de son nom.

        Les noms d'équipes peuvent différer légèrement entre football-data.org
        et API-Football (ex: "Paris Saint-Germain FC" vs "Paris Saint Germain"),
        d'où le recours à un rapprochement approximatif en repli.
        """
        name_map = self._team_name_map()
        if team_name in name_map:
            return name_map[team_name]

        closest = difflib.get_close_matches(team_name, name_map.keys(), n=1, cutoff=0.4)
        return name_map[closest[0]] if closest else None

    def get_team_statistics(self, team_id: int) -> dict[str, Any]:
        """Statistiques saison d'une équipe : forme, cartons, buts, matchs joués, etc."""

        def fetch() -> dict[str, Any]:
            payload = self._get(
                "/teams/statistics",
                {"league": self.league_id, "season": self.season, "team": team_id},
            )
            return payload.get("response", {}) or {}

        return cached_call(f"af:team_stats:{self.league_id}:{self.season}:{team_id}", fetch)

    def get_head_to_head(self, home_team_id: int, away_team_id: int, last: int = 5) -> list[dict[str, Any]]:
        """Les `last` dernières confrontations directes entre deux équipes (toutes compétitions)."""

        def fetch() -> list[dict[str, Any]]:
            payload = self._get(
                "/fixtures/headtohead",
                {"h2h": f"{home_team_id}-{away_team_id}", "last": last},
            )
            return payload.get("response", []) or []

        # Clé de cache indépendante de l'ordre pour éviter les doublons domicile/extérieur.
        ordered_ids = sorted([home_team_id, away_team_id])
        return cached_call(f"af:h2h:{ordered_ids[0]}-{ordered_ids[1]}:{last}", fetch)

    def get_squad_average_age(self, team_id: int) -> float | None:
        """Âge moyen de l'effectif, utilisé comme proxy d'expérience (voir advanced_stats)."""

        def fetch() -> float | None:
            payload = self._get("/players/squads", {"team": team_id})
            response = payload.get("response", []) or []
            if not response:
                return None
            players = response[0].get("players", []) or []
            ages = [p["age"] for p in players if p.get("age")]
            return sum(ages) / len(ages) if ages else None

        return cached_call(f"af:squad_age:{team_id}", fetch)
