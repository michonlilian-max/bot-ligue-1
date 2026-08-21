"""Génère un dashboard HTML statique et auto-suffisant à partir des pronostics.

Destiné à être publié via GitHub Pages (voir .github/workflows/predictions.yml
et README.md) : une simple page HTML, sans dépendance externe ni appel
réseau, régénérée à chaque exécution de l'Action.
"""
from __future__ import annotations

import html
from dataclasses import dataclass


@dataclass
class MatchRow:
    """Une ligne de pronostic, prête à être affichée (valeurs déjà formatées)."""

    home: str
    away: str
    home_win_prob: float  # entre 0 et 1
    draw_prob: float
    away_win_prob: float
    pick: str  # "1", "N" ou "2"
    predicted_score: str  # ex: "2-0"
    form_home: str
    form_away: str
    h2h: str


_PICK_LABELS = {"1": "Domicile", "N": "Nul", "2": "Extérieur"}


def _esc(value: str) -> str:
    return html.escape(str(value))


def _prob_bar(label: str, prob: float) -> str:
    pct = round(prob * 100)
    return (
        f'<div class="bar" style="--pct:{pct}%" title="{label}">'
        f'<span>{pct}%</span></div>'
    )


def _row_html(row: MatchRow) -> str:
    pick_label = _PICK_LABELS.get(row.pick, row.pick)
    return f"""
    <tr>
      <td class="teams"><span class="home">{_esc(row.home)}</span> <span class="vs">–</span> <span class="away">{_esc(row.away)}</span></td>
      <td class="prob-cell">{_prob_bar("Victoire domicile", row.home_win_prob)}</td>
      <td class="prob-cell">{_prob_bar("Match nul", row.draw_prob)}</td>
      <td class="prob-cell">{_prob_bar("Victoire extérieur", row.away_win_prob)}</td>
      <td><span class="pick pick-{_esc(row.pick)}">{_esc(pick_label)}</span></td>
      <td class="score">{_esc(row.predicted_score)}</td>
      <td class="muted">{_esc(row.form_home)}</td>
      <td class="muted">{_esc(row.form_away)}</td>
      <td class="muted">{_esc(row.h2h)}</td>
    </tr>"""


def render_dashboard(
    title: str,
    subtitle: str,
    rows: list[MatchRow],
    note: str | None = None,
) -> str:
    """Construit la page HTML complète du dashboard."""
    rows_html = "\n".join(_row_html(row) for row in rows) if rows else ""
    empty_state = (
        ""
        if rows
        else '<p class="empty">Aucun pronostic disponible pour le moment. '
        "Revenez après la prochaine exécution automatique.</p>"
    )
    note_html = f'<p class="note">{_esc(note)}</p>' if note else ""

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>
  :root {{
    --bg: #f6f7f9;
    --surface: #ffffff;
    --border: #e2e5ea;
    --text: #1a1d23;
    --text-muted: #6b7280;
    --accent: #2563eb;
    --accent-soft: #dbeafe;
    --bar-bg: #eef0f4;
    --bar-fill: #93c5fd;
    --bar-fill-strong: #2563eb;
    --pick1: #16a34a;
    --pick-n: #ca8a04;
    --pick2: #dc2626;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0f1115;
      --surface: #171a21;
      --border: #2a2e37;
      --text: #e7e9ee;
      --text-muted: #9aa1ac;
      --accent: #60a5fa;
      --accent-soft: #1e3a5f;
      --bar-bg: #232730;
      --bar-fill: #3b5a8a;
      --bar-fill-strong: #60a5fa;
      --pick1: #4ade80;
      --pick-n: #fbbf24;
      --pick2: #f87171;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.5;
  }}
  main {{
    max-width: 960px;
    margin: 0 auto;
    padding: 32px 20px 64px;
  }}
  header {{
    margin-bottom: 24px;
  }}
  h1 {{
    font-size: 1.6rem;
    margin: 0 0 4px;
  }}
  .subtitle {{
    color: var(--text-muted);
    font-size: 0.95rem;
    margin: 0;
  }}
  .note {{
    background: var(--accent-soft);
    color: var(--text);
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.88rem;
    margin: 16px 0 0;
  }}
  .empty {{
    color: var(--text-muted);
    padding: 40px 0;
    text-align: center;
  }}
  .table-wrap {{
    overflow-x: auto;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    margin-top: 20px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
    min-width: 720px;
  }}
  th, td {{
    padding: 12px 14px;
    text-align: left;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }}
  thead th {{
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-muted);
    font-weight: 600;
  }}
  tbody tr:last-child td {{
    border-bottom: none;
  }}
  tbody tr:hover {{
    background: color-mix(in srgb, var(--accent-soft) 35%, transparent);
  }}
  .teams .home {{ font-weight: 600; }}
  .teams .vs {{ color: var(--text-muted); }}
  .teams .away {{ font-weight: 600; }}
  .prob-cell {{ min-width: 90px; }}
  .bar {{
    position: relative;
    background: var(--bar-bg);
    border-radius: 6px;
    height: 22px;
    overflow: hidden;
  }}
  .bar::before {{
    content: "";
    position: absolute;
    inset: 0;
    width: var(--pct);
    background: var(--bar-fill-strong);
    opacity: 0.85;
  }}
  .bar span {{
    position: relative;
    z-index: 1;
    display: block;
    padding: 2px 8px;
    font-size: 0.78rem;
    font-variant-numeric: tabular-nums;
  }}
  .pick {{
    display: inline-block;
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    color: #fff;
  }}
  .pick-1 {{ background: var(--pick1); }}
  .pick-N {{ background: var(--pick-n); }}
  .pick-2 {{ background: var(--pick2); }}
  .score {{ font-variant-numeric: tabular-nums; font-weight: 600; }}
  .muted {{ color: var(--text-muted); font-size: 0.85rem; }}
  footer {{
    margin-top: 24px;
    color: var(--text-muted);
    font-size: 0.8rem;
  }}
  footer a {{ color: var(--accent); }}
</style>
</head>
<body>
<main>
  <header>
    <h1>{_esc(title)}</h1>
    <p class="subtitle">{_esc(subtitle)}</p>
    {note_html}
  </header>

  {empty_state}
  <div class="table-wrap" {"hidden" if not rows else ""}>
    <table>
      <thead>
        <tr>
          <th>Match</th>
          <th>1</th>
          <th>N</th>
          <th>2</th>
          <th>Pronostic</th>
          <th>Score probable</th>
          <th>Forme dom.</th>
          <th>Forme ext.</th>
          <th>H2H</th>
        </tr>
      </thead>
      <tbody>{rows_html}
      </tbody>
    </table>
  </div>

  <footer>
    Généré automatiquement par
    <a href="https://github.com/michonlilian-max/bot-ligue-1" target="_blank" rel="noopener">bot-ligue-1</a>.
  </footer>
</main>
</body>
</html>
"""
