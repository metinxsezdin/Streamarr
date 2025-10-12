using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;

namespace Streamarr.Plugin;

internal sealed class StreamarrApiClient
{
    private static readonly TimeSpan CatalogCacheDuration = TimeSpan.FromMinutes(10);

    private readonly IHttpClientFactory _httpClientFactory;
    private readonly ILogger _logger;

    private readonly object _cacheLock = new();
    private IReadOnlyList<StreamarrCatalogEntry>? _catalogCache;
    private Dictionary<string, StreamarrCatalogEntry>? _catalogIndex;
    private DateTime _catalogCacheTimestamp;
    private string? _lastResolverBaseUrl;
    private string? _lastApiKey;

    public StreamarrApiClient(IHttpClientFactory httpClientFactory, ILogger logger)
    {
        _httpClientFactory = httpClientFactory;
        _logger = logger;
    }

    public async Task<StreamarrCatalogEntry?> GetEntryByIdAsync(string? entryId, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(entryId))
        {
            return null;
        }

        var catalog = await GetCatalogAsync(cancellationToken).ConfigureAwait(false);
        Dictionary<string, StreamarrCatalogEntry>? index;
        lock (_cacheLock)
        {
            index = _catalogIndex;
        }

        if (index is not null && index.TryGetValue(entryId, out var cached))
        {
            return cached;
        }

