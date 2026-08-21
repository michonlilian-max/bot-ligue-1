"""Tests du dashboard HTML (données synthétiques, pas d'appel réseau)."""
from src.dashboard import MatchRow, render_dashboard


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
