# Turkish Streaming Site Scrapers

Proof-of-concept scrapers for Turkish streaming sites.

## Current Implementation

### 1. HDFilmCehennemi (Working) ✅

**Site Info:**
- URL: https://hdfilmcehennemi.la (domain changes frequently)
- Content: Turkish dubbed/subtitled movies and TV shows
- Traffic: High volume (Turkey)

**Status:** Fully functional

**Features:**
- ✅ Extract stream URLs from movie pages
- ✅ Playwright-based browser automation
- ✅ Master playlist capture
- ✅ Session-based stream handling
- ✅ Single quality stream (MEDIA playlist)

---

### 2. Dizimia (Working) ✅

**Site Info:**
- URL: https://dizimia4.com (domain changes frequently)
- Content: Turkish dubbed/subtitled TV series
- Traffic: High volume (Turkey)

**Status:** Fully functional

**Features:**
- ✅ Extract stream URLs from episode pages
- ✅ Playwright-based browser automation
- ✅ Cloudflare handling
- ✅ Multi-quality support (HD/FHD)
- ✅ MASTER playlist with variants
- ✅ Response interception for session streams

---

### 3. Dizibox (Working) ✅

**Site Info:**
- URL: https://dizibox.live (domain changes frequently)
- Content: Turkish dubbed/subtitled TV series
- Traffic: Medium volume (Turkey)

**Status:** Fully functional

**Features:**
- ✅ Extract stream URLs from episode pages
- ✅ Playwright-based browser automation
- ✅ 1080p MEDIA playlist (838 segments)
- ✅ PNG-disguised MPEG-TS segments
- ✅ Content-Type fixing via proxy
- ✅ Response interception for session streams

**Special Handling:**
- Segments have `.png` extension but contain MPEG-TS data
- Server sends `Content-Type: image/png`
- Proxy automatically fixes to `video/mp2t` for VLC compatibility

---

### 4. Universal Proxy Server ⭐

**One proxy for all sites!**

**Features:**
- 🔍 Auto-detects site from URL
- 📝 Site-specific header injection
- 🔄 Automatic URL rewriting
- 🔧 Content-Type fixing (Dizibox PNG→MPEG-TS)
- 🌐 HDFilmCehennemi + Dizibox support
- ➕ Easy to add new sites

**Location:** `working/universal_proxy_server.py`

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
playwright install firefox
```

### 2. Extract Stream URL

**For HDFilmCehennemi (Movies):**
```bash
cd working
python hdfilm_scraper.py
```

**For Dizimia (TV Series):**
```bash
cd working
python dizimia_scraper.py
```

Both scrapers will:
1. Open Firefox browser
2. Wait for you to click PLAY (and solve Cloudflare if needed)
3. Automatically capture the stream URL and content
4. Save results to JSON file

### 3. Start Universal Proxy Server

```bash
cd working
python universal_proxy_server.py
```

The proxy runs on `http://127.0.0.1:5000` and works for **all sites**.

### 4. Play in VLC

```bash
# HDFilmCehennemi
vlc "http://127.0.0.1:5000/stream/srv10.cdnimages961.sbs/hls/..."

# Dizimia
vlc "http://127.0.0.1:5000/stream/four.pichive.online/master.m3u8?v=..."
```

Or use VLC's "Open Network Stream" menu.

**Note:** The same proxy works for both HDFilmCehennemi and Dizimia!

---

## How It Works

### Stream URL Extraction

Both scrapers use the same approach:

1. **Browser Automation:**
   - Uses Playwright (Firefox) to load the page
   - Waits for user to click PLAY button (anti-bot measure)
   
2. **Network Interception:**
   - Captures M3U8 URL via `page.on('response')` event
   - Fetches content directly from response body
   
3. **Playlist Parsing:**
   - HDFilmCehennemi: MEDIA playlist (single quality, `.txt`)
   - Dizimia: MASTER playlist (HD/FHD variants, `.m3u8`)
   - Returns stream URL and metadata

### Universal Proxy Server

**Why is a proxy needed?**

All Turkish streaming CDNs require specific headers:
- `Referer`: Site URL
- `Origin`: Site domain
- `User-Agent`: Browser UA

VLC and other players don't send these headers by default, resulting in **404 Not Found** errors.

**How the universal proxy works:**

1. **Site Detection:**
   ```python
   srv10.cdnimages961.sbs    → HDFilmCehennemi
   four.pichive.online       → Dizimia
   ```

2. **Header Injection:**
   - Automatically selects correct headers for detected site
   - Each site has its own header profile

3. **Request Forwarding:**
   - Adds site-specific headers
   - Forwards to CDN
   - Returns response to player

