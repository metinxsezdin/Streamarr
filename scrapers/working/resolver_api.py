#!/usr/bin/env python3
"""
Flask API exposing the on-demand stream resolver for integration with Jellyfin.

Endpoints:
    GET /health
        Simple heartbeat check.
    POST /resolve
        Resolve a given streaming page URL. Body JSON:
            {
                "url": "...",              # required
                "site": "dizibox|hdfilm",  # optional hint
                "headed": false,           # optional debug flag
                "verbose": false           # include scraper logs
            }
        Response contains a temporary token and metadata.
    GET /stream/<token>
        Retrieve cached stream details. By default responds with HTTP redirect
        to the proxied stream URL. Append `?format=json` for metadata.
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple
from urllib.parse import quote_plus

from flask import Flask, jsonify, redirect, request

from stream_resolver import resolve_stream, SUPPORTED_SITES
from catalog_store import load_catalog, get_entry

app = Flask(__name__)

TOKEN_TTL_SECONDS = 5 * 60  # 5 minutes
PROXY_BASE_URL = os.environ.get("PROXY_BASE_URL")
CATALOG_PATH = Path(os.environ.get("CATALOG_PATH", Path(__file__).resolve().parent / "data/catalog.json"))
_token_cache: Dict[str, Dict] = {}
_catalog_index: Dict[str, Dict] = load_catalog(CATALOG_PATH)


def _cleanup_expired() -> None:
    now = time.time()
    expired = [token for token, payload in _token_cache.items() if payload["expires_at"] <= now]
    for token in expired:
        _token_cache.pop(token, None)


def _store_token(data: Dict) -> Tuple[str, float]:
    _cleanup_expired()
    token = uuid.uuid4().hex
    expires_at = time.time() + TOKEN_TTL_SECONDS
    _token_cache[token] = {"data": data, "expires_at": expires_at}
    return token, expires_at


def _resolve_stream_url(site: str, result: Dict) -> str:
    if site == "dizibox":
        base = result.get("quality_url") if PROXY_BASE_URL else result.get("proxy_url") or result.get("quality_url")
    elif site == "hdfilm":
        base = result.get("master_url")
    else:
        base = ""
    return _apply_proxy(site, base, result)


def _apply_proxy(site: str, stream_url: str, result: Dict) -> str:
    if not stream_url:
        return ""
    proxy_base = PROXY_BASE_URL.rstrip("/") if PROXY_BASE_URL else None
    if proxy_base:
        encoded = quote_plus(stream_url, safe="")
        return f"{proxy_base}/stream/{encoded}"
    if site == "dizibox":
        return result.get("proxy_url") or stream_url
    return stream_url


@app.get("/health")
def health() -> tuple[dict, int]:
    return {"status": "ok", "cache_size": len(_token_cache)}, 200


@app.post("/resolve")
def resolve_route() -> tuple[dict, int]:
    payload = request.get_json(force=True, silent=True) or {}
    content_id = payload.get("id")
    url = payload.get("url")
    site = payload.get("site")

    if content_id:
        entry = get_entry(_catalog_index, content_id)
        if not entry:
            return {"error": f"Unknown id '{content_id}'"}, 404
        url = entry.get("url")
        site = entry.get("site")

    if not url:
        return {"error": "Missing 'url' field"}, 400

    if site and site not in SUPPORTED_SITES:
        return {"error": f"Unsupported site '{site}'"}, 400

    headed = bool(payload.get("headed", False))
    verbose = bool(payload.get("verbose", False))

    try:
        data = resolve_stream(
            url,
            site=site,
            headless=not headed,
            quiet=not verbose,
        )
    except Exception as exc:
        return {"error": str(exc)}, 500

    token, expires_at_ts = _store_token(data)
    expires_at_iso = datetime.fromtimestamp(expires_at_ts, tz=timezone.utc).isoformat()
    stream_url = _resolve_stream_url(data["site"], data["result"])

    response = {
        "token": token,
        "expires_at": expires_at_iso,
        "proxy_url": f"/stream/{token}",
        "redirect_url": f"/stream/{token}",
        "stream_url": stream_url,
        "resolver": data,
    }
    return jsonify(response), 200


@app.get("/stream/<token>")
def stream_route(token: str) -> tuple[dict, int]:
    _cleanup_expired()
    payload = _token_cache.get(token)
    if not payload:
        return {"error": "Token not found or expired"}, 404

    data = payload["data"]
    expires_at_iso = datetime.fromtimestamp(payload["expires_at"], tz=timezone.utc).isoformat()
    stream_url = _resolve_stream_url(data["site"], data["result"])
    if not stream_url:
        return {"error": "No stream URL available for this token"}, 500

    response = {
        "site": data["site"],
        "original_url": data["url"],
        "stream_url": stream_url,
        "expires_at": expires_at_iso,
        "details": data["result"],
    }
    if request.args.get("format") == "json":
        return jsonify(response), 200
    return redirect(stream_url, code=302)


@app.get("/play/<path:content_id>")
def play_route(content_id: str):
    entry = get_entry(_catalog_index, content_id)
    if not entry:
        return {"error": "Unknown id"}, 404

    site = entry.get("site")
    if site not in SUPPORTED_SITES:
        return {"error": f"Unsupported site '{site}'"}, 400

    try:
        data = resolve_stream(
            entry["url"],
            site=site,
            headless=True,
            quiet=False,
        )
    except Exception as exc:
        return {"error": str(exc)}, 500

    token, expires_at_ts = _store_token(data)
    if request.args.get("format") == "json":
        expires_iso = datetime.fromtimestamp(expires_at_ts, tz=timezone.utc).isoformat()
        stream_url = _resolve_stream_url(data["site"], data["result"])
        return jsonify(
            {
                "token": token,
                "expires_at": expires_iso,
                "stream_url": stream_url,
                "resolver": data,
            }
        ), 200

    return redirect(f"/stream/{token}", code=302)


def create_app() -> Flask:
    """Factory for WSGI servers."""
    return app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5055, debug=False)
