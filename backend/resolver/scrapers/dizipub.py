"""
Dizipub scraper implementation.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import Response, sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


@dataclass
class StreamVariant:
    quality: str
    resolution: str
    bandwidth: int
    url: str


class DizipubScraper:
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
        "Gecko/20100101 Firefox/121.0"
    )

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self.master_url: Optional[str] = None
        self.embed_url: Optional[str] = None
        self.playlist_content: Optional[str] = None
        self.user_agent: str = self.DEFAULT_USER_AGENT
        self._variants: List[StreamVariant] = []
        self.cookies_header: str = ""
        self.variant_playlists: Dict[str, str] = {}

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_playlist_response(response: Response) -> bool:
        url = response.url.lower()
        if ".m3u8" in url:
            return True
        content_type = (response.headers or {}).get("content-type", "")
        return "application/vnd.apple.mpegurl" in content_type.lower()

    def _response_handler(self) -> None:
        def _capture(response: Response) -> None:
            if not self._is_playlist_response(response):
                return

            try:
                text = response.text()
            except Exception:
                text = ""

            if not self.master_url:
                self.master_url = response.url
                print(f"  [capture] Master playlist: {self.master_url}")

            if not text:
                return

            url = response.url
            if not self.playlist_content and url == self.master_url:
                self.playlist_content = text
                print(f"  [capture] Playlist bytes: {len(text)}")
            elif url != self.master_url and url not in self.variant_playlists:
                self.variant_playlists[url] = text
                print(f"  [capture] Variant playlist: {url} ({len(text)} bytes)")

        return _capture

    def _ensure_iframe_loaded(self, page) -> None:
        """Force lazy iframes to load."""
        script = """
            (() => {
                const frames = Array.from(document.querySelectorAll('iframe'));
                for (const iframe of frames) {
                    if (iframe.dataset && iframe.dataset.src && !iframe.src) {
                        iframe.src = iframe.dataset.src;
                    }
                }
            })();
        """
        try:
            page.evaluate(script)
        except Exception:
            pass

    def _detect_embed_url(self, page) -> None:
        try:
            iframe = page.query_selector("iframe[src*='//']")
            if not iframe:
                return
            src = iframe.get_attribute("src")
            if src:
                if src.startswith("//"):
                    src = f"https:{src}"
                self.embed_url = src
                print(f"  [capture] Embed iframe: {self.embed_url}")
        except Exception:
            pass
    
    def _get_player_context(self, page):
        if self.embed_url:
            base = self.embed_url.split("?", 1)[0]
            for frame in page.frames:
                try:
                    if frame.url and base in frame.url:
                        return frame
                except Exception:
                    continue
        return page

    def _wait_for_variant_capture(self, page, timeout_ms: int = 8000) -> None:
        """Block briefly waiting for at least one variant playlist response."""
        if not self.master_url:
            return
        deadline = time.time() + (timeout_ms / 1000)
        while time.time() < deadline:
            try:
                response = page.wait_for_event(
                    "response",
                    lambda resp: self._is_playlist_response(resp) and resp.url != self.master_url,
                    timeout=1000,
                )
                if response:
                    try:
                        # Ensure body is consumed so _response_handler captures it.
                        _ = response.text()
                    except Exception:
                        pass
                    if response.url in self.variant_playlists:
                        return
            except PlaywrightTimeout:
                continue
            except Exception:
                break

    def _auto_start_player(self, page) -> None:
        """Heuristic clicks to ensure the player is started."""
        click_selectors = [
            "button[data-player]",
            "button[aria-label='Play']",
            "button.play",
            ".btn-play",
            ".vjs-big-play-button",
            ".plyr__control--overlaid",
            ".jw-icon-playback",
        ]

        dismiss_selectors = [
            ".close",
            ".adsbox-close",
            "button[aria-label='Close']",
            ".vjs-close-button",
        ]

        # Try to close overlays/popups first.
        for selector in dismiss_selectors:
            try:
                element = page.query_selector(selector)
                if element:
                    element.click(timeout=500, force=True)
                    page.wait_for_timeout(300)
            except Exception:
                continue

        # Click possible server buttons.
        for selector in click_selectors:
            try:
                elements = page.query_selector_all(selector)
            except Exception:
                continue

            for element in elements:
                try:
                    element.click(timeout=500, force=True)
                    print(f"  [auto] Clicked '{selector}'")
                    page.wait_for_timeout(500)
                except Exception:
                    continue

        # Scroll to ensure lazy iframe loads.
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
        except Exception:
            pass
        page.wait_for_timeout(1000)

    @staticmethod
    def _parse_master_playlist(master_url: str, content: str) -> List[StreamVariant]:
        if not content:
            return []

        lines = content.strip().splitlines()
        variants: List[StreamVariant] = []

        for idx, line in enumerate(lines):
            line = line.strip()
            if not line.startswith("#EXT-X-STREAM-INF"):
                continue

            bandwidth = 0
            resolution = "Unknown"
            quality = "Unknown"

            parts = line.split(",")
            for part in parts:
                if part.startswith("BANDWIDTH="):
                    try:
                        bandwidth = int(part.split("=", 1)[1])
                    except ValueError:
                        bandwidth = 0
                elif part.startswith("RESOLUTION="):
                    resolution = part.split("=", 1)[1]
                elif part.startswith("NAME="):
                    quality = part.split("=", 1)[1].strip('"')

            if idx + 1 >= len(lines):
                continue

            next_line = lines[idx + 1].strip()
            if not next_line or next_line.startswith("#"):
                continue

            stream_url = next_line
            if not stream_url.lower().startswith("http"):
                stream_url = urljoin(master_url, stream_url)

            variants.append(
                StreamVariant(
                    quality=quality,
                    resolution=resolution,
                    bandwidth=bandwidth,
                    url=stream_url,
                )
            )

        return variants

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def get_stream_info(self, episode_url: str) -> Optional[Dict[str, object]]:
        print("=" * 80)
        print(f"PARSING: {episode_url}")
        print("=" * 80)

        self.master_url = None
        self.embed_url = None
        self.playlist_content = None
        self._variants = []
        self.variant_playlists = {}

        with sync_playwright() as playwright:
            browser = playwright.firefox.launch(headless=self.headless)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=self.user_agent,
                locale="tr-TR",
                timezone_id="Europe/Istanbul",
            )

            page = context.new_page()
            page.on("response", self._response_handler())

            try:
                page.goto(episode_url, wait_until="domcontentloaded", timeout=45000)
            except Exception as exc:
                print(f"? Failed to load page: {exc}")
                context.close()
                browser.close()
                return None

            page.wait_for_timeout(2000)
            self._ensure_iframe_loaded(page)
            self._detect_embed_url(page)
            control = self._get_player_context(page)
            self._auto_start_player(control)
            try:
                started = control.evaluate(
                    """
                        async () => {
                            const video = document.querySelector('video');
                            if (!video) {
                                return false;
                            }
                            try {
                                video.muted = true;
                                await video.play();
                                return true;
                            } catch (err) {
                                return false;
                            }
                        }
                    """
                )
                if started:
                    print("  [auto] Triggered video.play()")
            except Exception:
                pass

            # Allow network activity to settle.
            for i in range(30):
                if self.master_url and self.playlist_content:
                    break
                if (i + 1) % 5 == 0:
                    print(f"  [wait] {i + 1}s without playlist capture...")
                page.wait_for_timeout(1000)

            self._wait_for_variant_capture(control, timeout_ms=5000)

            # Try to fetch playlist manually if not captured.
            if self.master_url and not self.playlist_content:
                try:
                    script = """
                        async (masterUrl) => {
                            const response = await fetch(masterUrl, { credentials: 'include' });
                            return await response.text();
                        }
                    """
                    self.playlist_content = control.evaluate(script, self.master_url)
                    print(
                        f"  [fetch] Pulled playlist ({len(self.playlist_content)} bytes)"
                    )
                except Exception as exc:
                    print(f"  [fetch] Failed to download playlist: {exc}")

            if self.master_url and self.playlist_content and not self.variant_playlists:
                page.wait_for_timeout(3000)
                self._wait_for_variant_capture(control, timeout_ms=5000)

            try:
                cookies = context.cookies()
                if cookies:
                    self.cookies_header = "; ".join(f"{item['name']}={item['value']}" for item in cookies)
            except Exception:
                self.cookies_header = ""

            variants: List[StreamVariant] = []
            if self.master_url and self.playlist_content:
                variants = self._parse_master_playlist(self.master_url, self.playlist_content)
                fetch_variant_script = """
                    async (variantUrl) => {
                        const loadViaIframe = () =>
                            new Promise((resolve) => {
                                const iframe = document.createElement('iframe');
                                iframe.style.display = 'none';
                                iframe.referrerPolicy = 'no-referrer-when-downgrade';
                                iframe.onload = () => {
                                    try {
                                        const doc = iframe.contentDocument;
                                        const payload = doc ? doc.body.innerText : '';
                                        resolve(payload || '');
                                    } catch (error) {
                                        resolve('');
                                    } finally {
                                        iframe.remove();
                                    }
                                };
                                iframe.onerror = () => {
                                    iframe.remove();
                                    resolve('');
                                };
                                document.body.appendChild(iframe);
                                iframe.src = variantUrl;
                            });

                        let text = await loadViaIframe();
                        if (text) {
                            return { ok: true, status: 200, text };
                        }

                        try {
                            const response = await fetch(variantUrl, {
                                credentials: 'include',
                                cache: 'no-cache',
                            });
                            text = await response.text();
                            return { ok: response.ok, status: response.status, text };
                        } catch (error) {
                            return { ok: false, status: 0, error: String(error) };
                        }
                    }
                """
                for variant in variants:
                    if variant.url in self.variant_playlists:
                        continue
                    for _ in range(5):
                        if variant.url in self.variant_playlists:
                            break
                        page.wait_for_timeout(1000)
                    if variant.url in self.variant_playlists:
                        continue
                    try:
                        evaluation = control.evaluate(fetch_variant_script, variant.url)
                        if isinstance(evaluation, dict) and evaluation.get("ok") and evaluation.get("text"):
                            body = evaluation.get("text") or ""
                            self.variant_playlists[variant.url] = body
                            print(
                                f"  [fetch] Variant {variant.quality or variant.resolution} "
                                f"playlist ({len(body)} bytes)"
                            )
                        else:
                            status = None
                            if isinstance(evaluation, dict):
                                status = evaluation.get("status")
                            print(
                                f"  [fetch] Variant request failed ({status or 'N/A'}): {variant.url}"
                            )
                    except Exception as exc:
                        print(f"  [fetch] Variant request error: {exc}")

            browser.close()

        if not self.master_url or not self.playlist_content:
            print("? No playlist captured.")
            return None

        if not self._variants:
            self._variants = variants or self._parse_master_playlist(self.master_url, self.playlist_content)

        return {
            "embed_url": self.embed_url,
            "master_url": self.master_url,
            "variants": [
                {
                    "quality": variant.quality,
                    "resolution": variant.resolution,
                    "bandwidth": variant.bandwidth,
                    "url": variant.url,
                    "playlist": self.variant_playlists.get(variant.url),
                }
                for variant in self._variants
            ],
            "raw_playlist": self.playlist_content,
            "user_agent": self.user_agent,
            "cookies": self.cookies_header,
            "page_url": episode_url,
        }


def main() -> None:
    default_url = "https://dizipub.club/murdaugh-death-in-the-family-1-sezon-1-bolum"
    args = sys.argv[1:]

    headless = True
    if "--headed" in args:
        headless = False
        args.remove("--headed")

    target_url = args[0] if args else default_url
    scraper = DizipubScraper(headless=headless)
    start = time.time()
    result = scraper.get_stream_info(target_url)
    duration = time.time() - start

    if result:
        print("\n" + "=" * 80)
        print("  SUCCESS")
        print("=" * 80)
        print(f"  Master URL: {result['master_url']}")
        print(f"  Variants: {len(result['variants'])}")
    else:
        print("\n? Stream extraction failed.")

    print(f"\nElapsed: {duration:.1f}s")


if __name__ == "__main__":
    main()