4. **URL Rewriting:**
   - Rewrites segment URLs in playlists
   - Ensures all segments route through proxy
   
   ```
   Original:  https://srv10.cdnimages159.sbs/.../segment.jpg
   Proxied:   http://127.0.0.1:5000/stream/https://srv10.cdnimages159.sbs/.../segment.jpg
   ```

**Adding New Sites:**

Simply add a new profile to `SITE_HEADERS`:

```python
'newsite': {
    'domains': ['newsite.com', 'cdn.newsite.com'],
    'headers': {
        'Referer': 'https://newsite.com/',
        'Origin': 'https://newsite.com',
        'User-Agent': 'Mozilla/5.0 ...'
    }
}
```

---

## Output Format

Stream data is returned in this format:

```json
{
  "embed_url": "https://hdfilmcehennemi.mobi/video/embed/...",
  "master_url": "https://srv10.cdnimages961.sbs/.../master.txt",
  "variants": [
    {
      "quality": "Default",
      "resolution": "Unknown",
      "bandwidth": 0,
      "url": "https://srv10.cdnimages961.sbs/.../master.txt"
    }
  ],
  "raw_playlist": "#EXTM3U\n#EXT-X-VERSION:3\n..."
}
```

---

## Testing

### Test Stream URL Requirements

```bash
cd working
python test_stream_url.py
```

This tests if the stream URL requires headers:
- **Without headers:** 404 Not Found ❌
- **With headers:** 200 OK ✅

### Test Proxy Server

```bash
# Terminal 1: Start proxy
python hdfilm_proxy_server.py

# Terminal 2: Test proxy
python test_proxy.py
```

Verifies that the proxy correctly:
- Fetches the master playlist
- Rewrites segment URLs
- Adds required headers

---

## Architecture

```
┌─────────────────┐
│  Movie Page     │
│ (User clicks    │
│  PLAY button)   │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ hdfilm_scraper  │ → Captures master.txt URL
│ (Playwright)    │ → Fetches playlist content
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Master Playlist │ → #EXTM3U with segment list
│ (79KB, 767 seg) │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Proxy Server    │ → Adds headers (Referer/Origin)
│ (Flask)         │ → Rewrites segment URLs
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   VLC Player    │ → Plays stream smoothly
└─────────────────┘
```

---

## Technical Details

### Stream URLs

HDFilmCehennemi uses **session-based streams**:
- URLs expire quickly (minutes)
- Tied to browser session
- Require specific headers

**Playlist Format:**
- Extension: `.txt` (not `.m3u8`)
- Type: MEDIA playlist (direct segment list)
- No quality variants (single stream)

### Required Headers

```python
{
    'Referer': 'https://hdfilmcehennemi.mobi/',
    'Origin': 'https://hdfilmcehennemi.mobi',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
}
```

### Browser Automation

- **Browser:** Firefox (via Playwright)
- **Headless:** No (for manual PLAY button click)
- **Event:** `page.on('response')` to capture network traffic
- **Timing:** Uses `page.wait_for_timeout()` for real-time event processing

---

## Files

### `working/hdfilm_scraper.py`
Main scraper - extracts stream URLs from movie pages.

### `working/hdfilm_proxy_server.py`
Flask-based proxy server - adds headers and rewrites URLs.

### `working/test_stream_url.py`
Tests if stream URL requires headers.

### `working/test_proxy.py`
Tests proxy server functionality.

### `working/SITE_ANALYSIS.md`
Detailed technical analysis of HDFilmCehennemi.

### `working/README.md`
Detailed documentation for working scripts.

---

## Next Steps

1. **Full Automation**
   - Automatic PLAY button detection and clicking
   - Bypass bot detection
   
2. **Dizimia Support**
   - Apply same architecture to Dizimia
   - Handle TV series episodes
   
3. **Multi-Site Proxy**
   - Single proxy for multiple sites
   - Site-specific header profiles
   
4. **Prowlarr Indexer**
   - Torznab API wrapper
   - Jellyfin/Radarr/Sonarr integration
   
5. **Metadata Enhancement**
   - TMDB/TVDB matching
   - Poster/artwork extraction

---

## Known Limitations

1. **Manual PLAY Click:**
   - Anti-bot detection requires user interaction
   - Cannot be fully automated (yet)
   
2. **Domain Changes:**
   - Site domains change frequently
   - Scraper needs URL updates
   
3. **Session Expiration:**
   - Stream URLs expire quickly
   - On-demand extraction required (no caching)
   
4. **Single Quality:**
   - Most streams have only one quality
   - No adaptive bitrate variants

---

## Legal Notice

This scraper is for **educational purposes only**.

- Streaming copyrighted content without permission is illegal in most jurisdictions
- Users are responsible for compliance with local laws
- This tool does not host, store, or distribute any content
- It only extracts publicly available URLs from websites

Use responsibly and respect copyright laws.
