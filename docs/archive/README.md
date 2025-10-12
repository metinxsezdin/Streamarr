# Turkish Streaming Scrapers - Working Scripts

Bu klasör HDFilmCehennemi ve Dizimia için çalışan scraper ve proxy dosyalarını içerir.

## Dosyalar

### 1. **Scrapers**

#### `hdfilm_scraper.py`
HDFilmCehennemi film sayfalarından stream URL'leri çıkartır.

**Kullanım:**
```bash
python hdfilm_scraper.py
```

**Akış:**
1. Film sayfasını açar (Firefox)
2. Kullanıcı PLAY butonuna basar
3. Master playlist URL'ini otomatik yakalar
4. İçeriği `hdfilm_scraper_result.json` dosyasına kaydeder

---

#### `dizibox_scraper.py`
Dizibox dizi bölümlerinden stream URL'leri çıkartır.

**Kullanım:**
```bash
python dizibox_scraper.py
```

**Akış:**
1. Bölüm sayfasını açar (Firefox)
2. Kullanıcı PLAY butonuna basar
3. M3U8 quality endpoint'ini otomatik yakalar
4. Proxy URL'i oluşturur
5. Sonuçları `dizibox_scraper_result.json` dosyasına kaydeder

**Özellikler:**
- 1080p MEDIA playlist (838 segment)
- PNG-disguised MPEG-TS segments
- Response interception ile direkt içerik yakalama
- Proxy URL otomatik oluşturma

**Özel Durum:**
Dizibox segment'leri `.png` uzantılı ama içerik MPEG-TS. Proxy sunucusu Content-Type'ı otomatik düzeltir.

---

### 2. **Proxy Server**

#### `universal_proxy_server.py` ⭐
**TÜM siteler için tek proxy server!**

**Özellikler:**
- 🔍 URL'den otomatik site algılama
- 📝 Site-specific header ekleme
- 🔄 Playlist URL rewriting
- 🔧 Content-Type fixing (Dizibox PNG→MPEG-TS)
- 🌐 HDFilmCehennemi, Dizibox desteği
- ➕ Yeni site eklemesi kolay

**Kullanım:**
```bash
python universal_proxy_server.py
```

Sunucu `http://127.0.0.1:5000` adresinde başlar.

**VLC ile kullanım:**
```bash
# HDFilmCehennemi
vlc "http://127.0.0.1:5000/stream/srv10.cdnimages961.sbs/hls/..."

# Dizibox
vlc "http://127.0.0.1:5000/stream/https://dbx.molystream.org/embed/..."
```

**Desteklenen siteler:**
- **HDFilmCehennemi**: hdfilmcehennemi.la, cdnimages
- **Dizibox**: dizibox.live, molystream.org, *.xyz CDN'leri

**Yeni site ekleme:**
`SITE_HEADERS` dictionary'sine yeni profil ekleyin:
```python
'yenisite': {
    'domains': ['yenisite.com', 'cdn.yenisite.com'],
    'headers': {
        'Referer': 'https://yenisite.com/',
        'Origin': 'https://yenisite.com',
        'User-Agent': 'Mozilla/5.0 ...'
    }
}
```

---

### 3. **Test Script**

#### `test_universal_proxy.py`
Universal proxy'nin her iki site için de çalıştığını test eder.

**Kullanım:**
```bash
# Terminal 1: Proxy başlat
python universal_proxy_server.py

# Terminal 2: Test çalıştır
python test_universal_proxy.py
```

---

## Tam Workflow

### HDFilmCehennemi

```bash
# 1. Stream URL çıkart
python hdfilm_scraper.py
# → Browser açılır, PLAY'e tıklayın
# → hdfilm_scraper_result.json oluşur

# 2. Proxy başlat (başka terminal)
python universal_proxy_server.py

# 3. VLC'de oynat
vlc "http://127.0.0.1:5000/stream/[STREAM_URL]"
```

### Dizimia

```bash
# 1. Stream URL çıkart
python dizimia_scraper.py
# → Browser açılır, Cloudflare çözün, PLAY'e tıklayın
# → dizimia_scraper_result.json oluşur

# 2. Proxy başlat (başka terminal)
python universal_proxy_server.py

# 3. VLC'de oynat
vlc "http://127.0.0.1:5000/stream/[STREAM_URL]"
```

### Dizibox

```bash
# 1. Stream URL çıkart
python dizibox_scraper.py
# → Browser açılır, PLAY'e tıklayın
# → dizibox_scraper_result.json oluşur
# → Proxy URL ekranda gösterilir

# 2. Proxy başlat (başka terminal)
python universal_proxy_server.py

# 3. VLC'de oynat
vlc "http://127.0.0.1:5000/stream/[STREAM_URL]"
# veya scraper çıktısındaki komutu direkt çalıştır
```

---

## Teknik Detaylar

### Neden Proxy Gerekiyor?

