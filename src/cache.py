"""Cache disque simple (fichiers JSON) pour limiter les appels à l'API-Football.

Le plan gratuit d'API-Football est limité à 100 requêtes/jour : ce cache
évite de refaire les mêmes appels lorsqu'on relance le bot plusieurs fois
dans un court laps de temps.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable

from src import config


def _cache_path(key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return Path(config.CACHE_DIR) / f"{digest}.json"


def cached_call(key: str, fetch_fn: Callable[[], Any], ttl_seconds: int | None = None) -> Any:
    """Retourne le résultat en cache s'il est encore valide, sinon appelle fetch_fn et le met en cache."""
    ttl = ttl_seconds if ttl_seconds is not None else config.CACHE_TTL_SECONDS
    path = _cache_path(key)

    if path.exists():
        try:
            payload = json.loads(path.read_text())
            if time.time() - payload["timestamp"] < ttl:
                return payload["data"]
        except (json.JSONDecodeError, KeyError, OSError):
            pass  # cache corrompu ou illisible : on ignore et on recalcule

    data = fetch_fn()

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"timestamp": time.time(), "data": data}))
    except OSError:
        pass  # le cache est une optimisation, pas une nécessité

    return data
