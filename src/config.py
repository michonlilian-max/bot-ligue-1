"""Configuration du bot : chargement des variables d'environnement."""
import os

from dotenv import load_dotenv

load_dotenv()

# Jeton d'API football-data.org (https://www.football-data.org/client/register)
FOOTBALL_DATA_API_TOKEN = os.getenv("FOOTBALL_DATA_API_TOKEN", "")

# Code de la compétition Ligue 1 sur football-data.org
COMPETITION_CODE = "FL1"

# URL de base de l'API
API_BASE_URL = "https://api.football-data.org/v4"

# Nombre de buts maximum considéré pour le calcul des probabilités de score exact
MAX_GOALS = 6
