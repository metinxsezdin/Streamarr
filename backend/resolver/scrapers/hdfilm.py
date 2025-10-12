"""
HDFilmCehennemi scraper implementation.
"""
from __future__ import annotations

import re
import sys
import time
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class HDFilmScraper:
    """Scraper for HDFilmCehennemi movies."""

    DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self.master_url: Optional[str] = None
        self.embed_url: Optional[str] = None
        self.last_page_url: Optional[str] = None
        self.user_agent: str = self.DEFAULT_USER_AGENT

    def auto_start_player(self, page) -> bool:
        """Attempt to trigger the player without manual interaction."""
        print("\n[auto] Starting playback automatically...")
        triggered = False

        try:
            overlay = page.wait_for_selector(".play-that-video", timeout=8000)
            if overlay:
                overlay.click(timeout=2000, force=True)
                print("  [auto] Clicked main poster overlay")
                triggered = True
        except PlaywrightTimeout:
            print("  [auto] Overlay '.play-that-video' not found")
        except Exception as exc:
            print(f"  [auto] Overlay click failed: {exc}")

        try:
            applied = page.evaluate(
                """
                () => {
                    const container = document.querySelector('.video-container');
                    if (!container) {
                        return false;
                    }
                    const iframe = container.querySelector('iframe');
                    if (!iframe) {
                        return false;
                    }
                    let changed = false;
                    if (iframe.dataset && iframe.dataset.src && !iframe.src) {
                        iframe.src = iframe.dataset.src;
                        changed = true;
                    }
                    if (container.hasAttribute('hidden')) {
                        container.removeAttribute('hidden');
                        changed = true;
                    }
                    return changed;
                }
                """
            )
            if applied:
                print("  [auto] Activated hidden iframe container")
                triggered = True
        except Exception as exc:
            print(f"  [auto] Failed to activate iframe container: {exc}")

        iframe_frame = None
        try:
            iframe_element = page.wait_for_selector(".video-container iframe", timeout=8000)
            iframe_frame = iframe_element.content_frame()
            if iframe_element:
                src = iframe_element.get_attribute("src") or iframe_element.get_attribute("data-src")
                if src:
                    self.embed_url = src
                    print(f"  [auto] Detected embed iframe: {src[:80]}...")
        except PlaywrightTimeout:
            print("  [auto] No iframe appeared after attempting activation")
            return triggered
        except Exception as exc:
            print(f"  [auto] Failed to obtain iframe frame: {exc}")
            return triggered

        if not iframe_frame:
            print("  [auto] Unable to resolve iframe content frame")
            return triggered

        try:
            iframe_frame.wait_for_load_state('domcontentloaded', timeout=8000)
        except PlaywrightTimeout:
            pass
        except Exception:
            pass

        try:
            play_button = iframe_frame.get_by_role("button", name="Play Video")
            play_button.click(timeout=3000)
            print("  [auto] Clicked iframe play button (role=button, name='Play Video')")
            iframe_frame.wait_for_timeout(800)
            return True
        except Exception as exc:
            print(f"  [auto] Codegen play button click failed: {exc}")

        play_selectors = [
            "button.vjs-big-play-button",
            ".vjs-big-play-button",
            ".plyr__control--overlaid",
            "button[title='Play Video']",
            ".btn-play",
        ]

        for selector in play_selectors:
            try:
                button = iframe_frame.query_selector(selector)
                if button:
                    button.click(timeout=2000, force=True)
                    print(f"  [auto] Clicked player selector: {selector}")
                    iframe_frame.wait_for_timeout(800)
                    return True
            except Exception:
                continue

        try:
            played_count = iframe_frame.evaluate(
                """
                () => {
                    const video = document.querySelector('video');
                    if (!video) {
                        return false;
                    }
                    video.muted = true;
                    const result = video.play();
                    if (result && typeof result.then === 'function') {
                        result.then(() => {}).catch(() => {});
                    }
                    return true;
                }
                """
            )
            if played_count:
                print("  [auto] Triggered video.play() fallback")
                iframe_frame.wait_for_timeout(1000)
                return True
        except Exception as exc:
            print(f"  [auto] video.play() fallback failed: {exc}")

        print("  [auto] Unable to auto-start playback.")
        return triggered

    def parse_master_playlist(self, content: str) -> List[Dict[str, Any]]:
        if not content:
            return []

        variants: List[Dict[str, Any]] = []
        lines = content.strip().split('\n')

        has_stream_inf = any('#EXT-X-STREAM-INF' in line for line in lines)
        has_segments = any('#EXTINF' in line for line in lines)

        if has_stream_inf:
            print("  Detected: MASTER playlist with multiple variants")
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith('#EXT-X-STREAM-INF'):
                    bandwidth = re.search(r'BANDWIDTH=(\d+)', line)
                    resolution = re.search(r'RESOLUTION=([\dx]+)', line)
                    name = re.search(r'NAME="?([^",]+)"?', line)

                    if i + 1 < len(lines):
                        variant_url = lines[i + 1].strip()
                        if variant_url and not variant_url.startswith('#'):
                            if not variant_url.startswith('http'):
                                variant_url = urljoin(self.master_url, variant_url)
                            variants.append({
                                'quality': name.group(1) if name else 'Unknown',
                                'resolution': resolution.group(1) if resolution else 'Unknown',
                                'bandwidth': int(bandwidth.group(1)) if bandwidth else 0,
                                'url': variant_url
                            })
                            print(f"  ✓ {variants[-1]['quality']}: {variants[-1]['resolution']}")
                i += 1

        elif has_segments:
            print("  Detected: MEDIA playlist (direct stream, single quality)")
            variants.append({
                'quality': 'Default',
                'resolution': 'Unknown',
                'bandwidth': 0,
                'url': self.master_url
            })
            print(f"  ✓ Single stream URL: {self.master_url[:70]}...")

        return variants

    def get_stream_info(self, page_url: str) -> Optional[Dict[str, Any]]:
        print("=" * 80)
        print("  HDFilmCehennemi Scraper - Proof of Concept")
        print("=" * 80)

        master_urls: List[str] = []
        self.master_url = None
        self.embed_url = None
        self.last_page_url = page_url

        def handle_response(response):
            url = response.url
            status = response.status
            if status == 200 and any(x in url.lower() for x in ['/txt/master', 'master.m3u8', 'master.txt']):
                if url not in master_urls:
                    master_urls.append(url)
                    timestamp = time.strftime("%H:%M:%S")
                    print(f"\n  [{timestamp}] ✓✓ MASTER URL CAPTURED: {url[:70]}...")
                    print(f"  Total URLs captured: {len(master_urls)}")

        with sync_playwright() as p:
            browser = p.firefox.launch(headless=self.headless)
            context = browser.new_context(
                user_agent=self.user_agent,
                locale='tr-TR'
            )
            page = context.new_page()
            page.on('response', handle_response)

            try:
                print("\n[1/2] Loading movie page...")
                page.goto(page_url, wait_until='domcontentloaded', timeout=30000)
                time.sleep(3)

                print("\n[2/2] Attempting to start playback automatically...")
                auto_started = self.auto_start_player(page)
                if auto_started:
                    print("  [auto] Playback trigger sent; waiting for master playlist...\n")
                else:
                    print("  [auto] Trigger could not be confirmed; listening for stream traffic...\n")

                for i in range(60):
                    if master_urls:
                        print(f"\n  ✓ Master URL captured after {i + 1}s!")
                        break
                    if (i + 1) % 5 == 0:
                        print(f"  [{i + 1}s] Still waiting... (ensure video is loading)")
                    page.wait_for_timeout(1000)

                if not master_urls:
                    print("  ✗ No master URL captured!")
                    print("  Tip: Make sure the video actually started.")
                    return None

                self.master_url = master_urls[0]
                print(f"  Master URL: {self.master_url[:80]}...")

                print("  Fetching playlist content via browser context...")
                try:
                    content = page.evaluate(
                        f"""
                        async () => {{
                            const response = await fetch('{self.master_url}');
                            return await response.text();
                        }}
                        """
                    )
                    print(f"  ✓ Fetched {len(content)} bytes")
                except Exception as exc:
                    print(f"  ✗ Failed to fetch: {exc}")
                    return None

                iframes = page.query_selector_all('iframe')
                for iframe in iframes:
                    src = iframe.get_attribute('src')
                    if src and ('embed' in src or 'player' in src or 'video' in src):
                        self.embed_url = src
                        break

                print("\n  Parsing playlist variants...")
                variants = self.parse_master_playlist(content)

            except Exception as exc:
                print(f"\n✗ Error: {exc}")
                return None
            finally:
                print("\n  Closing browser (waiting for cleanup)...")
                time.sleep(2)
                browser.close()

        embed_url = self.embed_url

        print("\n" + "=" * 80)
        print("  RESULTS")
        print("=" * 80)
        if embed_url:
            print(f"  Embed URL: {embed_url[:70]}...")
        print(f"  Master URL: {self.master_url[:70]}...")
        print(f"  Variants found: {len(variants)}")
        print("=" * 80 + "\n")

        return {
            'embed_url': embed_url,
            'master_url': self.master_url,
            'variants': variants,
            'raw_playlist': content,
            'user_agent': self.user_agent
        }


def main() -> None:
    test_url = "https://www.hdfilmcehennemi.la/nobody-2-2/"
    scraper = HDFilmScraper(headless=False)

    try:
        result = scraper.get_stream_info(test_url)
        if result and result['variants']:
            print("\n✓ SUCCESS! Stream URLs extracted:")
            print("\nAvailable qualities:")
            for i, variant in enumerate(result['variants'], 1):
                print(f"\n  {i}. {variant['quality']} ({variant['resolution']})")
                print(f"     URL: {variant['url'][:100]}...")

            import json
            with open('hdfilm_scraper_result.json', 'w', encoding='utf-8') as handle:
                json.dump(result, handle, indent=2, ensure_ascii=False)
            print("\n✓ Full results saved to: hdfilm_scraper_result.json")

            with open('hdfilm_master_playlist.txt', 'w', encoding='utf-8') as handle:
                handle.write(result['raw_playlist'])
            print("✓ Master playlist saved to: hdfilm_master_playlist.txt")
        else:
            print("\n✗ Failed to extract stream information")

    except Exception as exc:
        print(f"\n✗ Error: {exc}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
