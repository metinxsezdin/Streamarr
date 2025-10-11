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
        Retrieve cached stream details for playback while token is valid.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Tuple

from flask import Flask, jsonify, request

from stream_resolver import resolve_stream, SUPPORTED_SITES

app = Flask(__name__)

TOKEN_TTL_SECONDS = 5 * 60  # 5 minutes
_token_cache: Dict[str, Dict] = {}


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
        return result.get("proxy_url") or result.get("quality_url")
    if site == "hdfilm":
        return result.get("master_url")
    return ""


@app.get("/health")
def health() -> tuple[dict, int]:
    return {"status": "ok", "cache_size": len(_token_cache)}, 200


@app.post("/resolve")
def resolve_route() -> tuple[dict, int]:
    payload = request.get_json(force=True, silent=True) or {}
    url = payload.get("url")
    if not url:
        return {"error": "Missing 'url' field"}, 400

    site = payload.get("site")
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
    return jsonify(response), 200


def create_app() -> Flask:
    """Factory for WSGI servers."""
    return app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5055, debug=False)
