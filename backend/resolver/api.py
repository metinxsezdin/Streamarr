"""
Flask API exposing the on-demand stream resolver for integration with Jellyfin.
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Set, Tuple
from urllib.parse import quote, quote_plus, unquote, urljoin

import requests
from flask import Flask, Response, jsonify, redirect, request, stream_with_context

from .stream_resolver import resolve_stream, SUPPORTED_SITES
from .catalog import load_catalog, get_entry

app = Flask(__name__)

TOKEN_TTL_SECONDS = 5 * 60
PROXY_BASE_URL = os.environ.get("PROXY_BASE_URL")
ROOT_DIR = Path(__file__).resolve().parents[2]
CATALOG_PATH = Path(os.environ.get("CATALOG_PATH", ROOT_DIR / "data/catalog.json"))
RESOLVER_PORT = int(os.environ.get("RESOLVER_PORT", os.environ.get("PORT", "5055")))
_token_cache: Dict[str, Dict] = {}
_catalog_index: Dict[str, Dict] = load_catalog(CATALOG_PATH)
_content_token_cache: Dict[str, Dict[str, float | str]] = {}
_token_to_content: Dict[str, Set[str]] = {}


def _cleanup_expired() -> None:
    now = time.time()
    expired = [token for token, payload in _token_cache.items() if payload["expires_at"] <= now]
    for token in expired:
        _token_cache.pop(token, None)
        _remove_token_mapping(token)


def _cleanup_content_cache() -> None:
    now = time.time()
    for content_id, cached in list(_content_token_cache.items()):
        token = cached.get("token")
        payload = _token_cache.get(token)
        if (
            not token
            or payload is None
            or payload["expires_at"] <= now
            or cached.get("expires_at", 0) <= now
        ):
            _content_token_cache.pop(content_id, None)
            if token:
                _remove_token_mapping(token, content_id)


def _remove_token_mapping(token: str, specific_content: str | None = None) -> None:
    if specific_content:
        cached_set = _token_to_content.get(token)
        if cached_set:
            cached_set.discard(specific_content)
            if not cached_set:
                _token_to_content.pop(token, None)
        cached_entry = _content_token_cache.get(specific_content)
        if cached_entry and cached_entry.get("token") == token:
            _content_token_cache.pop(specific_content, None)
        return

    content_ids = _token_to_content.pop(token, set())
    for content_id in content_ids:
        cached_entry = _content_token_cache.get(content_id)
        if cached_entry and cached_entry.get("token") == token:
            _content_token_cache.pop(content_id, None)


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


def _cache_content_token(content_id: str, token: str, expires_at: float) -> None:
    _content_token_cache[content_id] = {"token": token, "expires_at": expires_at}
    _token_to_content.setdefault(token, set()).add(content_id)


def _touch_token(token: str) -> float:
    new_expiry = time.time() + TOKEN_TTL_SECONDS
    payload = _token_cache.get(token)
    if payload is not None:
        payload["expires_at"] = new_expiry
    for content_id in _token_to_content.get(token, set()):
        cached = _content_token_cache.get(content_id)
        if cached:
            cached["expires_at"] = new_expiry
    return new_expiry


def _get_cached_token_by_key(key: str):
    _cleanup_content_cache()
    cached = _content_token_cache.get(key)
    if not cached:
        return None
    token = cached.get("token")
    if not token:
        _content_token_cache.pop(key, None)
        return None
    payload = _token_cache.get(token)
    if payload is None:
        _remove_token_mapping(token, key)
        return None
    _touch_token(token)
    return token, payload


def _get_cached_token_for_entry(entry_id: str | None, url: str | None):
    keys = []
    if entry_id:
        keys.append(f"id:{entry_id}")
    if url:
        keys.append(f"url:{url}")

    for key in keys:
        cached = _get_cached_token_by_key(key)
        if cached:
            return cached
    return None


def _cache_token_for_entry(entry_id: str | None, url: str | None, token: str, expires_at: float) -> None:
    if entry_id:
        _cache_content_token(f"id:{entry_id}", token, expires_at)
    if url:
        _cache_content_token(f"url:{url}", token, expires_at)


def _get_hdfilm_headers(result: Dict) -> Dict[str, str]:
    referer = result.get("embed_url") or result.get("page_url") or "https://www.hdfilmcehennemi.la/"
    user_agent = result.get("user_agent") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
    return {
        "Referer": referer,
        "User-Agent": user_agent,
    }


def _serve_hdfilm_master(token: str, data: Dict) -> Response:
    result = data.get("result") or {}
    master_url = result.get("master_url")
    variants = result.get("variants") or []
    if not master_url:
        return jsonify({"error": "Missing master URL"}), 500

    headers = _get_hdfilm_headers(result)

    if not variants:
        try:
            resp = requests.get(master_url, headers=headers, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as exc:
            return jsonify({"error": f"Failed to fetch master playlist: {exc}"}), 502
        return Response(resp.text, content_type="application/vnd.apple.mpegurl")

    lines = ["#EXTM3U"]
    base_url = request.url_root.rstrip("/")
    for index, variant in enumerate(variants):
        attributes = []
        bandwidth = variant.get("bandwidth")
        resolution = variant.get("resolution")
        codecs = variant.get("codecs")
        if bandwidth:
            attributes.append(f"BANDWIDTH={int(bandwidth)}")
        if resolution and resolution != "Unknown":
            attributes.append(f"RESOLUTION={resolution}")
        if codecs:
            attributes.append(f"CODECS=\"{codecs}\"")
        attr_line = ",".join(attributes)
        if attr_line:
            lines.append(f"#EXT-X-STREAM-INF:{attr_line}")
        else:
            lines.append("#EXT-X-STREAM-INF:")
        proxied = f"{base_url}/proxy/{token}?variant={index}"
        lines.append(proxied)
    lines.append("")  # ensure trailing newline
    return Response("\n".join(lines), content_type="application/vnd.apple.mpegurl")


@app.get("/health")
def health() -> tuple[dict, int]:
    return {"status": "ok", "cache_size": len(_token_cache)}, 200


@app.get("/catalog")
def catalog_route():
    return jsonify(list(_catalog_index.values())), 200


@app.post("/resolve")
def resolve_route() -> tuple[dict, int]:
    payload = request.get_json(force=True, silent=True) or {}
    content_id = payload.get("id")
    url = payload.get("url")
    site = payload.get("site")
    entry = None

    if content_id:
        entry = get_entry(_catalog_index, content_id)
        if not entry:
            return {"error": f"Unknown id '{content_id}'"}, 404
        url = entry.get("url")
        site = entry.get("site")
        if not headed and not verbose:
            cached = _get_cached_token_for_entry(entry.get("id"), entry.get("url"))
            if cached:
                token, cached_payload = cached
                stream_url = _resolve_stream_url(cached_payload["data"]["site"], cached_payload["data"]["result"])
                expires_at_ts = cached_payload["expires_at"]
                response = {
                    "token": token,
                    "expires_at": datetime.fromtimestamp(expires_at_ts, tz=timezone.utc).isoformat(),
                    "proxy_url": f"/stream/{token}",
                    "redirect_url": f"/stream/{token}",
                    "stream_url": stream_url,
                    "resolver": cached_payload["data"],
                }
                return jsonify(response), 200
    elif url and not headed and not verbose:
        cached = _get_cached_token_for_entry(None, url)
        if cached:
            token, cached_payload = cached
            stream_url = _resolve_stream_url(cached_payload["data"]["site"], cached_payload["data"]["result"])
            expires_at_ts = cached_payload["expires_at"]
            response = {
                "token": token,
                "expires_at": datetime.fromtimestamp(expires_at_ts, tz=timezone.utc).isoformat(),
                "proxy_url": f"/stream/{token}",
                "redirect_url": f"/stream/{token}",
                "stream_url": stream_url,
                "resolver": cached_payload["data"],
            }
            return jsonify(response), 200

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
    cache_entry_id = entry["id"] if entry else None
    cache_url = entry["url"] if entry else url
    _cache_token_for_entry(cache_entry_id, cache_url, token, expires_at_ts)
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
def stream_route(token: str):
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

    if data["site"] == "hdfilm":
        return _serve_hdfilm_master(token, data)

    return redirect(stream_url, code=302)


@app.get("/play/<path:content_id>")
def play_route(content_id: str):
    entry = get_entry(_catalog_index, content_id)
    if not entry:
        return {"error": "Unknown id"}, 404

    site = entry.get("site")
    if site not in SUPPORTED_SITES:
        return {"error": f"Unsupported site '{site}'"}, 400

    cached = _get_cached_token_for_entry(entry.get("id"), entry.get("url"))
    if cached:
        token, cached_payload = cached
        stream_url = _resolve_stream_url(cached_payload["data"]["site"], cached_payload["data"]["result"])
        if request.args.get("format") == "json":
            expires_iso = datetime.fromtimestamp(cached_payload["expires_at"], tz=timezone.utc).isoformat()
            return jsonify(
                {
                    "token": token,
                    "expires_at": expires_iso,
                    "stream_url": stream_url,
                    "resolver": cached_payload["data"],
                }
            ), 200

        if cached_payload["data"]["site"] == "hdfilm":
            return _serve_hdfilm_master(token, cached_payload["data"])

        return redirect(f"/stream/{token}", code=302)

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
    _cache_token_for_entry(entry.get("id"), entry.get("url"), token, expires_at_ts)
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


def _fetch_with_headers(url: str, headers: Dict[str, str], stream: bool = False):
    return requests.get(url, headers=headers, stream=stream, timeout=20)


@app.get("/proxy/<token>")
@app.get("/proxy/<token>/<path:subpath>")
def proxy_route(token: str, subpath: str | None = None):
    _cleanup_expired()
    payload = _token_cache.get(token)
    if not payload:
        return {"error": "Token not found or expired"}, 404

    data = payload["data"]
    result = data.get("result") or {}
    if data.get("site") != "hdfilm":
        return {"error": "Proxy only supported for hdfilm"}, 400

    headers = _get_hdfilm_headers(result)
    variants = result.get("variants") or []
    variant_param = request.args.get("variant")
    segment_param = request.args.get("segment")

    if subpath and subpath.startswith("segment") and not segment_param:
        segment_param = request.args.get("segment")

    if variant_param is not None:
        try:
            index = int(variant_param)
        except ValueError:
            return {"error": "Invalid variant index"}, 400
        if index < 0 or index >= len(variants):
            return {"error": "Variant index out of range"}, 404
        variant = variants[index]
        variant_url = variant.get("url")
        if not variant_url:
            return {"error": "Variant URL missing"}, 500
        try:
            resp = _fetch_with_headers(variant_url, headers, stream=False)
            resp.raise_for_status()
        except requests.RequestException as exc:
            return {"error": f"Failed to fetch variant playlist: {exc}"}, 502

        base_url = request.url_root.rstrip("/")
        allowed_ext = (".ts", ".m4s", ".m4a", ".m4v", ".mp4", ".aac", ".vtt", ".mp3", ".webvtt")
        filtered_lines: list[str] = []
        pending_extinf: str | None = None
        has_segment = False

        for raw_line in resp.text.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue

            if stripped.startswith("#EXTINF"):
                pending_extinf = raw_line
                continue

            if stripped.startswith("#"):
                filtered_lines.append(raw_line)
                continue

            absolute = urljoin(variant_url, stripped)
            normalized = absolute.lower().split("?", 1)[0]
            if not normalized.endswith(allowed_ext):
                pending_extinf = None
                continue

            proxied = f"{base_url}/proxy/{token}/segment.ts?segment={quote(absolute, safe='')}"
            if pending_extinf is not None:
                filtered_lines.append(pending_extinf)
                pending_extinf = None
            filtered_lines.append(proxied)

            has_segment = True

        if not has_segment:
            return jsonify({"error": "No playable segments found in variant playlist"}), 502

        filtered_lines.append("")
        return Response("\n".join(filtered_lines), content_type="application/vnd.apple.mpegurl")

    if segment_param is not None:
        segment_url = unquote(segment_param)
        if not segment_url:
            return {"error": "Segment URL missing"}, 400
        try:
            resp = _fetch_with_headers(segment_url, headers, stream=True)
            resp.raise_for_status()
        except requests.RequestException as exc:
            return {"error": f"Failed to fetch segment: {exc}"}, 502

        excluded_headers = {"content-encoding", "transfer-encoding", "connection"}
        response_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers}
        return Response(
            stream_with_context(resp.iter_content(chunk_size=8192)),
            status=resp.status_code,
            headers=response_headers,
        )

    return jsonify({"error": "Invalid proxy request"}), 400


def create_app() -> Flask:
    """Factory for WSGI servers."""
    return app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=RESOLVER_PORT, debug=False)
