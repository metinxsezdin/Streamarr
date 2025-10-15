"""
Flask API exposing the on-demand stream resolver for integration with Jellyfin.
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set, Tuple
from urllib.parse import quote, quote_plus, unquote, urljoin, urlparse

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
