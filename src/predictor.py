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

from src.config import MAX_GOALS, PRIOR_SEASON_WEIGHT_MATCHES


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
class BlendedTeamStats:
    """Statistiques d'une équipe mélangeant saison en cours et saison précédente.

    Produit par `blend_team_stats` : en tout début de saison, les moyennes
    sont ramenées vers celles de la saison précédente (peu ou pas de matchs
    joués cette saison-ci), puis l'effet s'estompe progressivement au fil des
    journées. Expose les mêmes attributs que `TeamStats` (avg_home_scored,
    etc.) pour rester utilisable de manière interchangeable dans
    `expected_goals`.
    """

    avg_home_scored: float = 0.0
    avg_home_conceded: float = 0.0
    avg_away_scored: float = 0.0
    avg_away_conceded: float = 0.0


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


def _shrink(current_avg: float, current_matches: int, prior_avg: float, prior_weight_matches: float) -> float:
    """Ramène une moyenne courante vers une moyenne "a priori" (shrinkage bayésien simple).

    `prior_weight_matches` est le nombre de matchs "virtuels" attribués à
    l'a priori : avec peu de matchs courants, le résultat est proche de
    `prior_avg` ; il se rapproche de `current_avg` au fur et à mesure que
    `current_matches` augmente.
    """
    total_weight = current_matches + prior_weight_matches
    if total_weight <= 0:
        return 0.0
    return (current_matches * current_avg + prior_weight_matches * prior_avg) / total_weight


def blend_team_stats(
    current_season_stats: dict[str, TeamStats],
    previous_season_stats: dict[str, TeamStats],
    prior_weight_matches: float = PRIOR_SEASON_WEIGHT_MATCHES,
) -> dict[str, BlendedTeamStats]:
    """Mélange les stats de la saison en cours avec celles de la saison précédente.

    À n'utiliser que lorsque des données de la saison précédente sont
    disponibles : mélanger avec un dictionnaire vide tirerait artificiellement
    les moyennes vers zéro (voir `_shrink`). C'est à l'appelant de ne pas
    appeler cette fonction en l'absence de données de saison précédente.
    """
    all_teams = set(current_season_stats) | set(previous_season_stats)
    blended: dict[str, BlendedTeamStats] = {}

    for team in all_teams:
        current = current_season_stats.get(team, TeamStats())
        previous = previous_season_stats.get(team, TeamStats())

        blended[team] = BlendedTeamStats(
            avg_home_scored=_shrink(
                current.avg_home_scored, current.home_matches, previous.avg_home_scored, prior_weight_matches
            ),
            avg_home_conceded=_shrink(
                current.avg_home_conceded, current.home_matches, previous.avg_home_conceded, prior_weight_matches
            ),
            avg_away_scored=_shrink(
                current.avg_away_scored, current.away_matches, previous.avg_away_scored, prior_weight_matches
            ),
            avg_away_conceded=_shrink(
                current.avg_away_conceded, current.away_matches, previous.avg_away_conceded, prior_weight_matches
            ),
        )

    return blended


def compute_league_averages(
    finished_matches: list[dict[str, Any]],
    previous_season_matches: list[dict[str, Any]] | None = None,
    prior_weight_matches: float = PRIOR_SEASON_WEIGHT_MATCHES,
) -> LeagueAverages:
    """Calcule les moyennes de buts domicile/extérieur sur la ligue (utilisées en repli).

    Si `previous_season_matches` est fourni, les moyennes de la saison en
    cours sont mélangées (shrinkage) avec celles de la saison précédente,
    pour rester fiables en tout début de saison courante.
    """
    current_home_total, current_away_total, current_count = _goal_totals(finished_matches)

    if current_count == 0 and not previous_season_matches:
        return LeagueAverages()

    current_home_avg = current_home_total / current_count if current_count else 0.0
    current_away_avg = current_away_total / current_count if current_count else 0.0

    if not previous_season_matches:
        return LeagueAverages(avg_home_goals=current_home_avg, avg_away_goals=current_away_avg)

    previous_home_total, previous_away_total, previous_count = _goal_totals(previous_season_matches)
    if previous_count == 0:
        previous_home_avg, previous_away_avg = LeagueAverages().avg_home_goals, LeagueAverages().avg_away_goals
    else:
        previous_home_avg = previous_home_total / previous_count
        previous_away_avg = previous_away_total / previous_count

    return LeagueAverages(
        avg_home_goals=_shrink(current_home_avg, current_count, previous_home_avg, prior_weight_matches),
        avg_away_goals=_shrink(current_away_avg, current_count, previous_away_avg, prior_weight_matches),
    )


def _goal_totals(matches: list[dict[str, Any]]) -> tuple[int, int, int]:
    """Retourne (total buts domicile, total buts extérieur, nombre de matchs comptés)."""
    total_home_goals = 0
    total_away_goals = 0
    count = 0

    for match in matches:
        score = match.get("score", {}).get("fullTime", {})
        home_goals = score.get("home")
        away_goals = score.get("away")
        if home_goals is None or away_goals is None:
            continue
        total_home_goals += home_goals
        total_away_goals += away_goals
        count += 1

    return total_home_goals, total_away_goals, count


def expected_goals(
    home_team: str,
    away_team: str,
    stats: dict[str, TeamStats | BlendedTeamStats],
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
    stats: dict[str, TeamStats | BlendedTeamStats],
    league_avg: LeagueAverages,
    strength_multipliers: tuple[float, float] | None = None,
) -> MatchPrediction:
    """Prédit le résultat (1N2) et le score le plus probable d'un match.

    `strength_multipliers`, si fourni, est un couple (multiplicateur_domicile,
    multiplicateur_extérieur) appliqué aux buts attendus (lambda) du modèle de
    base. Il vient typiquement de
    `advanced_stats.compute_strength_multipliers`, qui combine forme récente,
    confrontations directes, discipline et expérience de l'effectif.
    """
    lambda_home, lambda_away = expected_goals(home_team, away_team, stats, league_avg)

    if strength_multipliers is not None:
        home_multiplier, away_multiplier = strength_multipliers
        lambda_home = max(lambda_home * home_multiplier, 0.05)
        lambda_away = max(lambda_away * away_multiplier, 0.05)

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
