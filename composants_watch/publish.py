"""Génération de deals.json et publication git (jeton passé par en-tête, jamais stocké)."""
from __future__ import annotations

import base64
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_payload(scored: dict, health: dict, now: datetime, version: int = 1,
                  down_after: int = 5) -> dict:
    sources = {}
    for name, h in health.items():
        if h.get("disabled"):
            sources[name] = {"status": "disabled", "items": 0, "last_ok": None}
        else:
            status = "down" if h.get("consecutive_failures", 0) >= down_after else "ok"
            sources[name] = {"status": status, "items": h.get("items", 0), "last_ok": h.get("last_ok")}
    return {"generated_at": _iso(now), "version": version, "sources": sources, **scored}


def _comparable(d: dict) -> dict:
    """Contenu sans les horodatages qui bougent à chaque passe."""
    out = {k: v for k, v in d.items() if k != "generated_at"}
    out["sources"] = {n: {k: v for k, v in s.items() if k != "last_ok"}
                      for n, s in (d.get("sources") or {}).items()}
    return out


def write_json(payload: dict, path: Path) -> bool:
    """Écrit atomiquement si le contenu a changé ; renvoie True si écrit."""
    path = Path(path)
    if path.exists():
        try:
            if _comparable(json.loads(path.read_text(encoding="utf-8"))) == _comparable(payload):
                return False
        except ValueError:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    return True


def _git(repo: Path, *args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    # Le jeton passe par l'environnement (lisible par le seul utilisateur), jamais
    # par la ligne de commande (visible dans ps et dans le message de TimeoutExpired).
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", **(env_extra or {}))
    return subprocess.run(["git", *args], cwd=repo, capture_output=True,
                          text=True, timeout=120, env=env)


def git_push(repo: Path, rel_path: str, token_path: Path, now: datetime) -> tuple[bool, str]:
    repo = Path(repo)
    try:
        _git(repo, "add", "--", rel_path)
        if _git(repo, "diff", "--cached", "--quiet", "--", rel_path).returncode == 1:
            c = _git(repo, "commit", "-q", "-m", f"data: mise à jour {_iso(now)}", "--", rel_path)
            if c.returncode != 0:
                return False, f"commit impossible : {c.stderr.strip()[-300:]}"
        url = _git(repo, "remote", "get-url", "origin").stdout.strip()
        env_extra: dict = {}
        token = ""
        if url.startswith("https://"):
            token_path = Path(token_path)
            if not token_path.exists():
                return False, "token absent"
            token = token_path.read_text(encoding="utf-8").strip()
            basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
            env_extra = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.extraHeader",
                         "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}"}
        p = _git(repo, "push", "-q", "origin", "HEAD:main", env_extra=env_extra)
    except subprocess.TimeoutExpired:
        return False, "push : délai dépassé"
    except OSError as e:
        return False, f"git indisponible : {e.strerror}"
    if p.returncode != 0:
        msg = p.stderr.strip()
        if token:
            msg = msg.replace(token, "***")
        return False, f"push échoué : {msg[-300:]}"
    return True, "ok"
