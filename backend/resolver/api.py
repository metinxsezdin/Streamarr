"""
Flask API exposing the on-demand stream resolver for integration with Jellyfin.
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set, Tuple, List
from urllib.parse import quote, quote_plus, unquote, urljoin, urlparse
import re
from copy import deepcopy

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

RELAY_SITES = {"hdfilm", "dizipub", "dizipal", "dizilla"}
_DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
DEFAULT_REFERERS = {
    "hdfilm": "https://www.hdfilmcehennemi.la/",
    "dizipub": "https://dizipub.club/",
    "dizipal": "https://dizipal1503.com/",
    "dizilla": "https://dizilla40.com/",
}
DEFAULT_SOURCE_PRIORITY = 100


def _parse_resolution_token(token: Optional[str]) -> Tuple[int, int]:
    if not token or not isinstance(token, str):
        return 0, 0
    match = re.search(r"(\d{3,4})\s*[xX]\s*(\d{3,4})", token)
    if match:
        try:
            width = int(match.group(1))
            height = int(match.group(2))
            return width, height
        except ValueError:
            return 0, 0
    match = re.search(r"(\d{3,4})p", token, re.IGNORECASE)
    if match:
        try:
            height = int(match.group(1))
            # assume 16:9 aspect ratio when width missing
            width = height * 16 // 9
            return width, height
        except ValueError:
            return 0, 0
    return 0, 0


def _variant_sort_key(variant: Dict[str, object], index: int) -> Tuple[int, int, int, int]:
    width, height = _parse_resolution_token(variant.get("resolution"))
    awidth, aheight = _parse_resolution_token(variant.get("quality"))
    width = max(width, awidth)
    height = max(height, aheight)

    resolution_score = width * height if width and height else height * height

    bandwidth = 0
    try:
        candidate = variant.get("bandwidth")
        if candidate is not None:
            bandwidth = int(candidate)
    except (ValueError, TypeError):
        bandwidth = 0

    # prefer variants with explicit playlist text only if nothing else
    has_playlist = 1 if variant.get("playlist") else 0

    return (resolution_score, height, bandwidth, has_playlist, -index)


def _select_best_variant(variants: Optional[List[Dict[str, object]]]) -> Optional[Tuple[int, Dict[str, object]]]:
    if not variants:
        return None
    best_index = -1
    best_variant: Optional[Dict[str, object]] = None
    best_score = (-1, -1, -1, -1, 0)
    for idx, variant in enumerate(variants):
        if not isinstance(variant, dict):
            continue
        score = _variant_sort_key(variant, idx)
        if score > best_score:
            best_score = score
            best_variant = variant
            best_index = idx
    if best_variant is None:
        return None
    return best_index, best_variant


def _decorate_best_variant(result: Optional[Dict[str, object]]) -> None:
    if not isinstance(result, dict):
        return
    variants = result.get("variants")
    best_info = _select_best_variant(variants if isinstance(variants, list) else None)
    if not best_info:
        return
    best_index, best_variant = best_info
    result["best_variant_index"] = best_index
    result["best_variant"] = deepcopy(best_variant)
    best_url = best_variant.get("url")
    if isinstance(best_url, str) and best_url:
        result["preferred_stream_url"] = best_url


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


def _cookies_from_header(cookie_header: Optional[str], target_url: str) -> list[dict]:
    if not cookie_header:
        return []
    parsed = urlparse(target_url)
    domain = parsed.hostname
    if not domain:
        return []
    secure = parsed.scheme == "https"
    cookies: list[dict] = []
    for chunk in cookie_header.split(";"):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        name, value = chunk.split("=", 1)
        cookies.append(
            {
                "name": name.strip(),
                "value": value,
                "domain": domain,
                "path": "/",
                "secure": secure,
                "httpOnly": False,
            }
        )
    return cookies


def _entry_sources(entry: Dict) -> list[Dict[str, object]]:
    sources = entry.get("sources")
    normalized: list[Dict[str, object]] = []

    if isinstance(sources, list):
        for raw in sources:
            if not isinstance(raw, dict):
                continue
            site = raw.get("site")
            url = raw.get("url")
            if not isinstance(site, str) or not isinstance(url, str):
                continue
            priority_value = raw.get("priority", DEFAULT_SOURCE_PRIORITY)
            try:
                priority = int(priority_value)
            except (TypeError, ValueError):
                priority = DEFAULT_SOURCE_PRIORITY
            normalized.append(
                {
                    "site": site,
                    "url": url,
                    "priority": priority,
                    "site_entry_id": raw.get("site_entry_id"),
                }
            )

    if not normalized:
        site = entry.get("site")
        url = entry.get("url")
        if isinstance(site, str) and isinstance(url, str):
            normalized.append(
                {
                    "site": site,
                    "url": url,
                    "priority": DEFAULT_SOURCE_PRIORITY,
                    "site_entry_id": entry.get("id"),
                }
            )

    normalized.sort(key=lambda item: (item.get("priority", DEFAULT_SOURCE_PRIORITY), item.get("site", "")))
    return normalized


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


def _fetch_variant_playlist_via_browser(
    site: str,
    variant_url: str,
    result: Dict,
) -> Tuple[Optional[str], Optional[str]]:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        return None, "Playwright runtime is not available on this server"

    try:
        with sync_playwright() as playwright:
            browser = playwright.firefox.launch(headless=True)
            context = browser.new_context(
                user_agent=result.get("user_agent") or _DEFAULT_USER_AGENT,
                locale="tr-TR",
                timezone_id="Europe/Istanbul",
            )
            try:
                cookies = _cookies_from_header(result.get("cookies"), variant_url)
                if cookies:
                    try:
                        context.add_cookies(cookies)
                    except Exception:
                        pass

                page = context.new_page()
                navigation_target = result.get("embed_url") or result.get("page_url") or DEFAULT_REFERERS.get(site, "")
                if navigation_target:
                    try:
                        page.goto(navigation_target, wait_until="domcontentloaded", timeout=20000)
                        page.wait_for_timeout(2000)
                    except Exception:
                        pass

                fetch_result = page.evaluate(
                    """
                    async (targetUrl) => {
                        try {
                            const response = await fetch(targetUrl, { credentials: 'include' });
                            const text = await response.text();
                            return { ok: response.ok, status: response.status, text };
                        } catch (error) {
                            return { ok: false, status: 0, error: String(error) };
                        }
                    }
                    """,
                    variant_url,
                )

                text = (fetch_result or {}).get("text") if isinstance(fetch_result, dict) else None
                status = (fetch_result or {}).get("status") if isinstance(fetch_result, dict) else None
                ok = bool((fetch_result or {}).get("ok")) if isinstance(fetch_result, dict) else False
                if ok and text:
                    return text, None
                if text and "#EXTM3U" in text:
                    return text, None

                headers = {
                    "Accept": "application/vnd.apple.mpegurl",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                }
                if navigation_target:
                    headers["Referer"] = navigation_target

                api_response = context.request.get(variant_url, headers=headers, timeout=20000)
                status = api_response.status
                text = ""
                try:
                    text = api_response.text()
                except Exception:
                    text = ""

                if api_response.ok and text:
                    return text, None

                if "#EXTM3U" in (text or ""):
                    return text, None

                return None, f"Browser relay received status {status or 'unknown'}"
            finally:
                context.close()
                browser.close()
    except Exception as exc:
        return None, f"Browser relay failed: {exc}"


def _store_token(data: Dict) -> Tuple[str, float]:
    _cleanup_expired()
    token = uuid.uuid4().hex
    expires_at = time.time() + TOKEN_TTL_SECONDS
    _token_cache[token] = {"data": data, "expires_at": expires_at}
    return token, expires_at


def _resolve_stream_url(site: str, result: Dict) -> str:
    if site == "dizibox":
        base = result.get("quality_url") if PROXY_BASE_URL else result.get("proxy_url") or result.get("quality_url")
    elif site in RELAY_SITES:
        base = (
            result.get("master_url")
            or result.get("playlist_url")
            or result.get("quality_url")
            or result.get("stream_url")
        )
    else:
        base = result.get("stream_url") or ""
    preferred = result.get("preferred_stream_url")
    if isinstance(preferred, str) and preferred:
        base = preferred
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


def _get_cached_token_for_entry(entry_id: str | None, site: str | None, url: str | None):
    keys: list[str] = []
    if entry_id and site:
        keys.append(f"id:{entry_id}:site:{site}")
    if url:
        keys.append(f"url:{url}")
    if entry_id:
        keys.append(f"id:{entry_id}")

    for key in keys:
        cached = _get_cached_token_by_key(key)
        if not cached:
            continue
        token, payload = cached
        data = payload.get("data") or {}
        data_site = data.get("site")
        data_url = data.get("url")
        if site and data_site and data_site != site:
            continue
        if url and data_url and data_url != url:
            continue
        return token, payload
    return None


def _cache_token_for_entry(entry_id: str | None, site: str | None, url: str | None, token: str, expires_at: float) -> None:
    if entry_id and site:
        _cache_content_token(f"id:{entry_id}:site:{site}", token, expires_at)
    if entry_id:
        _cache_content_token(f"id:{entry_id}", token, expires_at)
    if url:
        _cache_content_token(f"url:{url}", token, expires_at)


def _get_site_headers(site: str, result: Dict) -> Dict[str, str]:
    headers = {
        "User-Agent": result.get("user_agent") or _DEFAULT_USER_AGENT,
    }
    referer = result.get("embed_url") or result.get("page_url") or DEFAULT_REFERERS.get(site, "")
    if referer:
        headers["Referer"] = referer
    cookies = result.get("cookies")
    if cookies:
        headers["Cookie"] = cookies
    return headers


def _build_token_payload(token: str, expires_at: float, data: Dict) -> Dict[str, object]:
    _decorate_best_variant((data or {}).get("result"))
    stream_url = _resolve_stream_url(data["site"], data["result"])
    return {
        "token": token,
        "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
        "proxy_url": f"/stream/{token}",
        "redirect_url": f"/stream/{token}",
        "stream_url": stream_url,
        "resolver": data,
    }


def _serve_hls_master(token: str, data: Dict) -> Response:
    site = data.get("site")
    result = data.get("result") or {}
    _decorate_best_variant(result)
    master_url = (
        result.get("master_url")
        or result.get("playlist_url")
        or result.get("quality_url")
        or result.get("stream_url")
    )
    original_variants = result.get("variants") or []
    best_variant = result.get("best_variant") if isinstance(result.get("best_variant"), dict) else None
    variants = [best_variant] if best_variant else list(original_variants)
    raw_playlist = result.get("raw_playlist")

    if not master_url and not raw_playlist:
        return jsonify({"error": "Missing master URL"}), 500

    headers = _get_site_headers(site or "", result)

    if not variants and raw_playlist:
        return Response(raw_playlist, content_type="application/vnd.apple.mpegurl")

    if not variants and master_url:
        try:
            resp = _fetch_with_headers(master_url, headers, stream=False)
            resp.raise_for_status()
        except requests.RequestException as exc:
            return jsonify({"error": f"Failed to fetch master playlist: {exc}"}), 502
        return Response(resp.text, content_type="application/vnd.apple.mpegurl")

    base_url = request.url_root.rstrip("/")
    lines = ["#EXTM3U"]
    if best_variant and isinstance(result.get("best_variant_index"), int):
        variant_entries = [(int(result.get("best_variant_index")), best_variant)]
    else:
        variant_entries = [(idx, variant) for idx, variant in enumerate(variants)]

    for original_index, variant in variant_entries:
        attributes: list[str] = []
        bandwidth = variant.get("bandwidth")
        if bandwidth:
            try:
                attributes.append(f"BANDWIDTH={int(bandwidth)}")
            except (ValueError, TypeError):
                pass
        resolution = variant.get("resolution")
        if resolution and resolution != "Unknown":
            attributes.append(f"RESOLUTION={resolution}")
        codecs = variant.get("codecs")
        if codecs:
            attributes.append(f'CODECS="{codecs}"')
        quality = variant.get("quality")
        if quality and (not resolution or quality not in resolution):
            attributes.append(f'NAME="{quality}"')

        attr_line = ",".join(attributes)
        if attr_line:
            lines.append(f"#EXT-X-STREAM-INF:{attr_line}")
        else:
            lines.append("#EXT-X-STREAM-INF:")
        proxied = f"{base_url}/proxy/{token}?variant={original_index}"
        lines.append(proxied)
    lines.append("")
    return Response("\n".join(lines), content_type="application/vnd.apple.mpegurl")


@app.get("/health")
def health() -> tuple[dict, int]:
    return {"status": "ok", "cache_size": len(_token_cache)}, 200


@app.get("/catalog")
def catalog_route():
    return jsonify(list(_catalog_index.values())), 200


@app.post("/resolve")
def resolve_route() -> tuple[Response, int]:
    payload = request.get_json(force=True, silent=True) or {}
    content_id = payload.get("id")
    url = payload.get("url")
    site = payload.get("site")
    headed = bool(payload.get("headed", False))
    verbose = bool(payload.get("verbose", False))
    entry = None

    if content_id:
        entry = get_entry(_catalog_index, content_id)
        if not entry:
            return jsonify({"error": f"Unknown id '{content_id}'"}), 404
        url = entry.get("url")
        site = entry.get("site")

    if not url:
        return jsonify({"error": "Missing 'url' field"}), 400

    if site and site not in SUPPORTED_SITES:
        return jsonify({"error": f"Unsupported site '{site}'"}), 400

    if not headed and not verbose:
        cached = _get_cached_token_for_entry(entry.get("id") if entry else None, site, url)
        if cached:
            token, cached_payload = cached
            cached_data = cached_payload.get("data") or {}
            _decorate_best_variant(cached_data.get("result"))
            response = _build_token_payload(token, cached_payload["expires_at"], cached_payload["data"])
            return jsonify(response), 200

    try:
        data = resolve_stream(
            url,
            site=site,
            headless=not headed,
            quiet=not verbose,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    _decorate_best_variant((data or {}).get("result"))
    token, expires_at_ts = _store_token(data)
    cache_entry_id = entry.get("id") if entry else None
    _cache_token_for_entry(cache_entry_id, site, url, token, expires_at_ts)
    response = _build_token_payload(token, expires_at_ts, data)
    return jsonify(response), 200


@app.get("/stream/<token>")
def stream_route(token: str):
    _cleanup_expired()
    payload = _token_cache.get(token)
    if not payload:
        return {"error": "Token not found or expired"}, 404

    data = payload["data"]
    _decorate_best_variant(data.get("result"))
    if request.args.get("format") == "json":
        response = _build_token_payload(token, payload["expires_at"], data)
        response.update(
            {
                "site": data["site"],
                "original_url": data["url"],
                "details": data["result"],
            }
        )
        return jsonify(response), 200

    if data.get("site") in RELAY_SITES:
        return _serve_hls_master(token, data)

    stream_url = _resolve_stream_url(data["site"], data["result"])
    if not stream_url:
        return {"error": "No stream URL available for this token"}, 500

    return redirect(stream_url, code=302)


@app.get("/play/<path:content_id>")
def play_route(content_id: str):
    entry = get_entry(_catalog_index, content_id)
    if not entry:
        return {"error": "Unknown id"}, 404
    sources = _entry_sources(entry)
    if not sources:
        return {"error": "No valid sources defined for this entry"}, 400

    errors: list[Dict[str, str]] = []
    entry_id = entry.get("id")

    for source in sources:
        site = source.get("site")
        url = source.get("url")
        if not isinstance(site, str) or not isinstance(url, str):
            errors.append({"error": "Invalid source payload", "site": str(site), "url": str(url)})
            continue
        if site not in SUPPORTED_SITES:
            errors.append({"error": f"Unsupported site '{site}'", "site": site, "url": url})
            continue

        cached = _get_cached_token_for_entry(entry_id, site, url)
        if cached:
            token, cached_payload = cached
            cached_data = cached_payload.get("data") or {}
            _decorate_best_variant(cached_data.get("result"))
            if request.args.get("format") == "json":
                response = _build_token_payload(token, cached_payload["expires_at"], cached_payload["data"])
                return jsonify(response), 200

            if cached_payload["data"].get("site") in RELAY_SITES:
                return _serve_hls_master(token, cached_payload["data"])

            return redirect(f"/stream/{token}", code=302)

        try:
            data = resolve_stream(
                url,
                site=site,
                headless=True,
                quiet=False,
            )
        except Exception as exc:
            errors.append({"error": str(exc), "site": site, "url": url})
            continue

        _decorate_best_variant(data.get("result"))
        token, expires_at_ts = _store_token(data)
        _cache_token_for_entry(entry_id, site, url, token, expires_at_ts)
        if request.args.get("format") == "json":
            response = _build_token_payload(token, expires_at_ts, data)
            return jsonify(response), 200

        if data.get("site") in RELAY_SITES:
            return _serve_hls_master(token, data)

        return redirect(f"/stream/{token}", code=302)

    return {"error": "All sources failed to resolve", "details": errors}, 502


def _fetch_with_headers(url: str, headers: Dict[str, str], stream: bool = False):
    return requests.get(url, headers=headers, stream=stream, timeout=20)


def _fetch_variant_playlist(site: str, variant: Dict, result: Dict, headers: Dict[str, str]):
    playlist_text = variant.get("playlist")
    variant_url = variant.get("url")
    if playlist_text:
        return playlist_text, None
    if not variant_url:
        return None, "Variant URL missing"

    relay_text, relay_error = _fetch_variant_playlist_via_browser(site, variant_url, result)
    if relay_text:
        return relay_text, None

    try:
        resp = _fetch_with_headers(variant_url, headers, stream=False)
        resp.raise_for_status()
    except requests.RequestException as exc:
        message = f"Failed to fetch variant playlist: {exc}"
        if relay_error:
            message = f"{message}; browser relay: {relay_error}"
        return None, message
    return resp.text, None


@app.get("/proxy/<token>")
@app.get("/proxy/<token>/<path:subpath>")
def proxy_route(token: str, subpath: str | None = None):
    _cleanup_expired()
    payload = _token_cache.get(token)
    if not payload:
        return {"error": "Token not found or expired"}, 404

    data = payload["data"]
    site = data.get("site")
    if site not in RELAY_SITES:
        return {"error": "Proxy only supported for relay-enabled sites"}, 400

    result = data.get("result") or {}
    _decorate_best_variant(result)
    headers = _get_site_headers(site, result)
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
        playlist_text, playlist_error = _fetch_variant_playlist(site, variant, result, headers)
        if not playlist_text:
            return {"error": playlist_error or "Variant playlist unavailable"}, 502
        variant_url = variant.get("url") or result.get("master_url") or ""

        base_url = request.url_root.rstrip("/")
        allowed_ext = (".ts", ".m4s", ".m4a", ".m4v", ".mp4", ".aac", ".vtt", ".mp3", ".webvtt")
        filtered_lines: list[str] = []
        pending_extinf: str | None = None
        has_segment = False

        for raw_line in playlist_text.splitlines():
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
