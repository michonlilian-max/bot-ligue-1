"""Tests du modèle de prédiction (données synthétiques, pas d'appel réseau)."""
import math

from src.predictor import (
    TeamStats,
    blend_team_stats,
    build_team_stats,
    compute_league_averages,
    expected_goals,
    predict_match,
    score_probability_matrix,
)


def _match(home: str, away: str, home_goals: int, away_goals: int) -> dict:
    return {
        "homeTeam": {"name": home},
        "awayTeam": {"name": away},
        "score": {"fullTime": {"home": home_goals, "away": away_goals}},
    }


FINISHED_MATCHES = [
    _match("PSG", "Nice", 3, 0),
    _match("Lyon", "PSG", 0, 2),
    _match("Nice", "Lyon", 1, 1),
    _match("PSG", "Lyon", 4, 1),
    _match("Lyon", "Nice", 2, 2),
    _match("Nice", "PSG", 0, 1),
]


def test_build_team_stats_aggregates_goals_correctly():
    stats = build_team_stats(FINISHED_MATCHES)

    psg = stats["PSG"]
    assert psg.home_matches == 2
    assert psg.home_goals_scored == 7  # 3 + 4
    assert psg.home_goals_conceded == 1  # 0 + 1
    assert psg.away_matches == 2  # Lyon 0-2 PSG, Nice 0-1 PSG
    assert psg.away_goals_scored == 3  # 2 + 1
    assert psg.away_goals_conceded == 0


def test_compute_league_averages():
    league_avg = compute_league_averages(FINISHED_MATCHES)
    assert league_avg.avg_home_goals > 0
    assert league_avg.avg_away_goals > 0


def test_expected_goals_are_positive():
    stats = build_team_stats(FINISHED_MATCHES)
    league_avg = compute_league_averages(FINISHED_MATCHES)

    lambda_home, lambda_away = expected_goals("PSG", "Nice", stats, league_avg)

    assert lambda_home > 0
    assert lambda_away > 0


def test_score_probability_matrix_sums_close_to_one():
    matrix = score_probability_matrix(lambda_home=1.5, lambda_away=1.2, max_goals=10)
    total = sum(matrix.values())
    # Avec max_goals=10, on capture quasiment toute la masse de probabilité.
    assert math.isclose(total, 1.0, abs_tol=1e-3)


def test_predict_match_probabilities_sum_to_one():
    stats = build_team_stats(FINISHED_MATCHES)
    league_avg = compute_league_averages(FINISHED_MATCHES)

    prediction = predict_match("PSG", "Nice", stats, league_avg)

    total_prob = prediction.home_win_prob + prediction.draw_prob + prediction.away_win_prob
    assert math.isclose(total_prob, 1.0, abs_tol=1e-6)
    assert prediction.most_likely_result in {"1", "N", "2"}


def test_predict_match_favors_stronger_team():
    # PSG a une meilleure attaque et une meilleure défense que Nice dans les données de test.
    stats = build_team_stats(FINISHED_MATCHES)
    league_avg = compute_league_averages(FINISHED_MATCHES)

    prediction = predict_match("PSG", "Nice", stats, league_avg)

    assert prediction.home_win_prob > prediction.away_win_prob


def test_predict_match_applies_strength_multipliers():
    stats = build_team_stats(FINISHED_MATCHES)
    league_avg = compute_league_averages(FINISHED_MATCHES)

    baseline = predict_match("PSG", "Nice", stats, league_avg)
    # On simule Nice en très grande forme (H2H/forme dominante) face à un PSG affaibli.
    boosted_away = predict_match("PSG", "Nice", stats, league_avg, strength_multipliers=(0.75, 1.25))

    assert boosted_away.lambda_away > baseline.lambda_away
    assert boosted_away.lambda_home < baseline.lambda_home
    assert boosted_away.away_win_prob > baseline.away_win_prob


# --- Prise en compte de la saison précédente ---