        return catalog.FirstOrDefault(entry => string.Equals(entry.Id, entryId, StringComparison.OrdinalIgnoreCase));
    }

    private static string NormalizeResolverBase(string? value)
    {
        var baseUrl = string.IsNullOrWhiteSpace(value) ? "http://127.0.0.1:5055" : value.Trim();
        if (!baseUrl.Contains("://", StringComparison.Ordinal))
        {
            baseUrl = $"http://{baseUrl}";
        }

        if (!baseUrl.EndsWith("/", StringComparison.Ordinal))
        {
            baseUrl += "/";
        }

        return baseUrl;
    }

    private (string BaseUrl, string? ApiKey) GetConfigurationSnapshot()
    {
        var configuration = StreamarrPlugin.Instance?.Configuration;
        var resolverBase = NormalizeResolverBase(configuration?.ResolverBaseUrl);
        var apiKey = string.IsNullOrWhiteSpace(configuration?.ApiKey) ? null : configuration!.ApiKey!.Trim();
        return (resolverBase, string.IsNullOrEmpty(apiKey) ? null : apiKey);
    }

    private void EnsureConfigurationSnapshot((string BaseUrl, string? ApiKey) snapshot)
    {
        if (!string.Equals(_lastResolverBaseUrl, snapshot.BaseUrl, StringComparison.OrdinalIgnoreCase)
            || !string.Equals(_lastApiKey, snapshot.ApiKey, StringComparison.Ordinal))
        {
            lock (_cacheLock)
            {
                _catalogCache = null;
                _catalogIndex = null;
                _catalogCacheTimestamp = DateTime.MinValue;
            }

            _lastResolverBaseUrl = snapshot.BaseUrl;
            _lastApiKey = snapshot.ApiKey;
        }
    }

    private void SetCatalogCache(IReadOnlyList<StreamarrCatalogEntry> entries)
    {
        lock (_cacheLock)
        {
            _catalogCache = entries;
            _catalogCacheTimestamp = DateTime.UtcNow;
            _catalogIndex = BuildCatalogIndex(entries);
        }
    }

    private void EnsureCatalogIndex()
    {
        lock (_cacheLock)
        {
            if (_catalogCache is null || _catalogIndex is not null)
            {
                return;
            }

            _catalogIndex = BuildCatalogIndex(_catalogCache);
        }
    }

    private static Dictionary<string, StreamarrCatalogEntry> BuildCatalogIndex(IEnumerable<StreamarrCatalogEntry> entries)
    {
        var index = new Dictionary<string, StreamarrCatalogEntry>(StringComparer.OrdinalIgnoreCase);
        foreach (var entry in entries)
        {
            if (!string.IsNullOrWhiteSpace(entry.Id))
            {
                index[entry.Id] = entry;
            }
        }

        return index;
    }

    private HttpClient CreateClient((string BaseUrl, string? ApiKey) snapshot)
    {
        var client = _httpClientFactory.CreateClient("StreamarrResolver");
        client.BaseAddress = new Uri(snapshot.BaseUrl, UriKind.Absolute);
        client.DefaultRequestHeaders.Remove("X-Api-Key");
        if (!string.IsNullOrWhiteSpace(snapshot.ApiKey))
        {
            client.DefaultRequestHeaders.TryAddWithoutValidation("X-Api-Key", snapshot.ApiKey);
        }

        return client;
    }

    public async Task<IReadOnlyList<StreamarrCatalogEntry>> GetCatalogAsync(CancellationToken cancellationToken)
    {
        var snapshot = GetConfigurationSnapshot();
        EnsureConfigurationSnapshot(snapshot);

        IReadOnlyList<StreamarrCatalogEntry>? cached;
        lock (_cacheLock)
        {
            if (_catalogCache is not null && DateTime.UtcNow - _catalogCacheTimestamp < CatalogCacheDuration)
            {
                cached = _catalogCache;
            }
            else
            {
                cached = null;
            }
        }

        if (cached is not null)
        {
            EnsureCatalogIndex();
            return cached;
        }

        try
        {
            using var client = CreateClient(snapshot);
            var entries = await client.GetFromJsonAsync<IReadOnlyList<StreamarrCatalogEntry>>("catalog", cancellationToken: cancellationToken)
                .ConfigureAwait(false);
            if (entries is not null)
            {
                SetCatalogCache(entries);
                return entries;
            }
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to retrieve catalog from resolver API");
        }

        IReadOnlyList<StreamarrCatalogEntry>? fallback;
        lock (_cacheLock)
        {
            fallback = _catalogCache;
        }

        if (fallback is not null)
        {
            EnsureCatalogIndex();
            return fallback;
        }

        return Array.Empty<StreamarrCatalogEntry>();
    }

    public async Task<StreamarrCatalogEntry?> FindMovieAsync(MovieInfoLookup lookup, CancellationToken cancellationToken)
    {
        var catalog = await GetCatalogAsync(cancellationToken).ConfigureAwait(false);
        return catalog.FirstOrDefault(entry => entry.IsMovie && entry.MatchesMovie(lookup));
    }

    public async Task<IReadOnlyList<StreamarrCatalogEntry>> FindSeriesMatchesAsync(SeriesInfoLookup lookup, CancellationToken cancellationToken)
    {
        var catalog = await GetCatalogAsync(cancellationToken).ConfigureAwait(false);
        var matches = new Dictionary<string, StreamarrCatalogEntry>(StringComparer.OrdinalIgnoreCase);
        foreach (var entry in catalog)
        {
            if (!entry.IsEpisode || !entry.MatchesSeries(lookup))
            {
                continue;
            }

            var key = string.IsNullOrWhiteSpace(entry.SeriesSlug) ? entry.Id : entry.SeriesSlug;
            if (!matches.ContainsKey(key))
            {
                matches[key] = entry;
            }
        }

        return matches.Values.ToList();
    }

    public async Task<StreamarrCatalogEntry?> FindEpisodeAsync(EpisodeInfoLookup lookup, CancellationToken cancellationToken)
    {
        var catalog = await GetCatalogAsync(cancellationToken).ConfigureAwait(false);
        return catalog.FirstOrDefault(entry => entry.IsEpisode && entry.MatchesEpisode(lookup));
    }

    public async Task<StreamarrResolveResponse?> ResolveStreamAsync(string entryId, CancellationToken cancellationToken)
    {
        var snapshot = GetConfigurationSnapshot();
        EnsureConfigurationSnapshot(snapshot);

        try
        {
            using var client = CreateClient(snapshot);
            var response = await client.GetFromJsonAsync<StreamarrResolveResponse>($"play/{Uri.EscapeDataString(entryId)}?format=json", cancellationToken: cancellationToken)
                .ConfigureAwait(false);
            return response;
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to resolve stream for entry {EntryId}", entryId);
            return null;
        }
    }
}
