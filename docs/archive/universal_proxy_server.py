"""
Universal Proxy Server for Turkish Streaming Sites
Automatically detects site and adds required headers
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from flask import Flask, Response, request
import requests
import sys
import io
import logging
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Ensure UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

app = Flask(__name__)

# Constants
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
PROXY_HOST = '127.0.0.1'
PROXY_PORT = 5000
CHUNK_SIZE = 8192
REQUEST_TIMEOUT = 30


@dataclass
class SiteConfig:
    """Configuration for a streaming site"""
    name: str
    domains: List[str]
    referer: str
    origin: str
    user_agent: str = DEFAULT_USER_AGENT
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers for this site"""
        return {
            'Referer': self.referer,
            'Origin': self.origin,
            'User-Agent': self.user_agent,
        }


# Site configurations
SITE_CONFIGS = [
    SiteConfig(
        name='hdfilmcehennemi',
        domains=['hdfilmcehennemi.la', 'hdfilmcehennemi.mobi', 'hdfilmcehennemi.com', 'cdnimages'],
        referer='https://hdfilmcehennemi.mobi/',
        origin='https://hdfilmcehennemi.mobi'
    ),
    SiteConfig(
        name='dizibox',
        domains=['dizibox.live', 'molystream.org', '.xyz'],
        referer='https://dbx.molystream.org/',
        origin='https://dbx.molystream.org'
    ),
]


def detect_site(url: str) -> Optional[SiteConfig]:
    """
    Detect which site the URL belongs to
    
    Args:
        url: The stream URL to analyze
        
    Returns:
        SiteConfig if site detected, None otherwise
    """
    url_lower = url.lower()
    
    for config in SITE_CONFIGS:
        for domain in config.domains:
            if domain.lower() in url_lower:
                return config
    
    return None


def get_default_headers() -> Dict[str, str]:
    """Get default headers for unknown sites"""
    return {'User-Agent': DEFAULT_USER_AGENT}


def should_fix_content_type(site_config: Optional[SiteConfig], url: str) -> bool:
    """
    Check if Content-Type needs fixing
    
    Args:
        site_config: The site configuration
        url: The stream URL
        
    Returns:
        True if Content-Type should be fixed
    """
    return site_config and site_config.name == 'dizibox' and url.endswith('.png')


def fix_content_type(original_type: str, site_config: Optional[SiteConfig], url: str) -> Tuple[str, bool]:
    """
    Fix Content-Type header if needed
    
    Args:
        original_type: Original Content-Type from response
        site_config: The site configuration
        url: The stream URL
        
    Returns:
        Tuple of (content_type, was_fixed)
    """
    if should_fix_content_type(site_config, url):
        return 'video/mp2t', True
    return original_type or 'application/vnd.apple.mpegurl', False


def is_playlist(content_type: str, url: str) -> bool:
    """
    Check if response is a playlist
    
    Args:
        content_type: Content-Type header value
        url: The stream URL
        
    Returns:
        True if response is likely a playlist
    """
    return (
        'mpegurl' in content_type or 
        'text' in content_type or 
        url.endswith(('.m3u8', '.txt'))
    )


def rewrite_playlist_urls(content: str, base_url: str) -> Tuple[str, int]:
    """
    Rewrite URLs in playlist to go through proxy
    
    Args:
        content: Playlist content
        base_url: Base URL for relative paths
        
    Returns:
        Tuple of (rewritten_content, num_urls_rewritten)
    """
    if '#EXTM3U' not in content and '#EXT-X-' not in content:
        return content, 0
    
    lines = []
    urls_rewritten = 0
    
    for line in content.split('\n'):
        stripped = line.strip()
        
        # Skip empty lines and comments
        if not stripped or stripped.startswith('#'):
            lines.append(line)
            continue
        
        # Process URLs
        if stripped.startswith('http'):
            # Absolute URL - proxy it
            proxy_url = f"http://{PROXY_HOST}:{PROXY_PORT}/stream/{stripped}"
            lines.append(proxy_url)
            urls_rewritten += 1
        elif stripped:
            # Relative URL - make absolute and proxy it
            absolute_url = f"{base_url}/{stripped}"
            proxy_url = f"http://{PROXY_HOST}:{PROXY_PORT}/stream/{absolute_url}"
            lines.append(proxy_url)
            urls_rewritten += 1
        else:
            lines.append(line)
    
    return '\n'.join(lines), urls_rewritten


def create_response_headers(content_type: str) -> Dict[str, str]:
    """
    Create response headers with CORS enabled
    
    Args:
        content_type: Content-Type value
        
    Returns:
        Dictionary of response headers
    """
    return {
        'Content-Type': content_type,
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Access-Control-Allow-Headers': '*',
    }


