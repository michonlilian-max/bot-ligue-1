"""Statistiques avancées et indice de force composite.

Vient compléter le modèle Poisson de base (buts marqués/encaissés) avec :
- la forme récente (5 derniers matchs) ;
- les confrontations directes (5 derniers face-à-face) ;
- la discipline (cartons jaunes/rouges par match) ;
- l'expérience de l'effectif (âge moyen, utilisé comme proxy — l'API
  gratuite ne donne pas le nombre de matchs joués en carrière par joueur).

Ces signaux sont combinés en un ajustement multiplicatif appliqué aux buts
attendus (lambda) du modèle Poisson : voir `compute_strength_multipliers`.

La masse salariale et le prix d'achat des joueurs ne sont volontairement
pas inclus : il n'existe pas de source gratuite fiable pour ces données
(voir README).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src import config


@dataclass
class TeamForm:
    """Forme d'une équipe sur ses 5 derniers matchs (toutes compétitions confondues)."""

    points: int = 0  # sur 15 (victoire=3, nul=1, défaite=0)
    wins: int = 0
    draws: int = 0
    losses: int = 0


@dataclass
class TeamDiscipline:
    """Cartons reçus par une équipe sur la saison en cours."""

    yellow_cards: int = 0
    red_cards: int = 0
    matches_played: int = 0

    @property
    def cards_per_match(self) -> float:
        """Indice de discipline : un carton rouge compte double d'un jaune."""
        if not self.matches_played:
            return 0.0
        return (self.yellow_cards + self.red_cards * 2) / self.matches_played


@dataclass
class HeadToHeadSummary:
    """Résumé des confrontations directes entre deux équipes, du point de vue de l'équipe à domicile."""

    home_wins: int = 0
    draws: int = 0
    away_wins: int = 0
    matches_considered: int = 0

    @property
    def home_score(self) -> float:
        """Score de dominance en confrontations directes, de -1 (extérieur domine) à +1 (domicile domine)."""
        if not self.matches_considered:
            return 0.0
        return (self.home_wins - self.away_wins) / self.matches_considered


@dataclass
class AdvancedSignals:
    """Ensemble des signaux avancés disponibles pour une équipe avant un match."""

    form: TeamForm
    discipline: TeamDiscipline
    avg_squad_age: float | None = None


def parse_form_string(form: str | None) -> TeamForm:
    """Parse la chaîne de forme renvoyée par API-Football (ex: "WWDLW", 5 derniers matchs)."""
    if not form:
        return TeamForm()

    recent = form[-5:]
    points = wins = draws = losses = 0
    for result in recent:
        if result == "W":
            points += 3
            wins += 1
        elif result == "D":
            points += 1
            draws += 1
        elif result == "L":
            losses += 1

    return TeamForm(points=points, wins=wins, draws=draws, losses=losses)


def _sum_card_totals(interval_breakdown: dict[str, Any]) -> int:
    """Additionne les cartons sur tous les intervalles de temps renvoyés par l'API."""
    total = 0
    for interval_stats in interval_breakdown.values():
        value = interval_stats.get("total") if isinstance(interval_stats, dict) else None
        if value:
            total += value
    return total


def extract_discipline(team_statistics: dict[str, Any]) -> TeamDiscipline:
    """Extrait les statistiques de cartons à partir de la réponse `/teams/statistics` d'API-Football."""
    cards = team_statistics.get("cards", {}) or {}
    yellow_total = _sum_card_totals(cards.get("yellow", {}) or {})
    red_total = _sum_card_totals(cards.get("red", {}) or {})

    played = 0
    fixtures = team_statistics.get("fixtures", {}) or {}
    played_block = fixtures.get("played", {}) or {}
    if isinstance(played_block, dict):
        played = played_block.get("total") or 0

    return TeamDiscipline(yellow_cards=yellow_total, red_cards=red_total, matches_played=played)


def summarize_head_to_head(fixtures: list[dict[str, Any]], home_team_id: int, last: int = 5) -> HeadToHeadSummary:
    """Résume les `last` dernières confrontations directes du point de vue de `home_team_id`."""
    home_wins = draws = away_wins = considered = 0

    for fixture in fixtures[:last]:
        goals = fixture.get("goals", {}) or {}
        home_goals, away_goals = goals.get("home"), goals.get("away")
        if home_goals is None or away_goals is None:
            continue

        teams = fixture.get("teams", {}) or {}
        fixture_home_id = (teams.get("home") or {}).get("id")

        if fixture_home_id == home_team_id:
            team_goals, opponent_goals = home_goals, away_goals
        else:
            team_goals, opponent_goals = away_goals, home_goals

        considered += 1
        if team_goals > opponent_goals:
            home_wins += 1
        elif team_goals == opponent_goals:
            draws += 1
        else:
            away_wins += 1

    return HeadToHeadSummary(home_wins=home_wins, draws=draws, away_wins=away_wins, matches_considered=considered)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def compute_strength_multipliers(
    home: AdvancedSignals,
    away: AdvancedSignals,
    head_to_head: HeadToHeadSummary | None = None,
) -> tuple[float, float]:
    """Calcule les multiplicateurs à appliquer aux buts attendus (lambda) de chaque équipe.

    Combine forme récente, confrontations directes, discipline et expérience
    en un score composite dans [-1, 1] (positif = avantage domicile), puis le
    convertit en un ajustement multiplicatif borné à
    +/- `config.MAX_STRENGTH_ADJUSTMENT` sur les buts attendus.
    """
    form_diff = (home.form.points - away.form.points) / 15  # dans [-1, 1]

    if home.discipline.matches_played and away.discipline.matches_played:
        # Moins de cartons = avantage : on inverse le signe (away - home).
        discipline_diff = _clamp((away.discipline.cards_per_match - home.discipline.cards_per_match) / 3, -1, 1)
    else:
        discipline_diff = 0.0

    if home.avg_squad_age is not None and away.avg_squad_age is not None:
        # Un effectif plus âgé est utilisé comme proxy d'un effectif plus expérimenté.
        experience_diff = _clamp((home.avg_squad_age - away.avg_squad_age) / 5, -1, 1)
    else:
        experience_diff = 0.0

    h2h_diff = head_to_head.home_score if head_to_head else 0.0

    weighted = (
        config.FORM_WEIGHT * form_diff
        + config.H2H_WEIGHT * h2h_diff
        + config.DISCIPLINE_WEIGHT * discipline_diff
        + config.EXPERIENCE_WEIGHT * experience_diff
    )
    weighted = _clamp(weighted, -1, 1)

    home_multiplier = 1 + weighted * config.MAX_STRENGTH_ADJUSTMENT
    away_multiplier = 1 - weighted * config.MAX_STRENGTH_ADJUSTMENT

    low = 1 - config.MAX_STRENGTH_ADJUSTMENT
    high = 1 + config.MAX_STRENGTH_ADJUSTMENT
    return _clamp(home_multiplier, low, high), _clamp(away_multiplier, low, high)
