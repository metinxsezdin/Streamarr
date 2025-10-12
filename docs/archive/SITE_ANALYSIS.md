# Turkish Streaming Sites - Technical Analysis

## Objective
Understand the technical architecture of Turkish streaming sites to build reliable scrapers.

---

## Sites to Analyze

### 1. Dizimia (dizimia4.com)
**Type:** TV Series
**Priority:** High

### 2. HDFilmCehennemi (hdfilmcehennemi[X].com)
**Type:** Movies
**Priority:** Medium

### 3. Dizilla (dizilla40.com)
**Type:** TV Series
**Priority:** Low (already analyzed via Kodi plugin)

---

## Analysis Checklist for Each Site

### A. Initial Page Load
- [ ] URL structure for episodes/movies
- [ ] JavaScript frameworks used (React, Vue, Next.js, etc.)
- [ ] SPA (Single Page Application) vs Traditional
- [ ] Cloudflare / Bot protection mechanisms
- [ ] DevTools detection

### B. Video Player
- [ ] Player technology (Video.js, HLS.js, JWPlayer, etc.)
- [ ] Iframe structure
- [ ] Player domain (same or different from main site)
- [ ] Auto-play behavior

### C. Stream URL Discovery
- [ ] How is M3U8 URL generated? (API call, embedded in page, etc.)
- [ ] M3U8 URL format and patterns
- [ ] Required headers (Referer, User-Agent, etc.)
- [ ] Authentication/Token mechanism
- [ ] Session management

### D. M3U8 Structure
- [ ] Master playlist vs direct variant
- [ ] Available qualities
- [ ] Segment naming pattern
- [ ] Segment duration
- [ ] CDN domains used

### E. Session & Cookies
- [ ] Required cookies
- [ ] Session lifetime
- [ ] IP binding
- [ ] CORS restrictions

### F. Anti-Scraping Measures
- [ ] Rate limiting
- [ ] CAPTCHA
- [ ] Fingerprinting
- [ ] Obfuscation techniques

---

## Manual Investigation Steps

### Step 1: Open in Real Browser (No Automation)
1. Open site in Firefox/Chrome
2. Open DevTools (F12) - Network tab
3. Filter: `m3u8` and `ts`
4. Navigate to an episode/movie
5. Click play on video
6. Observe network requests

### Step 2: Document Findings
- Copy M3U8 URLs
- Note all request headers
- Check response headers
- Identify CDN pattern

### Step 3: Test M3U8 Portability
- Try fetching M3U8 URL with `curl` (with headers)
- Try in VLC
- Test segment URL directly
- Measure link lifetime

### Step 4: Analyze Player JavaScript
- Find player init code
- Look for M3U8 URL construction
- Identify API endpoints
- Check for encryption/obfuscation

---

## Results Will Be Documented Below

### Dizimia Analysis
**Status:** PENDING - Ready for manual investigation

### HDFilmCehennemi Analysis
**Status:** IN PROGRESS

#### Initial Findings (2025-10-11)

**Test Movie:** Nobody 2 (https://www.hdfilmcehennemi.la/nobody-2-2/)

**Architecture:**
- Main site: `hdfilmcehennemi.la`
- Player embed: `hdfilmcehennemi.mobi/video/embed/`
- Video player: Video.js with HLS.js streaming
- CDN: Multiple `.sbs` domains (cdnimages159, cdnimages860, cdnimages1655, etc.)

**Stream URL Discovery:**
1. Main page loads iframe from `hdfilmcehennemi.mobi`
2. POST request to `/ah/` endpoint (likely auth/token generation)
3. Master playlist loaded from: `https://srv10.cdnimages[XXX].sbs/hls/[movie-id].mp4/txt/master.txt`

**CRITICAL FINDING:** HDFilmCehennemi uses `.txt` extension for playlists, NOT `.m3u8`!

**Example URLs:**
```
Embed: https://hdfilmcehennemi.mobi/video/embed/JFa7kMUZr33/?rapidrame_id=qda52qg61lyn
Master: https://srv10.cdnimages1655.sbs/hls/nobody-2-2025-webmp4-JFa7kMUZr33.mp4/txt/master.txt
```

**Session Management - DETAILED FINDINGS:**

**Hash System:**
- Hash is **embedded in iframe JavaScript** (obfuscated with eval/packer)
- Hash format: 32-char MD5-like string (e.g., `210fc90e4bdbbeadd716b82d99ac72a2`)
- Hash is **hard-coded** per video in embed page source
- POST to `/ah/` with `hash=<value>` validates/triggers playback (returns empty 200 OK)

**POST Request Flow:**
1. User clicks PLAY on movie page
2. iframe loads: `https://hdfilmcehennemi.mobi/video/embed/{VIDEO_ID}/`
3. iframe JavaScript (obfuscated) contains hash value
4. Video player automatically POST to: `https://hdfilmcehennemi.mobi/video/embed/{VIDEO_ID}/ah/`
   - Body: `hash={HASH_VALUE}`
   - Headers: `X-Requested-With: XMLHttpRequest`, `Origin: hdfilmcehennemi.mobi`
5. POST returns empty 200 OK (validation only, no data returned)
6. Master playlist URL already present in player config
7. Browser fetches: `https://srv10.cdnimagesXXX.sbs/hls/{filename}.mp4/txt/master.txt`

**Key Insight:**
- Hash does NOT generate master URL - it's a **validation token**
- Master URL is pre-generated and embedded in player source
- CDN domain varies (load balancing: cdnimages159, 860, 1655, 2117, etc.)
- Session requires: proper Referer + Origin headers + valid hash POST
- **No cookies required** - CORS allows `*` on CDN

**Required Headers for Stream Access:**
```
Referer: https://hdfilmcehennemi.mobi/...
Origin: https://hdfilmcehennemi.mobi
User-Agent: Mozilla/5.0...
```

### Dizilla Analysis
**Status:** COMPLETED (via Kodi plugin analysis)
- Uses server-side parser system
- Dynamic parser download
- M3U8 extraction from embedded players
- Requires specific headers

---

## Next Steps After Analysis
1. Design scraper architecture based on findings
2. Implement proof-of-concept for easiest site
3. Build proxy/caching strategy for session management
4. Test reliability and error handling