@app.route('/stream/<path:stream_url>')
def proxy_stream(stream_url: str) -> Response:
    """
    Proxy stream URL with auto-detected headers
    
    Args:
        stream_url: The stream URL to proxy
        
    Returns:
        Flask Response object
    """
    # Reconstruct full URL
    if not stream_url.startswith('http'):
        stream_url = 'https://' + stream_url
    
    # Detect site and get headers
    site_config = detect_site(stream_url)
    headers = site_config.get_headers() if site_config else get_default_headers()
    
    # Logging
    site_label = f"[{site_config.name.upper()}]" if site_config else "[UNKNOWN]"
    logger.info(f"{site_label} Request: {stream_url[:80]}...")
    
    try:
        # Make request with site-specific headers
        response = requests.get(stream_url, headers=headers, stream=True, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        logger.info(f"{site_label} CDN Response: {response.status_code}")
        
        # Get and fix Content-Type
        original_content_type = response.headers.get('Content-Type', 'application/vnd.apple.mpegurl')
        content_type, was_fixed = fix_content_type(original_content_type, site_config, stream_url)
        
        if was_fixed:
            logger.info(f"{site_label} Fixed Content-Type: {original_content_type} -> {content_type}")
        
        # Create response headers
        response_headers = create_response_headers(content_type)
        
        # Handle playlists
        if is_playlist(original_content_type, stream_url):
            content = response.text
            base_url = '/'.join(stream_url.split('/')[:-1])
            
            rewritten_content, urls_rewritten = rewrite_playlist_urls(content, base_url)
            
            if urls_rewritten > 0:
                logger.info(f"{site_label} Rewrote {urls_rewritten} URLs")
                return Response(rewritten_content, headers=response_headers)
        
        # Binary content (segments, images, etc.)
        def generate():
            """Generator for streaming binary content"""
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    yield chunk
        
        return Response(generate(), headers=response_headers)
    
    except requests.exceptions.RequestException as e:
        logger.error(f"{site_label} Request error: {e}")
        return Response(f"Proxy error: {e}", status=502)
    except Exception as e:
        logger.error(f"{site_label} Unexpected error: {e}")
        return Response(f"Server error: {e}", status=500)


@app.route('/')
def index() -> str:
    """Info page"""
    sites_html = ""
    for config in SITE_CONFIGS:
        sites_html += f"<li><strong>{config.name.upper()}</strong>: {', '.join(config.domains)}</li>"
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Universal Streaming Proxy</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            pre {{ background: #f4f4f4; padding: 10px; border-radius: 5px; }}
            code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }}
        </style>
    </head>
    <body>
        <h1>🌐 Universal Streaming Proxy Server</h1>
        <p>Running on <strong>http://{PROXY_HOST}:{PROXY_PORT}</strong></p>
        
        <h2>Supported Sites:</h2>
        <ul>{sites_html}</ul>
        
        <h2>Usage:</h2>
        <pre>vlc "http://{PROXY_HOST}:{PROXY_PORT}/stream/&lt;STREAM_URL&gt;"</pre>
        
        <h2>Features:</h2>
        <ul>
            <li>🔍 Auto-detects site from URL</li>
            <li>📝 Adds site-specific headers automatically</li>
            <li>🔄 Rewrites playlist URLs to route through proxy</li>
            <li>🔧 Fixes Content-Type for disguised segments (Dizibox)</li>
        </ul>
        
        <h2>Health Check:</h2>
        <p><a href="/health">/health</a></p>
    </body>
    </html>
    """


@app.route('/health')
def health() -> Dict[str, any]:
    """Health check endpoint"""
    return {
        'status': 'ok',
        'supported_sites': [config.name for config in SITE_CONFIGS],
        'version': '2.0'
    }


def main():
    """Main entry point"""
    print("=" * 80)
    print("  Universal Streaming Proxy Server v2.0")
    print("=" * 80)
    print("\n  Supported Sites:")
    for config in SITE_CONFIGS:
        print(f"    - {config.name.upper()}: {len(config.domains)} domain(s)")
    print(f"\n  Server: http://{PROXY_HOST}:{PROXY_PORT}")
    print(f"  Health: http://{PROXY_HOST}:{PROXY_PORT}/health")
    print("\n  Press Ctrl+C to stop")
    print("=" * 80 + "\n")
    
    app.run(host=PROXY_HOST, port=PROXY_PORT, threaded=True, debug=False)


if __name__ == '__main__':
    main()
