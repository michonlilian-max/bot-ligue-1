"""Tests du dashboard HTML (données synthétiques, pas d'appel réseau)."""
from src.dashboard import MatchRow, OtherMatchRow, render_dashboard


def test_render_dashboard_includes_match_data():
    rows = [
        MatchRow(
            home="Paris Saint-Germain FC",
            away="Nice",
            home_win_prob=0.62,
            draw_prob=0.24,
            away_win_prob=0.14,
            pick="1",
            predicted_score="2-0",
            form_home="13/15",
            form_away="6/15",
            h2h="3V 1N 1D",
        )
    ]

    html = render_dashboard("Pronostics Ligue 1 — journée 5", "Généré le 2026-08-21 06:00 UTC", rows)

    assert "<!doctype html>" in html
    assert "Paris Saint-Germain FC" in html
    assert "Nice" in html
    assert "62%" in html
    assert "2-0" in html
    assert "13/15" in html


def test_render_dashboard_escapes_team_names():
    rows = [
        MatchRow(
            home="<script>alert(1)</script>",
            away="Nice",
            home_win_prob=0.5,
            draw_prob=0.3,
            away_win_prob=0.2,
            pick="1",
            predicted_score="1-0",
            form_home="-",
            form_away="-",
            h2h="-",
        )
    ]

    html = render_dashboard("Titre", "Sous-titre", rows)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_dashboard_empty_state_shows_note():
    html = render_dashboard("Pronostics Ligue 1", "Généré le 2026-08-21", [], note="Aucun match à venir trouvé.")

    assert "Aucun match à venir trouvé." in html
    assert "Aucun pronostic disponible" in html


def test_render_dashboard_without_note_omits_note_block():
    html = render_dashboard("Titre", "Sous-titre", [])
    assert 'class="note"' not in html


def test_render_dashboard_hides_advanced_columns_when_unavailable():
    rows = [
        MatchRow(
            home="PSG",
            away="Nice",
            home_win_prob=0.6,
            draw_prob=0.25,
            away_win_prob=0.15,
            pick="1",
            predicted_score="2-0",
            form_home="-",
            form_away="-",
            h2h="-",
        )
    ]

    html = render_dashboard("Titre", "Sous-titre", rows, show_advanced=False)

    assert "Forme dom." not in html
    assert "Forme ext." not in html
    assert "<th>H2H</th>" not in html


def test_render_dashboard_shows_advanced_columns_by_default():
    rows = [
        MatchRow(
            home="PSG",
            away="Nice",
            home_win_prob=0.6,
            draw_prob=0.25,
            away_win_prob=0.15,
            pick="1",
            predicted_score="2-0",
            form_home="13/15",
            form_away="6/15",
            h2h="3V 1N 1D",
        )
    ]

    html = render_dashboard("Titre", "Sous-titre", rows)

    assert "Forme dom." in html
    assert "13/15" in html


def test_render_dashboard_includes_other_matches_section():
    other = [OtherMatchRow(home="Marseille", away="Strasbourg", status_label="En cours", score="0-0")]

    html = render_dashboard("Titre", "Sous-titre", [], other_matches=other)

    assert "Autres matchs de la journée" in html
    assert "Marseille" in html
    assert "En cours" in html
    assert "0-0" in html


def test_render_dashboard_omits_other_matches_section_when_none():
    html = render_dashboard("Titre", "Sous-titre", [])
    assert "Autres matchs de la journée" not in html
