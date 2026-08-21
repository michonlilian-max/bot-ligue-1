"""Point d'entrée CLI du bot de prédiction Ligue 1.

Usage:
    python -m src.main                 # prédit la prochaine journée
    python -m src.main --matchday 5    # prédit une journée précise
"""
from __future__ import annotations

import argparse
import sys

from tabulate import tabulate

from src.data_fetcher import FootballDataClient, FootballDataError
from src.predictor import build_team_stats, compute_league_averages, predict_match


def run(matchday: int | None = None) -> int:
    client = FootballDataClient()

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

    print(f"\nPrédictions Ligue 1 — journée {target_matchday}\n")

    rows = []
    for match in upcoming:
        home = match["homeTeam"]["name"]
        away = match["awayTeam"]["name"]
        prediction = predict_match(home, away, stats, league_avg)
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
            ]
        )

    headers = ["Domicile", "Extérieur", "1", "N", "2", "Pronostic", "Score probable"]
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
    args = parser.parse_args()
    sys.exit(run(matchday=args.matchday))


if __name__ == "__main__":
    main()
