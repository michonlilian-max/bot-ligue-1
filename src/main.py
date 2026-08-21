"""Point d'entrée CLI du bot de prédiction Ligue 1.

Usage:
    python -m src.main                              # prédit la prochaine journée
    python -m src.main --matchday 5                 # prédit une journée précise
    python -m src.main --no-advanced                # ignore les statistiques avancées (API-Football)
    python -m src.main --output predictions/x.md     # écrit aussi le résultat dans un fichier Markdown

Le modèle de base (buts marqués/encaissés, domicile/extérieur) ne nécessite
que la clé football-data.org. Si une clé API-Football (API_FOOTBALL_TOKEN)
est également configurée, le pronostic est affiné avec la forme récente, les
confrontations directes, la discipline (cartons) et l'expérience de
l'effectif (voir src/advanced_stats.py).

`--output` sert notamment à l'exécution automatisée via GitHub Actions (voir
.github/workflows/predictions.yml) : le fichier généré est commité dans le
dépôt à chaque exécution.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from tabulate import tabulate

from src.advanced_stats import (
    AdvancedSignals,
    compute_strength_multipliers,
    extract_discipline,
    parse_form_string,
    summarize_head_to_head,
)
from src import config
from src.api_football_client import ApiFootballClient, ApiFootballError
from src.data_fetcher import FootballDataClient, FootballDataError
from src.predictor import blend_team_stats, build_team_stats, compute_league_averages, predict_match


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

    try:
        home_id = client.find_team_id(home_name)
        away_id = client.find_team_id(away_name)
        if home_id is None or away_id is None:
            print(
                f"Avertissement: équipe non trouvée sur API-Football ({home_name} / {away_name}), "
                "statistiques avancées ignorées pour ce match.",
                file=sys.stderr,
            )
            return None, {}

        home_stats_json = client.get_team_statistics(home_id)
        away_stats_json = client.get_team_statistics(away_id)
        h2h_fixtures = client.get_head_to_head(home_id, away_id, last=5)
        home_avg_age = client.get_squad_average_age(home_id)
        away_avg_age = client.get_squad_average_age(away_id)
    except ApiFootballError as exc:
        # N'importe quel appel API-Football ci-dessus peut échouer (plan
        # gratuit ne couvrant pas la saison en cours, quota dépassé, etc.) :
        # on se rabat silencieusement sur le modèle de base pour ce match.
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


def _write_output(path: str, content: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def run(matchday: int | None = None, use_advanced: bool = True, output: str | None = None) -> int:
    client = FootballDataClient()
    advanced_client = ApiFootballClient() if use_advanced else ApiFootballClient(api_key="")

    if advanced_client.is_configured:
        # Test unique en amont plutôt qu'un essai par match : évite de
        # gaspiller le quota gratuit (100 req/jour) si les statistiques
        # avancées sont indisponibles pour une raison durable (plan gratuit
        # ne couvrant pas la saison en cours, quota déjà dépassé, etc.).
        try:
            advanced_client.find_team_id("_probe_")
        except ApiFootballError as exc:
            print(
                f"Avertissement: statistiques avancées désactivées pour cette exécution ({exc})",
                file=sys.stderr,
            )
            advanced_client = ApiFootballClient(api_key="")

    try:
        finished = client.fetch_finished_matches()
    except FootballDataError as exc:
        # Erreur bloquante (jeton invalide, API indisponible, etc.) : on ne
        # génère pas de fichier de sortie et on remonte un code d'erreur, pour
        # que l'exécution automatisée (GitHub Actions) apparaisse en échec.
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1

    # En tout début de saison (peu ou pas de matchs joués), on complète avec
    # le classement/les stats de la saison précédente (voir
    # predictor.blend_team_stats). Erreur non bloquante : on continue avec la
    # seule saison en cours si la saison précédente n'est pas disponible.
    previous_season = config.current_season() - 1
    try:
        previous_finished = client.fetch_finished_matches(season=previous_season)
    except FootballDataError as exc:
        print(
            f"Avertissement: saison précédente ({previous_season}) indisponible ({exc}), "
            "poursuite avec la seule saison en cours.",
            file=sys.stderr,
        )
        previous_finished = []

    if not finished and not previous_finished:
        message = (
            f"# Pronostics Ligue 1\n\n_Généré le {_timestamp()}._\n\n"
            "Aucun match terminé trouvé, ni pour la saison en cours ni pour la saison "
            "précédente : impossible de calculer des statistiques fiables.\n"
        )
        print(message, file=sys.stderr)
        if output:
            _write_output(output, message)
        return 0

    current_stats = build_team_stats(finished)
    if previous_finished:
        stats = blend_team_stats(current_stats, build_team_stats(previous_finished))
        league_avg = compute_league_averages(finished, previous_season_matches=previous_finished)
        if len(finished) < config.PRIOR_SEASON_WEIGHT_MATCHES * 2:
            print(
                f"Note: seulement {len(finished)} match(s) joué(s) cette saison — "
                f"les stats de la saison {previous_season}-{previous_season + 1} sont utilisées en complément.",
                file=sys.stderr,
            )
    else:
        stats = current_stats
        league_avg = compute_league_averages(finished)

    if matchday:
        upcoming = client.fetch_scheduled_matches(matchday=matchday)
        target_matchday = matchday
    else:
        target_matchday, upcoming = client.fetch_next_matchday()

    if not upcoming:
        message = (
            f"# Pronostics Ligue 1\n\n_Généré le {_timestamp()}._\n\n"
            "Aucun match à venir trouvé (probablement hors-saison ou entre deux journées).\n"
        )
        print(message, file=sys.stderr)
        if output:
            _write_output(output, message)
        return 0

    mode = "modèle avancé" if advanced_client.is_configured else "modèle de base"
    title = f"Pronostics Ligue 1 — journée {target_matchday}"
    if advanced_client.is_configured:
        print(f"\n{title} ({mode})\n")
    else:
        print(
            f"\n{title} ({mode} : définissez API_FOOTBALL_TOKEN pour activer "
            "forme/H2H/discipline/expérience)\n"
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
    table = tabulate(rows, headers=headers, tablefmt="github")
    print(table)

    if output:
        markdown = f"# {title}\n\n_Généré le {_timestamp()} ({mode})._\n\n{table}\n"
        _write_output(output, markdown)

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
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Écrit également le résultat dans ce fichier Markdown (ex: predictions/derniere-journee.md)",
    )
    args = parser.parse_args()
    sys.exit(run(matchday=args.matchday, use_advanced=not args.no_advanced, output=args.output))


if __name__ == "__main__":
    main()