PREVIOUS_SEASON_MATCHES = [
    _match("PSG", "Nice", 2, 1),
    _match("Nice", "PSG", 0, 3),
    _match("Lyon", "Nice", 1, 1),
    _match("Nice", "Lyon", 2, 0),
]


def test_blend_team_stats_uses_previous_season_when_no_current_matches():
    # Aucun match cette saison : le mélange doit reproduire exactement la
    # saison précédente (shrinkage total vers le prior).
    current_stats: dict[str, TeamStats] = {}
    previous_stats = build_team_stats(PREVIOUS_SEASON_MATCHES)

    blended = blend_team_stats(current_stats, previous_stats, prior_weight_matches=6)

    assert blended["PSG"].avg_home_scored == previous_stats["PSG"].avg_home_scored
    assert blended["Nice"].avg_away_conceded == previous_stats["Nice"].avg_away_conceded


def test_blend_team_stats_fades_toward_current_season_with_more_matches():
    previous_stats = build_team_stats(PREVIOUS_SEASON_MATCHES)

    # PSG a une seule victoire écrasante à domicile cette saison (moyenne très haute).
    few_matches = build_team_stats([_match("PSG", "Lyon", 5, 0)])
    blended_few = blend_team_stats(few_matches, previous_stats, prior_weight_matches=6)

    # Avec beaucoup de matchs similaires cette saison, le poids du prior doit diminuer.
    many_matches = build_team_stats(
        [_match("PSG", "Lyon", 5, 0)] * 20  # 20 matchs à domicile identiques
    )
    blended_many = blend_team_stats(many_matches, previous_stats, prior_weight_matches=6)

    # Le prior tire la moyenne "few" vers le bas (2 buts/match la saison passée) ;
    # avec beaucoup de matchs cette saison, la moyenne doit s'en rapprocher de 5.
    assert blended_few.get("PSG").avg_home_scored < blended_many.get("PSG").avg_home_scored
    assert blended_many.get("PSG").avg_home_scored > 4.0


def test_compute_league_averages_falls_back_to_previous_season_defaults_when_both_empty():
    league_avg = compute_league_averages([], previous_season_matches=[])
    assert league_avg.avg_home_goals == 1.5
    assert league_avg.avg_away_goals == 1.2


def test_compute_league_averages_blends_previous_season_when_current_is_empty():
    league_avg = compute_league_averages([], previous_season_matches=PREVIOUS_SEASON_MATCHES)
    # Avec 0 match cette saison, la moyenne doit être exactement celle de la
    # saison précédente (shrinkage total vers le prior).
    _, _, prev_count = (
        sum(m["score"]["fullTime"]["home"] for m in PREVIOUS_SEASON_MATCHES),
        sum(m["score"]["fullTime"]["away"] for m in PREVIOUS_SEASON_MATCHES),
        len(PREVIOUS_SEASON_MATCHES),
    )
    expected_home_avg = sum(m["score"]["fullTime"]["home"] for m in PREVIOUS_SEASON_MATCHES) / prev_count
    assert math.isclose(league_avg.avg_home_goals, expected_home_avg)


def test_compute_league_averages_without_previous_season_matches_current_only_behavior():
    # Sans saison précédente fournie, le comportement doit être identique à avant
    # (moyenne calculée uniquement sur la saison en cours).
    baseline = compute_league_averages(FINISHED_MATCHES)
    with_none = compute_league_averages(FINISHED_MATCHES, previous_season_matches=None)
    assert baseline == with_none


def test_predict_match_probabilities_still_sum_to_one_with_multipliers():
    stats = build_team_stats(FINISHED_MATCHES)
    league_avg = compute_league_averages(FINISHED_MATCHES)

    prediction = predict_match("PSG", "Nice", stats, league_avg, strength_multipliers=(1.25, 0.75))

    total_prob = prediction.home_win_prob + prediction.draw_prob + prediction.away_win_prob
    assert math.isclose(total_prob, 1.0, abs_tol=1e-6)
