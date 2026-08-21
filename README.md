# bot-ligue-1

Bot de prédiction Ligue 1 : pronostics 1N2 (victoire domicile / nul /
victoire extérieur) et score exact pour les matchs de Ligue 1 à venir.

## Comment ça marche

Le bot utilise un modèle statistique de type **loi de Poisson**, une
approche classique en prédiction football :

1. Il récupère les résultats des matchs déjà joués dans la saison via
   l'API [football-data.org](https://www.football-data.org/).
2. Il calcule pour chaque équipe sa force offensive et défensive, à
   domicile et à l'extérieur.
3. Il en déduit le nombre de buts attendus (λ) pour chaque équipe d'un
   match à venir, puis calcule la probabilité de chaque score exact
   possible avec une loi de Poisson.
4. Il additionne ces probabilités pour obtenir le pronostic 1N2, et
   retient le score le plus probable comme score exact prédit.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Éditez `.env` et renseignez votre jeton API gratuit obtenu sur
[football-data.org/client/register](https://www.football-data.org/client/register).

## Utilisation

```bash
# Prédire la prochaine journée
python -m src.main

# Prédire une journée précise
python -m src.main --matchday 5
```

Exemple de sortie :

```
Prédictions Ligue 1 — journée 5

| Domicile   | Extérieur   | 1   | N   | 2   | Pronostic   | Score probable   |
|------------|-------------|-----|-----|-----|-------------|------------------|
| PSG        | Nice        | 62% | 24% | 14% | 1           | 2-0              |
| Lyon       | Marseille   | 38% | 27% | 35% | 1           | 1-1              |
```

## Tests

```bash
pip install pytest
pytest tests/
```

Les tests utilisent des données synthétiques et ne nécessitent aucun
accès réseau ni clé API.

## Structure du projet

```
src/
├── config.py         # configuration (jeton API, constantes)
├── data_fetcher.py   # client API football-data.org
├── predictor.py       # modèle de prédiction (Poisson)
└── main.py             # point d'entrée CLI
tests/
└── test_predictor.py # tests du modèle de prédiction
```

## Limites connues (v1)

- Le modèle ne prend en compte que les statistiques de la saison en
  cours (pas d'historique multi-saisons, pas de forme récente pondérée,
  pas de blessures/suspensions).
- En tout début de saison, les statistiques sont peu fiables (peu de
  matchs joués par équipe).
