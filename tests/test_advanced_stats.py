"""Tests des statistiques avancées et de l'indice de force composite (données synthétiques)."""
from src.advanced_stats import (
    AdvancedSignals,
    TeamDiscipline,
    TeamForm,
    compute_strength_multipliers,
    extract_discipline,
    parse_form_string,
    summarize_head_to_head,
)
from src.config import MAX_STRENGTH_ADJUSTMENT


def test_parse_form_string_counts_points_correctly():
    form = parse_form_string("LWWDW")
    assert form.wins == 3
    assert form.draws == 1
    assert form.losses == 1
    assert form.points == 3 + 3 + 1 + 3  # W=3, W=3, D=1, W=3


def test_parse_form_string_keeps_only_last_five():
    # Sept résultats fournis, seuls les 5 derniers doivent compter.
    form = parse_form_string("WWLLLLL")
    assert form.wins == 0
    assert form.losses == 5
    assert form.points == 0


def test_parse_form_string_handles_empty_input():
    assert parse_form_string(None) == TeamForm()
    assert parse_form_string("") == TeamForm()


def test_extract_discipline_sums_intervals():
    team_statistics = {
        "cards": {
            "yellow": {
                "0-15": {"total": 2, "percentage": "20%"},
                "16-30": {"total": None, "percentage": None},
                "31-45": {"total": 3, "percentage": "30%"},
            },
            "red": {
                "0-15": {"total": None, "percentage": None},
                "76-90": {"total": 1, "percentage": "10%"},
            },
        },
        "fixtures": {"played": {"total": 10}},
    }

    discipline = extract_discipline(team_statistics)

    assert discipline.yellow_cards == 5
    assert discipline.red_cards == 1
    assert discipline.matches_played == 10
    # (5 jaunes + 1 rouge * 2) / 10 matchs
    assert discipline.cards_per_match == 0.7


def test_summarize_head_to_head_from_home_perspective():
    fixtures = [
        # PSG (id=1) reçoit et gagne 2-0
        {"teams": {"home": {"id": 1}, "away": {"id": 2}}, "goals": {"home": 2, "away": 0}},
        # PSG (id=1) se déplace et perd 3-1 (donc défaite du point de vue de l'équipe 1)
        {"teams": {"home": {"id": 2}, "away": {"id": 1}}, "goals": {"home": 3, "away": 1}},
        # Match nul
        {"teams": {"home": {"id": 1}, "away": {"id": 2}}, "goals": {"home": 1, "away": 1}},
    ]

    summary = summarize_head_to_head(fixtures, home_team_id=1)

    assert summary.matches_considered == 3
    assert summary.home_wins == 1
    assert summary.away_wins == 1
    assert summary.draws == 1


def test_summarize_head_to_head_skips_unfinished_matches():
    fixtures = [{"teams": {"home": {"id": 1}, "away": {"id": 2}}, "goals": {"home": None, "away": None}}]
    summary = summarize_head_to_head(fixtures, home_team_id=1)
    assert summary.matches_considered == 0


def test_compute_strength_multipliers_favors_team_with_better_form():
    home = AdvancedSignals(form=TeamForm(points=15, wins=5), discipline=TeamDiscipline())
    away = AdvancedSignals(form=TeamForm(points=0, losses=5), discipline=TeamDiscipline())

    home_mult, away_mult = compute_strength_multipliers(home, away)

    assert home_mult > 1.0
    assert away_mult < 1.0


def test_compute_strength_multipliers_are_bounded():
    # Signaux extrêmes dans toutes les dimensions pour vérifier le plafond.
    home = AdvancedSignals(
        form=TeamForm(points=15),
        discipline=TeamDiscipline(yellow_cards=0, red_cards=0, matches_played=10),
        avg_squad_age=30,
    )
    away = AdvancedSignals(
        form=TeamForm(points=0),
        discipline=TeamDiscipline(yellow_cards=50, red_cards=10, matches_played=10),
        avg_squad_age=18,
    )
    from src.advanced_stats import HeadToHeadSummary

    h2h = HeadToHeadSummary(home_wins=5, draws=0, away_wins=0, matches_considered=5)

    home_mult, away_mult = compute_strength_multipliers(home, away, h2h)

    assert home_mult == 1 + MAX_STRENGTH_ADJUSTMENT
    assert away_mult == 1 - MAX_STRENGTH_ADJUSTMENT


def test_compute_strength_multipliers_neutral_when_no_data():
    home = AdvancedSignals(form=TeamForm(), discipline=TeamDiscipline())
    away = AdvancedSignals(form=TeamForm(), discipline=TeamDiscipline())

    home_mult, away_mult = compute_strength_multipliers(home, away)

    assert home_mult == 1.0
    assert away_mult == 1.0
