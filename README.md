# Streamarr Repository

A toolkit for on-demand playback of Turkish streaming sites inside Jellyfin.

## Repository Layout

- ackend/resolver/ – Playwright-based scrapers and Flask resolver API
  - scrapers/ – site-specific scrapers (dizibox, hdfilm)
  - stream_resolver.py – wraps scrapers for CLI/API usage
  - pi.py – Flask application exposing /resolve, /stream/<token>, /catalog
  - metadata_fetcher.py – TMDB integration helpers
- scripts/ – command line utilities for maintaining the catalog and plugin assets
  - collect_links.py – harvest episode/movie URLs
  - catalog_builder.py – enrich harvested URLs and produce catalog.json
  - strm_generator.py – create Jellyfin *.strm files pointing at the resolver API
  - update_manifest.py – generate/refresh plugin manifest.json entries
- plugins/Streamarr/ – Jellyfin plugin source and repository manifest
  - in/Release/net8.0/ – compiled DLL & packaged ZIP ready for releases
- docs/ (optional) – add release notes, architecture diagrams, etc.

## Requirements

- Python 3.11+
- Playwright (pip install -r requirements.txt and playwright install firefox)
- .NET SDK 8.0 (for building the Jellyfin plugin)

## Resolver Quick Start

`ash
cd backend/resolver
python api.py
`
This exposes the resolver API at http://127.0.0.1:5055. Endpoints:
- POST /resolve – resolve an episode/movie URL
- GET /stream/<token> – redirect or JSON response with stream details
- GET /catalog – returns the static catalog used by Jellyfin

## Catalog & STRM Workflow

1. Collect links:
   `ash
   python scripts/collect_links.py --site hdfilm
   python scripts/collect_links.py --site dizibox --max-shows 100
   `
2. Build catalog (requires TMDB_KEY env variable if metadata enrichment is desired):
   `ash
   python scripts/catalog_builder.py --tmdb-key 
   `
3. Generate STRM files for Jellyfin:
   `ash
   python scripts/strm_generator.py --resolver-base http://127.0.0.1:5055
   `
   Point Jellyfin to the generated output/strm directory as a library.

## Jellyfin Plugin

- Build: dotnet build plugins/Streamarr/StreamarrPlugin.csproj -c Release
- Packaged ZIP and manifest are located in plugins/Streamarr/bin/Release/net8.0/
- Use scripts/update_manifest.py to bump versions and checksums before publishing.
- Example release automation:
  `ash
  python scripts/update_manifest.py \
      --manifest docs/manifest.json \
      --zip plugins/Streamarr/bin/Release/net8.0/StreamarrPlugin.zip \
      --version 0.1.1 \
      --target-abi 10.9.0.0 \
      --source-url https://github.com/<user>/Streamarr/releases/download/v0.1.1/StreamarrPlugin.zip \
      --guid 68c71f7d-a14e-4f21-9e10-7c02f51ae7b0 \
      --name Streamarr \
      --category General \
      --owner <user>
  `

## Development Notes

- All Python utilities expect to be executed from the repository root. They automatically add the ackend package to sys.path.
- TMDB integration is optional; if no key is present catalogue enrichment is skipped.
- When publishing to Jellyfin via GitHub Releases or Pages, ensure the manifest URL is accessible and the checksum matches the uploaded ZIP.

Happy streaming!