Tüm siteler CDN isteklerinde **zorunlu header'lar** gerektiriyor:
- `Referer`: Site URL'i
- `Origin`: Site domain'i
- `User-Agent`: Browser UA

VLC bu header'ları göndermediği için direkt URL çalışmaz (404).

**Dizibox için ek gereksinim:**
- Segment'ler `.png` uzantılı ama içerik MPEG-TS
- Sunucu `Content-Type: image/png` gönderiyor
- VLC bu header'a güvenip PNG decoder kullanıyor
- Proxy `Content-Type: video/mp2t` olarak düzeltiyor

### Universal Proxy Nasıl Çalışır?

1. **URL Analizi**: Gelen URL'den site algılanır
   ```
   srv10.cdnimages961.sbs → HDFilmCehennemi
   four.pichive.online → Dizimia
   dby39.90991019.xyz → Dizibox
   ```

2. **Header Injection**: Site-specific header'lar eklenir
   ```python
   # HDFilmCehennemi için
   headers = {
       'Referer': 'https://hdfilmcehennemi.mobi/',
       'Origin': 'https://hdfilmcehennemi.mobi',
       ...
   }
   ```

3. **URL Rewriting**: Playlist içindeki segment URL'leri proxy üzerinden geçecek şekilde yeniden yazılır
   ```
   Orijinal: https://srv10.cdnimages159.sbs/.../segment.jpg
   Rewrite:  http://127.0.0.1:5000/stream/https://srv10.cdnimages159.sbs/.../segment.jpg
   ```

4. **Streaming**: Tüm segment'ler otomatik olarak doğru header'larla indirilir

### Session-Based Streams

Her iki site de **session-based stream URL'ler** kullanıyor:
- URL'ler kısa ömürlü (dakikalar)
- Browser session'ına bağlı
- Direkt HTTP isteklerinde 404 veriyor

**Çözüm:** Response interception ile browser içinden direkt içerik yakalama.

---

## Site Karşılaştırması

| Özellik | HDFilmCehennemi | Dizimia | Dizibox |
|---------|----------------|---------|---------|
| **İçerik** | Filmler | Diziler | Diziler |
| **Playlist Formatı** | `.txt` (MEDIA) | `.m3u8` (MASTER) | `.m3u8` (MEDIA) |
| **Kalite Seçenekleri** | Tek kalite | HD/FHD (2 varyant) | 1080p (tek) |
| **Bot Koruması** | Manuel PLAY | Cloudflare + Manuel PLAY | Manuel PLAY |
| **CDN** | cdnimages | pichive.online | *.xyz (çoklu) |
| **Segment Türü** | JPG görüntü serisi | M3U8 standart | PNG-disguised TS |
| **Özel Durum** | - | - | Content-Type fix gerekli |

---

## Sorun Giderme

### "404 Not Found" hatası
- ✅ Proxy sunucusu çalışıyor mu kontrol edin
- ✅ URL doğru mu? (http://127.0.0.1:5000/stream/...)
- ✅ Stream URL expire olmamış mı? (yeniden scrape edin)

### Video yüklenmiyor
- ✅ Scraper çalışırken PLAY'e bastınız mı?
- ✅ Browser açık kaldı mı tüm işlem boyunca?
- ✅ Cloudflare çözdünüz mü? (Dizimia)

### Proxy yavaş
- ✅ İlk segment yavaş olabilir, sonrası hızlanır
- ✅ CDN hızı değişkendir

### Dizibox video çalışmıyor
- ✅ VLC'de Network Stream kullanıyor musunuz? (dosya olarak açmayın)
- ✅ Proxy loglarını kontrol edin (Content-Type fix mesajları görünmeli)
- ✅ Tarayıcıda stream URL'i test edin (M3U8 playlist görünmeli)

---

## Gelecek Planlar

1. **Otomatik PLAY Tetikleme**
   - JavaScript injection ile otomatik oynatma
   - Bot detection bypass

2. **Metadata Entegrasyonu**
   - TMDB/TVDB ile eşleştirme
   - Poster/artwork çekme

3. **Prowlarr Indexer**
   - Torznab API wrapper
   - Jellyfin/Radarr/Sonarr entegrasyonu

4. **Multi-Episode Support**
   - Tüm sezon bölümlerini toplu scrape
   - Batch processing

5. **Daha Fazla Site**
   - Dizimax, Dizipal, vb.
   - Site profilleri kolayca eklenebilir

---

## Site Analizi

Detaylı teknik analiz için: `SITE_ANALYSIS.md`

---

## Notlar

- Firefox Playwright browser gereklidir
- Proxy arka planda çalışmalı (streaming sırasında)
- Stream URL'ler session-based (kısa ömürlü)
- Manuel PLAY butonu gerekiyor (bot detection)
- Dizimia için Cloudflare bypass gerekebilir
- Dizibox için VLC Network Stream kullanımı zorunlu (M3U8 dosyası olarak açmayın)
