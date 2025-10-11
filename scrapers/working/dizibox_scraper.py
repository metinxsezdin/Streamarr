"""
Dizibox Scraper - Proof of Concept
Captures M3U8 stream URL from Dizibox episodes
"""
import time
import re
import json
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

class DiziboxScraper:
    def __init__(self, headless=False):
        self.headless = headless
        self.embed_id = None
        self.quality_url = None
        self.quality_content = None
        self.last_episode_url = None

    def click_videoyu_baslat(self, page):
        """Follow the nested iframe path discovered via codegen."""
        try:
            outer_iframe = page.wait_for_selector("#video-area iframe", timeout=8000)
        except PlaywrightTimeout:
            return False

        outer_frame = outer_iframe.content_frame()
        if not outer_frame:
            return False

        try:
            player_iframe = outer_frame.wait_for_selector("#Player iframe", timeout=8000)
        except PlaywrightTimeout:
            return False

        player_frame = player_iframe.content_frame()
        if not player_frame:
            return False

        try:
            play_button = player_frame.wait_for_selector("text=Videoyu Başlat", timeout=6000)
        except PlaywrightTimeout:
            return False

        try:
            play_button.click(timeout=2000, force=True)
            print("  [auto] Clicked 'Videoyu Başlat' inside nested iframes")
            player_frame.wait_for_timeout(500)
            return True
        except Exception:
            return False

    def auto_start_player(self, page):
        """Attempt to start playback without manual interaction."""
        print("\n[auto] Trying to start the player automatically...")
        time.sleep(1.0)

        if not self.embed_id:
            for _ in range(15):
                if self.embed_id:
                    break
                try:
                    page.wait_for_timeout(200)
                except Exception:
                    time.sleep(0.2)

        # Try the deterministic nested iframe path first
        clicked_codegen = self.click_videoyu_baslat(page)
        if clicked_codegen:
            # Allow a brief moment for the embed/player to initialize
            page.wait_for_timeout(1000)

        keywords = ("embed", "molystream", "player", "video")

        def collect_candidate_frames():
            frames = []
            for frame in page.frames:
                frame_url = (frame.url or "").lower()
                if any(word in frame_url for word in keywords):
                    frames.append(frame)
            if page.main_frame not in frames:
                frames.insert(0, page.main_frame)
            return frames

        play_selectors = [
            "button[aria-label='Play']",
            "button.vjs-big-play-button",
            ".vjs-big-play-button",
            ".plyr__control--overlaid",
            ".jw-icon-playback",
            ".jw-button-play",
            ".btn.btn-play",
            ".btn-play",
            "#play",
            ".fa-play-circle",
            ".fa-play"
        ]

        dismiss_selectors = [
            "button[aria-label='Close']",
            ".vjs-close-button",
            ".modal__close",
            ".overlay-close",
            ".adsbox-close",
            ".close"
        ]

        attempted_embed = False

        for attempt in range(2):
            candidate_frames = collect_candidate_frames()
            play_triggered = False

            for frame in candidate_frames:
                frame_desc = frame.url or "main document"
                print(f"  [auto] Inspecting frame: {frame_desc}")
                try:
                    frame.wait_for_load_state('domcontentloaded', timeout=5000)
                except Exception:
                    pass

                for selector in dismiss_selectors:
                    try:
                        element = frame.query_selector(selector)
                        if element:
                            print(f"    [auto] Closing overlay via selector: {selector}")
                            element.click(timeout=2000, force=True)
                            time.sleep(0.3)
                    except Exception:
                        continue

                for selector in play_selectors:
                    try:
                        element = frame.query_selector(selector)
                        if element:
                            print(f"    [auto] Clicking play selector: {selector}")
                            element.click(timeout=2000, force=True)
                            time.sleep(0.8)
                            play_triggered = True
                            break
                    except Exception:
                        continue

                if play_triggered:
                    break

                try:
                    triggered = frame.evaluate(
                        """
                        () => {
                            const videos = Array.from(document.querySelectorAll('video'));
                            let started = 0;
                            for (const video of videos) {
                                try {
                                    video.muted = true;
                                    const result = video.play();
                                    if (result && typeof result.then === 'function') {
                                        result.then(() => {}).catch(() => {});
                                    }
                                    started += 1;
                                } catch (err) {
                                    // Ignore per-video failures
                                }
                            }
                            return started;
                        }
                        """
                    )
                    if triggered:
                        print(f"    [auto] JS play() triggered on {triggered} video element(s)")
                        time.sleep(1.0)
                        play_triggered = True
                        break
                except Exception:
                    pass

                try:
                    box = frame.evaluate(
                        """
                        () => {
                            const video = document.querySelector('video');
                            if (!video) {
                                return null;
                            }
                            const rect = video.getBoundingClientRect();
                            return {
                                x: rect.left + rect.width / 2,
                                y: rect.top + rect.height / 2
                            };
                        }
                        """
                    )
                    if box:
                        print("    [auto] Clicking video element center via mouse actions")
                        x = float(box["x"])
                        y = float(box["y"])
                        page.mouse.move(x, y)
                        page.mouse.click(x, y)
                        time.sleep(0.8)
                        play_triggered = True
                        break
                except Exception:
                    pass

            if play_triggered:
                return True

            if (
                attempt == 0
                and self.embed_id
                and "molystream" not in (page.url or "").lower()
                and not attempted_embed
                and not clicked_codegen
            ):
                embed_url = f"https://dbx.molystream.org/embed/{self.embed_id}"
                print(f"  [auto] Retrying inside embed: {embed_url}")
                try:
                    page.goto(
                        embed_url,
                        wait_until='domcontentloaded',
                        timeout=30000,
                        referer=self.last_episode_url
                    )
                    time.sleep(2.0)
                    attempted_embed = True
                    continue
                except Exception as exc:
                    print(f"  [auto] Embed retry failed: {exc}")
                    break
            else:
                break

        try:
            played_count = page.evaluate(
                """
                () => {
                    const videos = Array.from(document.querySelectorAll('video'));
                    let triggered = 0;
                    for (const video of videos) {
                        try {
                            video.muted = true;
                            const result = video.play();
                            if (result && typeof result.then === 'function') {
                                result.then(() => {}).catch(() => {});
                            }
                            triggered += 1;
                        } catch (err) {
                            // Ignore individual failures
                        }
                    }
                    return triggered;
                }
                """
            )
            if played_count:
                print(f"  [auto] Triggered play() on {played_count} video element(s)")
                time.sleep(1.0)
                return True
        except Exception as exc:
            print(f"  [auto] JavaScript play() fallback failed: {exc}")

        if clicked_codegen:
            # We at least triggered the primary play button; allow caller to keep listening
            return True

        print("  [auto] Unable to auto-start playback.")
        return False
    
    def get_stream_url(self, episode_url):
        """Extract stream URL from episode page"""
        print("="*80)
        print("  Dizibox Scraper")
        print("="*80)
        print(f"\nEpisode: {episode_url}\n")
        
        quality_responses = {}
        self.embed_id = None
        self.quality_url = None
        self.quality_content = None
        self.last_episode_url = episode_url
        
        def handle_response(response):
            url = response.url
            
            # Capture embed ID
            if 'dbx.molystream.org/embed/' in url and '/q/' not in url and 'sheila' not in url:
                match = re.search(r'/embed/([a-f0-9\-]+)', url)
                if match:
                    self.embed_id = match.group(1)
                    print(f"  ✓ Embed ID: {self.embed_id}")
            
            # Capture quality endpoint
            if '/q/' in url and response.status == 200:
                print(f"\n  ✓✓ Quality URL: {url[:80]}...")
                self.quality_url = url
                try:
                    content = response.text()
                    quality_responses[url] = content
                    self.quality_content = content
                    print(f"  ✓ Content captured: {len(content)} bytes")
                except Exception as e:
                    print(f"  ✗ Failed: {e}")
        
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=self.headless)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
                locale='tr-TR',
                timezone_id='Europe/Istanbul'
            )
            page = context.new_page()
            page.on('response', handle_response)
            
            try:
                print("[1/3] Loading page...")
                page.goto(episode_url, wait_until='domcontentloaded', timeout=30000)
                time.sleep(3)
                
                print("\n[2/3] Attempting to start playback automatically...")
                auto_started = self.auto_start_player(page)
                if auto_started:
                    print("  [auto] Playback trigger sent; waiting for stream response...\n")
                else:
                    print("  [auto] Automatic trigger not confirmed; listening for stream traffic regardless...\n")
                
                for i in range(60):
                    if self.quality_url and self.quality_content:
                        print(f"\n  ✓ Stream captured after {i+1}s!")
                        break
                    if (i + 1) % 5 == 0:
                        print(f"  [{i+1}s] Still waiting...")
                    page.wait_for_timeout(1000)
                
                if not self.quality_url:
                    print("\n  ✗ No stream URL captured")
                    browser.close()
                    return None
                
                print("\n[3/3] Parsing stream...")
                
                # Analyze content
                is_media = '#EXTINF' in self.quality_content
                is_master = '#EXT-X-STREAM-INF' in self.quality_content
                
                if is_media:
                    print(f"  Type: MEDIA playlist (direct stream)")
                    # Extract base URL from segments
                    segment_match = re.search(r'(https?://[^\s]+?)(/[^\s]*\.(png|ts))', self.quality_content)
                    if segment_match:
                        base_url = segment_match.group(1)
                        print(f"  CDN: {base_url}")
                
                # Create proxy URL for VLC
                proxy_url = f"http://127.0.0.1:5000/stream/{self.quality_url}"
                
                # Save results
                results = {
                    'episode_url': episode_url,
                    'embed_id': self.embed_id,
                    'quality_url': self.quality_url,
                    'proxy_url': proxy_url,
                    'stream_type': 'media' if is_media else ('master' if is_master else 'unknown'),
                    'raw_playlist': self.quality_content
                }
                
                with open('dizibox_scraper_result.json', 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                
                print(f"\n  ✓ Results saved to: dizibox_scraper_result.json")
                print(f"\n  VLC URL (proxy): {proxy_url}")
                
                browser.close()
                return results
                
            except Exception as e:
                print(f"\n✗ Error: {e}")
                browser.close()
                return None


def main():
    """Test the scraper"""
    default_url = "https://www.dizibox.live/invasion-3-sezon-8-bolum-izle/"
    args = sys.argv[1:]

    headless = True
    if '--headed' in args:
        headless = False
        args.remove('--headed')

    if args:
        test_url = args[0]
    else:
        test_url = default_url
    
    scraper = DiziboxScraper(headless=headless)
    result = scraper.get_stream_url(test_url)
    
    if result:
        print("\n" + "="*80)
        print("  SUCCESS!")
        print("="*80)
        print(f"\n  Quality URL: {result['quality_url'][:80]}...")
        print(f"  Stream Type: {result['stream_type']}")
        print(f"  Playlist Size: {len(result['raw_playlist'])} bytes")
        print(f"\n  PLAY IN VLC:")
        print(f"  vlc \"{result['proxy_url']}\"")
        print("\n" + "="*80)

if __name__ == "__main__":
    main()

