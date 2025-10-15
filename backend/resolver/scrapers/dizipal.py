"""
Dizipal scraper implementation.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urljoin

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


class DizipalScraper:
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
        "Gecko/20100101 Firefox/121.0"
    )

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self.master_url: Optional[str] = None
        self.playlist_content: Optional[str] = None
        self.embed_url: Optional[str] = None
        self.user_agent: str = self.DEFAULT_USER_AGENT
        self._variants: List[StreamVariant] = []
        self.cookies_header: str = ""

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_playlist(response: Response) -> bool:
        url = response.url.lower()
        if ".m3u8" in url:
            return True
        content_type = (response.headers or {}).get("content-type", "").lower()
        return "application/vnd.apple.mpegurl" in content_type

    def _response_handler(self):
        def _capture(response: Response) -> None:
            if not self._is_playlist(response):
                return

            if not self.master_url:
                self.master_url = response.url
                print(f"  [capture] Master playlist: {self.master_url}")

            if not self.playlist_content:
                try:
                    text = response.text()
                except Exception:
                    text = ""
                if text:
                    self.playlist_content = text
                    print(f"  [capture] Playlist bytes: {len(text)}")

        return _capture

    def _parse_master_playlist(self, master_url: str, content: str) -> List[StreamVariant]:
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

    def _trigger_player(self, page) -> None:
        script = """
            (() => {
                try {
                    if (typeof disableDevtool !== 'undefined') {
                        disableDevtool.stop && disableDevtool.stop();
                    }
                } catch (e) {}

                try {
                    document.querySelectorAll('iframe').forEach(iframe => {
                        if (iframe.dataset && iframe.dataset.src && !iframe.src) {
                            iframe.src = iframe.dataset.src;
                        }
                    });
                } catch (e) {}

                try {
                    if (typeof startBd === 'function') {
                        startBd(1);
                    }
                } catch (e) {}

                const selectors = [
                    '#adContentWrapper',
                    '#mPlayerFd',
                    '.play-pre-bl',
                    'button[data-player]',
                    '.server-btn',
                    '[data-player-selector]',
                    '.btn-play',
                    '.plyr__control--overlaid',
                    '.vjs-big-play-button'
                ];

                for (const selector of selectors) {
                    const elements = Array.from(document.querySelectorAll(selector));
                    for (const element of elements) {
                        try {
                            element.click();
                        } catch (e) {}
                    }
                }
            })();
        """
        try:
            page.evaluate(script)
        except Exception:
            pass

        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
        except Exception:
            pass

    def _capture_embed_url(self, page) -> None:
        try:
            iframe = page.query_selector("iframe[src*='://']")
            if iframe:
                src = iframe.get_attribute("src")
                if src:
                    if src.startswith("//"):
                        src = f"https:{src}"
                    self.embed_url = src
                    print(f"  [capture] Embed iframe: {self.embed_url}")
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def get_stream_info(self, episode_url: str) -> Optional[Dict[str, object]]:
        print("=" * 80)
        print(f"PARSING: {episode_url}")
        print("=" * 80)

        self.master_url = None
        self.playlist_content = None
        self.embed_url = None
        self._variants = []

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
            self._trigger_player(page)
            page.wait_for_timeout(1500)
            self._capture_embed_url(page)

            for i in range(40):
                if self.master_url and self.playlist_content:
                    break
                if (i + 1) % 5 == 0:
                    print(f"  [wait] {i + 1}s without playlist capture...")
                self._trigger_player(page)
                page.wait_for_timeout(1000)

            if self.master_url and not self.playlist_content:
                try:
                    script = """
                        async (masterUrl) => {
                            const response = await fetch(masterUrl, { credentials: 'include' });
                            return await response.text();
                        }
                    """
                    self.playlist_content = page.evaluate(script, self.master_url)
                    print(
                        f"  [fetch] Pulled playlist ({len(self.playlist_content)} bytes)"
                    )
                except Exception as exc:
                    print(f"  [fetch] Failed to fetch playlist: {exc}")

            try:
                cookies = context.cookies()
                if cookies:
                    self.cookies_header = "; ".join(f"{item['name']}={item['value']}" for item in cookies)
            except Exception:
                self.cookies_header = ""

            browser.close()

        if not self.master_url or not self.playlist_content:
            print("? No playlist captured.")
            return None

        self._variants = self._parse_master_playlist(self.master_url, self.playlist_content)

        return {
            "embed_url": self.embed_url,
            "master_url": self.master_url,
            "variants": [
                {
                    "quality": variant.quality,
                    "resolution": variant.resolution,
                    "bandwidth": variant.bandwidth,
                    "url": variant.url,
                }
                for variant in self._variants
            ],
            "raw_playlist": self.playlist_content,
            "user_agent": self.user_agent,
            "cookies": self.cookies_header,
            "page_url": episode_url,
        }


def main() -> None:
    default_url = "https://dizipal1503.com/bolum/twisted-metal-2x8"
    args = sys.argv[1:]

    headless = True
    if "--headed" in args:
        headless = False
        args.remove("--headed")

    target_url = args[0] if args else default_url
    scraper = DizipalScraper(headless=headless)
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
