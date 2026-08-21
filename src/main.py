"""Point d'entrée CLI du bot de prédiction Ligue 1.

Usage:
    python -m src.main                 # prédit la prochaine journée
    python -m src.main --matchday 5    # prédit une journée précise
    python -m src.main --no-advanced   # ignore les statistiques avancées (API-Football)

Le modèle de base (buts marqués/encaissés, domicile/extérieur) ne nécessite
que la clé football-data.org. Si une clé API-Football (API_FOOTBALL_TOKEN)
est également configurée, le pronostic est affiné avec la forme récente, les
confrontations directes, la discipline (cartons) et l'expérience de
l'effectif (voir src/advanced_stats.py).
"""
from __future__ import annotations

import argparse
import sys

from tabulate import tabulate

from src.advanced_stats import (
    AdvancedSignals,
    compute_strength_multipliers,
    extract_discipline,
    parse_form_string,
    summarize_head_to_head,
)
from src.api_football_client import ApiFootballClient, ApiFootballError
from src.data_fetcher import FootballDataClient, FootballDataError
from src.predictor import build_team_stats, compute_league_averages, predict_match


def build_advanced_context(
    client: ApiFootballClient, home_name: str, away_name: str
) -> tuple[tuple[float, float] | None, dict[str, str]]:
    """Calcule les multiplicateurs de force avancés pour un match, si possible.

    Retourne (None, {}) si les statistiques avancées ne sont pas disponibles
    (pas de clé API-Football configurée, équipe non retrouvée, erreur API) :
    le bot se rabat alors silencieusement sur le modèle de base.
    """
    if not client.is_configured:
        return None, {}

    home_id = client.find_team_id(home_name)
    away_id = client.find_team_id(away_name)
    if home_id is None or away_id is None:
        print(
            f"Avertissement: équipe non trouvée sur API-Football ({home_name} / {away_name}), "
            "statistiques avancées ignorées pour ce match.",
            file=sys.stderr,
        )
        return None, {}

    try:
        home_stats_json = client.get_team_statistics(home_id)
        away_stats_json = client.get_team_statistics(away_id)
        h2h_fixtures = client.get_head_to_head(home_id, away_id, last=5)
        home_avg_age = client.get_squad_average_age(home_id)
        away_avg_age = client.get_squad_average_age(away_id)
    except ApiFootballError as exc:
        print(f"Avertissement: statistiques avancées indisponibles ({exc})", file=sys.stderr)
        return None, {}

    home_signals = AdvancedSignals(
        form=parse_form_string(home_stats_json.get("form")),
        discipline=extract_discipline(home_stats_json),
        avg_squad_age=home_avg_age,
    )
    away_signals = AdvancedSignals(
        form=parse_form_string(away_stats_json.get("form")),
        discipline=extract_discipline(away_stats_json),
        avg_squad_age=away_avg_age,
    )
    h2h_summary = summarize_head_to_head(h2h_fixtures, home_id, last=5)

    multipliers = compute_strength_multipliers(home_signals, away_signals, h2h_summary)

    info = {
        "forme_dom": f"{home_signals.form.points}/15",
        "forme_ext": f"{away_signals.form.points}/15",
        "h2h": f"{h2h_summary.home_wins}V {h2h_summary.draws}N {h2h_summary.away_wins}D",
    }
    return multipliers, info


def run(matchday: int | None = None, use_advanced: bool = True) -> int:
    client = FootballDataClient()
    advanced_client = ApiFootballClient() if use_advanced else ApiFootballClient(api_key="")

    try:
        finished = client.fetch_finished_matches()
    except FootballDataError as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1

    if not finished:
        print(
            "Aucun match terminé trouvé pour la saison en cours : "
            "impossible de calculer des statistiques fiables.",
            file=sys.stderr,
        )
        return 1

    stats = build_team_stats(finished)
    league_avg = compute_league_averages(finished)

    if matchday:
        upcoming = client.fetch_scheduled_matches(matchday=matchday)
        target_matchday = matchday
    else:
        target_matchday, upcoming = client.fetch_next_matchday()

    if not upcoming:
        print("Aucun match à venir trouvé.", file=sys.stderr)
        return 1

    if advanced_client.is_configured:
        print(f"\nPrédictions Ligue 1 — journée {target_matchday} (modèle avancé)\n")
    else:
        print(
            f"\nPrédictions Ligue 1 — journée {target_matchday} (modèle de base : "
            "définissez API_FOOTBALL_TOKEN pour activer forme/H2H/discipline/expérience)\n"
        )

    rows = []
    for match in upcoming:
        home = match["homeTeam"]["name"]
        away = match["awayTeam"]["name"]

        multipliers, info = build_advanced_context(advanced_client, home, away)
        prediction = predict_match(home, away, stats, league_avg, strength_multipliers=multipliers)

        score_h, score_a = prediction.predicted_score
        rows.append(
            [
                home,
                away,
                f"{prediction.home_win_prob:.0%}",
                f"{prediction.draw_prob:.0%}",
                f"{prediction.away_win_prob:.0%}",
                prediction.most_likely_result,
                f"{score_h}-{score_a}",
                info.get("forme_dom", "-"),
                info.get("forme_ext", "-"),
                info.get("h2h", "-"),
            ]
        )

    headers = [
        "Domicile",
        "Extérieur",
        "1",
        "N",
        "2",
        "Pronostic",
        "Score probable",
        "Forme dom.",
        "Forme ext.",
        "H2H (dom. perspective)",
    ]
    print(tabulate(rows, headers=headers, tablefmt="github"))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Bot de prédiction Ligue 1")
    parser.add_argument(
        "--matchday",
        type=int,
        default=None,
        help="Numéro de la journée à prédire (par défaut : la prochaine journée à venir)",
    )
    parser.add_argument(
        "--no-advanced",
        action="store_true",
        help="Désactive les statistiques avancées (API-Football), même si une clé est configurée",
    )
    args = parser.parse_args()
    sys.exit(run(matchday=args.matchday, use_advanced=not args.no_advanced))


if __name__ == "__main__":
    main()
