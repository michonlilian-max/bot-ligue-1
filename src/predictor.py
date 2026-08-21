"""Modèle de prédiction des matchs de Ligue 1, basé sur une loi de Poisson.

Principe (approche classique en prédiction football, type Dixon-Coles simplifié) :
1. On calcule, pour chaque équipe, sa force offensive et défensive à domicile
   et à l'extérieur, à partir des matchs déjà joués dans la saison.
2. On en déduit le nombre de buts attendus (lambda) pour chaque équipe d'un
   match à venir.
3. On utilise la loi de Poisson pour calculer la probabilité de chaque score
   exact possible, puis on en déduit les probabilités 1N2 (victoire domicile,
   nul, victoire extérieur) et le score le plus probable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from src.config import MAX_GOALS


@dataclass
class TeamStats:
    """Statistiques offensives/défensives d'une équipe sur la saison."""

    home_goals_scored: int = 0
    home_goals_conceded: int = 0
    home_matches: int = 0
    away_goals_scored: int = 0
    away_goals_conceded: int = 0
    away_matches: int = 0

    @property
    def avg_home_scored(self) -> float:
        return self.home_goals_scored / self.home_matches if self.home_matches else 0.0

    @property
    def avg_home_conceded(self) -> float:
        return self.home_goals_conceded / self.home_matches if self.home_matches else 0.0

    @property
    def avg_away_scored(self) -> float:
        return self.away_goals_scored / self.away_matches if self.away_matches else 0.0

    @property
    def avg_away_conceded(self) -> float:
        return self.away_goals_conceded / self.away_matches if self.away_matches else 0.0


@dataclass
class LeagueAverages:
    """Moyennes de buts marqués à domicile/extérieur sur l'ensemble de la ligue."""

    avg_home_goals: float = 1.5
    avg_away_goals: float = 1.2


@dataclass
class MatchPrediction:
    home_team: str
    away_team: str
    lambda_home: float
    lambda_away: float
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    predicted_score: tuple[int, int]
    score_matrix: dict[tuple[int, int], float] = field(repr=False, default_factory=dict)

    @property
    def most_likely_result(self) -> str:
        probs = {
            "1": self.home_win_prob,
            "N": self.draw_prob,
            "2": self.away_win_prob,
        }
        return max(probs, key=probs.get)


def build_team_stats(finished_matches: list[dict[str, Any]]) -> dict[str, TeamStats]:
    """Construit les statistiques par équipe à partir des matchs terminés (format API football-data.org)."""
    stats: dict[str, TeamStats] = {}

    for match in finished_matches:
        score = match.get("score", {}).get("fullTime", {})
        home_goals = score.get("home")
        away_goals = score.get("away")
        if home_goals is None or away_goals is None:
            continue

        home_name = match["homeTeam"]["name"]
        away_name = match["awayTeam"]["name"]

        home = stats.setdefault(home_name, TeamStats())
        away = stats.setdefault(away_name, TeamStats())

        home.home_goals_scored += home_goals
        home.home_goals_conceded += away_goals
        home.home_matches += 1

        away.away_goals_scored += away_goals
        away.away_goals_conceded += home_goals
        away.away_matches += 1

    return stats


def compute_league_averages(finished_matches: list[dict[str, Any]]) -> LeagueAverages:
    """Calcule les moyennes de buts domicile/extérieur sur la ligue (utilisées en repli)."""
    total_home_goals = 0
    total_away_goals = 0
    count = 0

    for match in finished_matches:
        score = match.get("score", {}).get("fullTime", {})
        home_goals = score.get("home")
        away_goals = score.get("away")
        if home_goals is None or away_goals is None:
            continue
        total_home_goals += home_goals
        total_away_goals += away_goals
        count += 1

    if count == 0:
        return LeagueAverages()

    return LeagueAverages(
        avg_home_goals=total_home_goals / count,
        avg_away_goals=total_away_goals / count,
    )


def expected_goals(
    home_team: str,
    away_team: str,
    stats: dict[str, TeamStats],
    league_avg: LeagueAverages,
) -> tuple[float, float]:
    """Calcule le nombre de buts attendus (lambda) pour les deux équipes d'un match.

    Force d'attaque = buts marqués par match / moyenne de la ligue.
    Force de défense = buts encaissés par match / moyenne de la ligue.
    lambda_home = force_attaque(domicile) * force_defense(exterieur) * moyenne_ligue_domicile
    lambda_away = force_attaque(exterieur) * force_defense(domicile) * moyenne_ligue_exterieur
    """
    home_stats = stats.get(home_team, TeamStats())
    away_stats = stats.get(away_team, TeamStats())

    home_attack = _safe_ratio(home_stats.avg_home_scored, league_avg.avg_home_goals)
    home_defense = _safe_ratio(home_stats.avg_home_conceded, league_avg.avg_away_goals)
    away_attack = _safe_ratio(away_stats.avg_away_scored, league_avg.avg_away_goals)
    away_defense = _safe_ratio(away_stats.avg_away_conceded, league_avg.avg_home_goals)

    lambda_home = home_attack * away_defense * league_avg.avg_home_goals
    lambda_away = away_attack * home_defense * league_avg.avg_away_goals

    # On évite les valeurs nulles ou aberrantes (peu/pas de matchs joués).
    lambda_home = max(lambda_home, 0.1)
    lambda_away = max(lambda_away, 0.1)

    return lambda_home, lambda_away


def _safe_ratio(value: float, reference: float, default: float = 1.0) -> float:
    if reference == 0:
        return default
    if value == 0:
        return default
    return value / reference


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def score_probability_matrix(
    lambda_home: float, lambda_away: float, max_goals: int = MAX_GOALS
) -> dict[tuple[int, int], float]:
    """Calcule la probabilité de chaque score exact possible (0-0, 1-0, ..., max_goals-max_goals).

    La matrice est normalisée pour que les probabilités somment à 1, car la
    somme tronquée à max_goals peut négliger une petite part de la masse de
    probabilité pour des équipes à très fort lambda.
    """
    matrix: dict[tuple[int, int], float] = {}
    for home_goals in range(max_goals + 1):
        for away_goals in range(max_goals + 1):
            matrix[(home_goals, away_goals)] = _poisson_pmf(home_goals, lambda_home) * _poisson_pmf(
                away_goals, lambda_away
            )

    total = sum(matrix.values())
    if total > 0:
        matrix = {score: p / total for score, p in matrix.items()}

    return matrix


def predict_match(
    home_team: str,
    away_team: str,
    stats: dict[str, TeamStats],
    league_avg: LeagueAverages,
) -> MatchPrediction:
    """Prédit le résultat (1N2) et le score le plus probable d'un match."""
    lambda_home, lambda_away = expected_goals(home_team, away_team, stats, league_avg)
    matrix = score_probability_matrix(lambda_home, lambda_away)

    home_win_prob = sum(p for (h, a), p in matrix.items() if h > a)
    draw_prob = sum(p for (h, a), p in matrix.items() if h == a)
    away_win_prob = sum(p for (h, a), p in matrix.items() if h < a)

    predicted_score = max(matrix, key=matrix.get)

    return MatchPrediction(
        home_team=home_team,
        away_team=away_team,
        lambda_home=lambda_home,
        lambda_away=lambda_away,
        home_win_prob=home_win_prob,
        draw_prob=draw_prob,
        away_win_prob=away_win_prob,
        predicted_score=predicted_score,
        score_matrix=matrix,
    )
