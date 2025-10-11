"""
Dizibox Scraper - Proof of Concept
Captures M3U8 stream URL from Dizibox episodes
"""
import sys
import io
import time
import re
import json
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

class DiziboxScraper:
    def __init__(self, headless=False):
        self.headless = headless
        self.embed_id = None
        self.quality_url = None
        self.quality_content = None
    
    def get_stream_url(self, episode_url):
        """Extract stream URL from episode page"""
        print("="*80)
        print("  Dizibox Scraper")
        print("="*80)
        print(f"\nEpisode: {episode_url}\n")
        
        quality_responses = {}
        
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
                
                print("\n[2/3] Please click PLAY button!")
                print("  Waiting for quality URL...\n")
                
                for i in range(30):
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
    test_url = "https://www.dizibox.live/invasion-3-sezon-8-bolum-izle/"
    
    scraper = DiziboxScraper(headless=False)
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

