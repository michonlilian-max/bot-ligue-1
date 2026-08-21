# bot-ligue-1

Bot de prédiction Ligue 1 : pronostics 1N2 (victoire domicile / nul /
victoire extérieur) et score exact pour les matchs de Ligue 1 à venir.

## Comment ça marche

### 1. Modèle de base — loi de Poisson

Approche statistique classique en prédiction football :

1. Récupération des résultats des matchs déjà joués dans la saison via
   l'API [football-data.org](https://www.football-data.org/).
2. Calcul, pour chaque équipe, de sa force offensive et défensive, à
   domicile et à l'extérieur (déjà une prise en compte du facteur
   **domicile/extérieur**).
3. Déduction du nombre de buts attendus (λ) pour chaque équipe d'un
   match à venir, puis calcul de la probabilité de chaque score exact
   possible avec une loi de Poisson.
4. Somme de ces probabilités pour obtenir le pronostic 1N2, et
   sélection du score le plus probable comme score exact prédit.

### 2. Statistiques avancées (optionnel) — indice de force composite

Si une clé [API-Football](https://dashboard.api-football.com/) est
configurée, le pronostic est affiné en ajustant les buts attendus (λ)
avec un indice composite tenant compte de :

- **forme récente** : résultats des 5 derniers matchs de chaque équipe ;
- **confrontations directes** : résultats des 5 derniers face-à-face
  entre les deux équipes ;
- **discipline** : cartons jaunes/rouges par match (un rouge compte
  double d'un jaune) ;
- **expérience de l'effectif** : âge moyen du groupe, utilisé comme
  proxy — l'API gratuite ne fournit pas le nombre de matchs joués en
  carrière par joueur.

Ces quatre signaux sont combinés (pondération dans `src/config.py`,
`FORM_WEIGHT`/`H2H_WEIGHT`/`DISCIPLINE_WEIGHT`/`EXPERIENCE_WEIGHT`) en
un score de -1 à +1 représentant le **rapport de force global** entre
les deux équipes, qui module ensuite les buts attendus de chaque
équipe (jusqu'à ±25%, `MAX_STRENGTH_ADJUSTMENT`). Voir
`src/advanced_stats.py` pour le détail du calcul.

Sans clé API-Football, le bot fonctionne quand même, avec le modèle de
base uniquement (colonnes forme/H2H affichées à `-`).

### Facteurs volontairement non inclus

**Masse salariale et prix d'achat des joueurs** ne sont pas intégrés :
il n'existe pas d'API gratuite officielle et fiable pour ces données
(Transfermarkt, la référence du secteur, n'a pas d'API publique et son
scraping irait à l'encontre de ses conditions d'utilisation). Piste
pour une prochaine évolution : maintenir un fichier `data/effectifs.json`
renseigné manuellement (masse salariale, valeur d'effectif par club) et
l'intégrer comme signal supplémentaire dans `compute_strength_multipliers`.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Éditez `.env` et renseignez :

- `FOOTBALL_DATA_API_TOKEN` (obligatoire) : jeton gratuit sur
  [football-data.org/client/register](https://www.football-data.org/client/register).
- `API_FOOTBALL_TOKEN` (optionnel, pour les statistiques avancées) :
  jeton gratuit (100 requêtes/jour) sur
  [dashboard.api-football.com](https://dashboard.api-football.com/).

## Utilisation

```bash
# Prédire la prochaine journée (avec statistiques avancées si API_FOOTBALL_TOKEN est configuré)
python -m src.main

# Prédire une journée précise
python -m src.main --matchday 5

# Forcer le modèle de base uniquement, même si API_FOOTBALL_TOKEN est configuré
python -m src.main --no-advanced
```

Exemple de sortie (modèle avancé) :

```
Prédictions Ligue 1 — journée 5 (modèle avancé)

| Domicile | Extérieur | 1   | N   | 2   | Pronostic | Score probable | Forme dom. | Forme ext. | H2H (dom. perspective) |
|----------|-----------|-----|-----|-----|-----------|-----------------|------------|------------|------------------------|
| PSG      | Nice      | 68% | 20% | 12% | 1         | 2-0             | 13/15      | 6/15       | 3V 1N 1D               |
| Lyon     | Marseille | 35% | 27% | 38% | 2         | 1-2             | 7/15       | 12/15      | 1V 2N 2D               |
```

Un appel API-Football est mis en cache localement (`.cache/`, 6h de
durée de vie) pour ne pas gaspiller le quota gratuit lors de
relances rapprochées.

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
├── config.py             # configuration (jetons API, pondérations, constantes)
├── data_fetcher.py       # client API football-data.org (calendrier, résultats)
├── api_football_client.py # client API-Football (forme, cartons, H2H, effectifs)
├── advanced_stats.py     # indice de force composite (forme/H2H/discipline/expérience)
├── predictor.py           # modèle de prédiction (Poisson + ajustement de force)
├── cache.py                # cache disque pour limiter les appels API-Football
└── main.py                 # point d'entrée CLI
tests/
├── test_predictor.py     # tests du modèle de prédiction
└── test_advanced_stats.py # tests des statistiques avancées
```

## Limites connues

- Le modèle ne prend en compte que les statistiques de la saison en
  cours (pas d'historique multi-saisons).
- En tout début de saison, les statistiques sont peu fiables (peu de
  matchs joués par équipe, forme et H2H sur des échantillons réduits).
- L'expérience de l'effectif est approximée par l'âge moyen du groupe,
  faute de données de carrière par joueur dans l'offre gratuite.
- Pas de prise en compte des blessures/suspensions individuelles, ni
  de la masse salariale/valeur de marché des effectifs (voir ci-dessus).
- Les noms d'équipes entre football-data.org et API-Football sont
  rapprochés automatiquement (`difflib`) : à vérifier en cas de nom
  ambigu ou de nouvelle équipe promue.
