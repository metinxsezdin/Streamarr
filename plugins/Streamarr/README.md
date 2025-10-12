# Streamarr Jellyfin Plugin (Preview)

Production-ready Jellyfin integration for the Streamarr resolver stack.

## Features

- Configurable resolver base URL with optional API key forwarded via `X-Api-Key`.
- Resolver client caches the catalog for 10 minutes and auto-invalidates when settings change.
- Admin UI exposes cache tuning + live resolver health check.
- Remote metadata providers (movies, series, episodes) surface Streamarr catalog matches and honour provider IDs.
- Playback integration redirects Jellyfin to the resolver's short-lived `/play/<id>` tokens.

## Build

```
dotnet restore
msbuild StreamarrPlugin.csproj /p:Configuration=Release
```

The resulting DLL can be placed in Jellyfin's plugins directory. This project targets Jellyfin 10.9.3; adjust package versions to match your server.

## Configuration

1. Deploy the Streamarr resolver service (Flask API).
2. Install the plugin and restart Jellyfin.
3. In the admin dashboard, open **Plugins -> Streamarr**, set the resolver base URL (e.g. http://127.0.0.1:5055) and provide an API key if your resolver demands one.
4. Refresh your libraries to pull Streamarr metadata; the plugin automatically re-caches the catalog whenever settings change.

_Note:_ The resolver service must expose `/catalog`, `/resolve`, `/play/<id>`, and `/stream/<token>` endpoints for full functionality.

## Repository Integration

To distribute the plugin via a custom repository, publish `repository.json` and register it inside Jellyfin:

1. Host `plugins/Streamarr/repository.json` on a public URL (GitHub Pages, S3, etc.).
2. In the Jellyfin admin dashboard go to **Plugins -> Repositories -> Add**.
3. Enter a name like "Streamarr Preview" and set the repository URL to the manifest link.
4. After saving, the Streamarr plugin should appear in the catalog and can be installed directly.

Remember to update the `sourceUrl` inside the manifest so it points to the hosted `StreamarrPlugin.dll` file.
