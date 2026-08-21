"""Configuration du bot : chargement des variables d'environnement."""
import os
from datetime import date

from dotenv import load_dotenv

load_dotenv()

# --- football-data.org (calendrier et résultats des matchs) ---
# Jeton d'API football-data.org (https://www.football-data.org/client/register)
FOOTBALL_DATA_API_TOKEN = os.getenv("FOOTBALL_DATA_API_TOKEN", "")

# Code de la compétition Ligue 1 sur football-data.org
COMPETITION_CODE = "FL1"

# URL de base de l'API
API_BASE_URL = "https://api.football-data.org/v4"

# Nombre de buts maximum considéré pour le calcul des probabilités de score exact
MAX_GOALS = 6


# --- API-Football / api-sports.io (statistiques avancées) ---
# Jeton gratuit (100 requêtes/jour) sur https://dashboard.api-football.com/
# Utilisé pour : forme récente, cartons jaunes/rouges, confrontations directes,
# effectifs (âge moyen). Optionnel : si absent, le bot se rabat sur le modèle
# de base (buts marqués/encaissés uniquement).
API_FOOTBALL_TOKEN = os.getenv("API_FOOTBALL_TOKEN", "")
API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"

# Identifiant de la compétition Ligue 1 (France) sur API-Football
API_FOOTBALL_LEAGUE_ID = 61


def current_season() -> int:
    """Retourne l'année de départ de la saison en cours (ex: 2025 pour 2025-2026).

    La saison de Ligue 1 démarre en général en août : avant juillet, on
    considère donc qu'on est encore dans la saison ayant démarré l'année
    précédente.
    """
    today = date.today()
    return today.year if today.month >= 7 else today.year - 1


# Saison API-Football à interroger. Peut être forcée via la variable
# d'environnement API_FOOTBALL_SEASON (ex: 2024), sinon calculée automatiquement.
_season_override = os.getenv("API_FOOTBALL_SEASON", "")
API_FOOTBALL_SEASON = int(_season_override) if _season_override else current_season()

# Répertoire de cache disque (réponses API-Football), pour ne pas gaspiller le
# quota gratuit quand on relance le bot plusieurs fois dans la journée.
CACHE_DIR = os.getenv("CACHE_DIR", ".cache")
CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 heures


# --- Pondération de l'indice de force additionnel ---
# Le modèle de base (buts marqués/encaissés, cf. predictor.expected_goals) est
# ajusté par un indice composite combinant forme récente, confrontations
# directes, discipline (cartons) et expérience de l'effectif. Les poids
# ci-dessous doivent sommer à 1.0.
FORM_WEIGHT = 0.40          # forme sur les 5 derniers matchs
H2H_WEIGHT = 0.25           # confrontations directes (5 dernières)
DISCIPLINE_WEIGHT = 0.15    # cartons jaunes/rouges par match
EXPERIENCE_WEIGHT = 0.20    # âge moyen de l'effectif (proxy d'expérience)

# Ajustement maximal appliqué aux buts attendus (lambda) : +/- 25%
MAX_STRENGTH_ADJUSTMENT = 0.25


# --- Prise en compte de la saison précédente ---
# En tout début de saison (peu ou pas de matchs joués), les moyennes de buts
# de la saison en cours sont mélangées à celles de la saison précédente (voir
# predictor.blend_team_stats et predictor.compute_league_averages), pour
# éviter des prédictions non fiables basées sur un échantillon trop petit.
#
# PRIOR_SEASON_WEIGHT_MATCHES fixe le nombre de matchs "virtuels" de la
# saison précédente injectés dans la moyenne de chaque équipe : plus il est
# grand, plus il faut de matchs joués cette saison pour que l'effet de la
# saison précédente s'estompe complètement.
PRIOR_SEASON_WEIGHT_MATCHES = 6
