"""
HDFilmCehennemi scraper implementation.
"""
from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from typing import Callable, Optional, Dict, Any, List
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


@dataclass
class PlayerProfile:
    name: str
    matcher: Callable[[Optional[str]], bool]
    selectors: List[str]
    fallback_video_play: bool = True


class HDFilmScraper:
    """Scraper for HDFilmCehennemi movies."""

    DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self.master_url: Optional[str] = None
        self.embed_url: Optional[str] = None
        self.last_page_url: Optional[str] = None
        self.user_agent: str = self.DEFAULT_USER_AGENT
        self.player_profiles: List[PlayerProfile] = self._build_profiles()

    def _build_profiles(self) -> List[PlayerProfile]:
        rapidrame_hosts = ("rapidrame", "rplayer", "hdfilmcehennemi.la/player")
        sobreats_hosts = ("sobreatsesuyp", "playnn", "playmix", "playdn", "movie", "wniodl", "sstream")

        def host_match(hosts: tuple[str, ...]) -> Callable[[Optional[str]], bool]:
            return lambda url: bool(url and any(host in url for host in hosts))

        return [
            PlayerProfile(
                name="rapidrame",
                matcher=host_match(rapidrame_hosts),
                selectors=[
                    "button.vjs-big-play-button",
                    ".vjs-big-play-button",
                    ".plyr__control--overlaid",
                    "button[title='Play Video']",
                    "button.plyr__control--overlaid",
                ],
            ),
            PlayerProfile(
                name="plyr-generic",
                matcher=host_match(sobreats_hosts),
                selectors=[
                    "button[aria-label='Play']",
                    ".plyr__controls button[data-plyr='play']",
                    ".plyr__control--overlaid",
                    ".plyr__control.plyr__control--overlaid",
                ],
            ),
            PlayerProfile(
                name="default",
                matcher=lambda _: True,
                selectors=[
                    "button.vjs-big-play-button",
                    ".vjs-big-play-button",
                    ".plyr__control--overlaid",
                    "button[title='Play Video']",
                    "button.plyr__control",
                ],
            ),
        ]

    def _click_selectors(self, frame, selectors: List[str]) -> bool:
        for selector in selectors:
            try:
                button = frame.query_selector(selector)
                if not button:
                    continue
                button.click(timeout=2000, force=True)
                print(f"  [profile] Clicked selector: {selector}")
                frame.wait_for_timeout(800)
                return True
            except Exception:
                continue
        return False

    def _video_play_fallback(self, frame) -> bool:
        try:
            played_count = frame.evaluate(
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
                frame.wait_for_timeout(1000)
                return True
        except Exception as exc:
            print(f"  [auto] video.play() fallback failed: {exc}")
        return False

    def _start_with_profiles(self, frame, embed_url: Optional[str]) -> bool:
        profile_names = []
        for profile in self.player_profiles:
            if not profile.matcher(embed_url):
                continue
            profile_names.append(profile.name)
            print(f"  [profile] Attempting '{profile.name}' profile")
            if self._execute_profile(profile, frame):
                return True
        if profile_names:
            print(f"  [profile] No success with profiles: {', '.join(profile_names)}")
        return False

    def _switch_to_tab(self, page, keyword: str) -> bool:
        pattern = re.compile(keyword, re.IGNORECASE)
        selectors = [
            f"text=/{keyword}/i",
            f"//button[contains(translate(normalize-space(.), '{keyword.upper()}', '{keyword.lower()}'), '{keyword.lower()}')]",
            f"//a[contains(translate(normalize-space(.), '{keyword.upper()}', '{keyword.lower()}'), '{keyword.lower()}')]",
            f"//li[contains(translate(normalize-space(.), '{keyword.upper()}', '{keyword.lower()}'), '{keyword.lower()}')]",
            "[data-player]",
            "[data-target]",
            "[data-source]",
        ]

        for selector in selectors:
            try:
                locator = page.locator(selector)
            except Exception:
                continue

            count = locator.count()
            if count == 0:
                continue

            for idx in range(count):
                candidate = locator.nth(idx)
                text = ""
                try:
                    text = candidate.inner_text(timeout=500) or ""
                except Exception:
                    pass

                attr_values = []
                try:
                    attr_values = [
                        candidate.get_attribute("data-player"),
                        candidate.get_attribute("data-target"),
                        candidate.get_attribute("data-source"),
                    ]
                except Exception:
                    pass

                if text and pattern.search(text):
                    print(f"  [tab] Switching to tab '{text.strip()}' via selector '{selector}'")
                    try:
                        candidate.click(timeout=2000, force=True)
                        page.wait_for_timeout(1500)
                        return True
                    except Exception as exc:
                        print(f"  [tab] Failed to click tab '{text.strip()}': {exc}")
                        continue

                if any(value and pattern.search(value) for value in attr_values):
                    print(f"  [tab] Switching via attribute using selector '{selector}'")
                    try:
                        candidate.click(timeout=2000, force=True)
                        page.wait_for_timeout(1500)
                        return True
                    except Exception as exc:
                        print(f"  [tab] Failed attribute click: {exc}")
                        continue

        print(f"  [tab] Could not locate a tab matching '{keyword}'")
        return False

    def _execute_profile(self, profile: PlayerProfile, frame) -> bool:
        if frame is None:
            return False
        clicked = self._click_selectors(frame, profile.selectors)
        if clicked:
            return True
        if profile.fallback_video_play:
            return self._video_play_fallback(frame)
        return False

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

        if not triggered:
            try:
                page.get_by_role("button", name="Rapidrame").click(timeout=3000)
                page.wait_for_timeout(600)
                print("  [auto] Clicked 'Rapidrame' button via role lookup")
                triggered = True
            except PlaywrightTimeout:
                print("  [auto] 'Rapidrame' button role not found")
            except Exception as exc:
                print(f"  [auto] Failed to click 'Rapidrame' button: {exc}")

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

        play_clicked = False
        try:
            iframe_frame.get_by_role("img", name="Play icon").click(timeout=3000)
            iframe_frame.wait_for_timeout(800)
            print("  [auto] Clicked 'Play icon' inside iframe via role lookup")
            triggered = True
            play_clicked = True
        except PlaywrightTimeout:
            print("  [auto] 'Play icon' role not found inside iframe")
        except Exception as exc:
            print(f"  [auto] Failed to click iframe 'Play icon': {exc}")

        if not play_clicked:
            try:
                page.get_by_role("img", name="Play icon").click(timeout=3000)
                page.wait_for_timeout(600)
                print("  [auto] Clicked 'Play icon' on main page via role lookup")
                triggered = True
                play_clicked = True
            except PlaywrightTimeout:
                print("  [auto] 'Play icon' role not found on main page")
            except Exception as exc:
                print(f"  [auto] Failed to click main page 'Play icon': {exc}")

        try:
            snippet = iframe_frame.content()[:500].replace("\n", " ")
            print(f"  [auto] Frame HTML snippet: {snippet}")
        except Exception as exc:
            print(f"  [auto] Failed to get frame HTML: {exc}")

        if self._start_with_profiles(iframe_frame, self.embed_url):
            return True

        print("  [auto] Unable to auto-start playback with known profiles.")
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

        master_keywords = (
            '/txt/master',
            'master.m3u8',
            'master.txt',
            'playlist.m3u8',
            'index.m3u8',
            '.ism/manifest',
            '.mpd',
        )
        skip_extensions = ('.ts', '.jpg', '.jpeg', '.png', '.gif', '.vtt', '.webvtt', '.aac', '.mp3', '.m4a')

        def maybe_add_master(candidate: str) -> None:
            if not candidate:
                return
            lowered_candidate = candidate.lower()
            if any(lowered_candidate.endswith(ext) for ext in skip_extensions):
                return
            if candidate not in master_urls:
                master_urls.append(candidate)
                timestamp = time.strftime('%H:%M:%S')
                print(f"\n  [{timestamp}] \u2713\u2713 MASTER URL CAPTURED: {candidate[:70]}...")
                print(f"  Total URLs captured: {len(master_urls)}")

        def handle_response(response):
            url = response.url
            status = response.status
            if status != 200:
                return

            lowered = url.lower()
            if any(keyword in lowered for keyword in master_keywords):
                if any(lowered.endswith(ext) for ext in skip_extensions):
                    return
                maybe_add_master(url)
                return

            content_type = ''
            try:
                headers = response.headers
                content_type = (headers.get('content-type') or '').lower()
            except Exception:
                headers = {}

            if any(key in lowered for key in ('.json', '.php')) or 'application/json' in content_type or 'text/plain' in content_type:
                body = ''
                try:
                    body = response.text()
                except Exception:
                    pass
                if body:
                    for match in re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', body):
                        maybe_add_master(match)
                    snippet = body[:200].replace('\n', ' ')
                    print(f"  [capture] {url[:60]} -> {snippet}...")


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

                attempt_configs = [
                    {"label": "default", "keyword": None},
                    {"label": "rapidrame", "keyword": "rapid"},
                ]

                for attempt_index, attempt in enumerate(attempt_configs, start=1):
                    if attempt_index > 1 or attempt["keyword"]:
                        keyword = attempt["keyword"]
                        if keyword:
                            print(f"\n[attempt {attempt_index}] Switching to player tab containing '{keyword}'")
                            if not self._switch_to_tab(page, keyword):
                                print(f"  [attempt {attempt_index}] Tab match for '{keyword}' not found, skipping.")
                                continue
                            master_urls.clear()
                            self.master_url = None
                            self.embed_url = None

                    print(f"\n[attempt {attempt_index}] Attempting to start playback automatically...")
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

                    if master_urls:
                        current_master = self.master_url or master_urls[0]
                        if current_master and "rapid" not in current_master.lower():
                            print(f"  [attempt {attempt_index}] Master '{current_master}' appears to be a slideshow source. Trying next tab...")
                            master_urls.clear()
                            self.master_url = None
                            self.embed_url = None
                            continue
                        break

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
