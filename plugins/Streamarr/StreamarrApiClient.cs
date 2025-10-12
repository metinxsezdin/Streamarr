using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;

namespace Streamarr.Plugin;

internal sealed class StreamarrApiClient
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly ILogger _logger;

    private readonly object _cacheLock = new();
    private IReadOnlyList<StreamarrCatalogEntry>? _catalogCache;
    private Dictionary<string, StreamarrCatalogEntry>? _catalogIndex;
    private DateTime _catalogCacheTimestamp;
    private ResolverClientConfig? _lastConfig;
    private readonly HashSet<string> _enabledProviders = new(StringComparer.OrdinalIgnoreCase);

    private static readonly string[] DefaultProviders = { "dizibox", "hdfilm" };
    private readonly record struct ResolverClientConfig(string BaseUrl, string? ApiKey, int CacheMinutes, bool DisableCache, string[] Providers);

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

    private ResolverClientConfig GetConfigurationSnapshot()
    {
        var configuration = StreamarrPlugin.Instance?.Configuration;
        var resolverBase = NormalizeResolverBase(configuration?.ResolverBaseUrl);
        var apiKey = string.IsNullOrWhiteSpace(configuration?.ApiKey) ? null : configuration!.ApiKey!.Trim();
        var cacheMinutes = configuration?.CatalogCacheMinutes ?? 10;
        if (cacheMinutes < 0)
        {
            cacheMinutes = 0;
        }

        var providers = NormalizeProviders(configuration?.EnabledProviders);

        return new ResolverClientConfig(
            resolverBase,
            string.IsNullOrEmpty(apiKey) ? null : apiKey,
            cacheMinutes,
            configuration?.DisableCatalogCache ?? false,
            providers);
    }

    private static string[] NormalizeProviders(IEnumerable<string>? providers)
    {
        if (providers is null)
        {
            return DefaultProviders.ToArray();
        }

        var normalized = providers
            .Select(p => (p ?? string.Empty).Trim())
            .Where(p => !string.IsNullOrWhiteSpace(p))
            .Select(p => p.ToLowerInvariant())
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();

        return normalized.Length > 0 ? normalized : DefaultProviders.ToArray();
    }

    private IReadOnlyList<StreamarrCatalogEntry> ApplyProviderFilter(IEnumerable<StreamarrCatalogEntry> entries)
    {
        if (_enabledProviders.Count == 0)
        {
            return Array.Empty<StreamarrCatalogEntry>();
        }

        var filtered = entries
            .Where(entry => !string.IsNullOrWhiteSpace(entry.Site) && _enabledProviders.Contains(entry.Site))
            .ToArray();

        return filtered.Length > 0 ? filtered : Array.Empty<StreamarrCatalogEntry>();
    }

    private void EnsureConfigurationSnapshot(ResolverClientConfig snapshot)
    {
        if (_lastConfig is null || !_lastConfig.Value.Equals(snapshot))
        {
            lock (_cacheLock)
            {
                _catalogCache = null;
                _catalogIndex = null;
                _catalogCacheTimestamp = DateTime.MinValue;
                _enabledProviders.Clear();
                foreach (var provider in snapshot.Providers)
                {
                    _enabledProviders.Add(provider);
                }
            }

            _lastConfig = snapshot;
        }
    }

    private IReadOnlyList<StreamarrCatalogEntry> SetCatalogCache(IReadOnlyList<StreamarrCatalogEntry> entries)
    {
        var filtered = ApplyProviderFilter(entries);
        lock (_cacheLock)
        {
            _catalogCache = filtered;
            _catalogCacheTimestamp = DateTime.UtcNow;
            _catalogIndex = BuildCatalogIndex(filtered);
        }
        return filtered;
    }

    private IReadOnlyList<StreamarrCatalogEntry> SetCatalogIndex(IReadOnlyList<StreamarrCatalogEntry> entries)
    {
        var filtered = ApplyProviderFilter(entries);
        lock (_cacheLock)
        {
            _catalogIndex = BuildCatalogIndex(filtered);
        }
        return filtered;
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

    private static TimeSpan GetCatalogCacheDuration(ResolverClientConfig snapshot)
    {
        if (snapshot.DisableCache)
        {
            return TimeSpan.Zero;
        }

        var minutes = Math.Clamp(snapshot.CacheMinutes, 1, 1440);
        return TimeSpan.FromMinutes(minutes);
    }

    private HttpClient CreateClient(ResolverClientConfig snapshot)
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
        var cacheDuration = GetCatalogCacheDuration(snapshot);

        IReadOnlyList<StreamarrCatalogEntry>? cached;
        lock (_cacheLock)
        {
            if (cacheDuration > TimeSpan.Zero
                && _catalogCache is not null
                && DateTime.UtcNow - _catalogCacheTimestamp < cacheDuration)
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
                return cacheDuration > TimeSpan.Zero
                    ? SetCatalogCache(entries)
                    : SetCatalogIndex(entries);
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

        if (cacheDuration > TimeSpan.Zero)
        {
            IReadOnlyList<StreamarrCatalogEntry>? fallback;
            lock (_cacheLock)
            {
                fallback = _catalogCache;
            }

            if (fallback is not null)
            {
                EnsureCatalogIndex();
                return ApplyProviderFilter(fallback);
            }
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

    public async Task<StreamarrHealthStatus> GetHealthAsync(CancellationToken cancellationToken)
    {
        var snapshot = GetConfigurationSnapshot();
        EnsureConfigurationSnapshot(snapshot);

        try
        {
            using var client = CreateClient(snapshot);
            var response = await client.GetAsync("health", cancellationToken).ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                return new StreamarrHealthStatus
                {
                    IsHealthy = false,
                    Summary = $"HTTP {(int)response.StatusCode}",
                    ResolverBaseUrl = snapshot.BaseUrl
                };
            }

            var payload = await response.Content.ReadFromJsonAsync<ResolverHealthPayload>(cancellationToken: cancellationToken).ConfigureAwait(false);
            return new StreamarrHealthStatus
            {
                IsHealthy = string.Equals(payload?.Status, "ok", StringComparison.OrdinalIgnoreCase),
                Summary = payload?.Status ?? "unknown",
                CacheSize = payload?.CacheSize,
                ResolverBaseUrl = snapshot.BaseUrl
            };
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to retrieve resolver health information");
            return new StreamarrHealthStatus
            {
                IsHealthy = false,
                Summary = ex.Message,
                ResolverBaseUrl = snapshot.BaseUrl
            };
        }
    }

    private sealed class ResolverHealthPayload
    {
        [JsonPropertyName("status")]
        public string? Status { get; set; }

        [JsonPropertyName("cache_size")]
        public int? CacheSize { get; set; }
    }
}

public sealed class StreamarrHealthStatus
{
    public bool IsHealthy { get; init; }

    public string Summary { get; init; } = string.Empty;

    public int? CacheSize { get; init; }

    public string? ResolverBaseUrl { get; init; }
}
