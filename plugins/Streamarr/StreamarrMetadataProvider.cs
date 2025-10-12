using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Entities.TV;
using MediaBrowser.Controller.Providers;
using MediaBrowser.Model.Providers;
using Microsoft.Extensions.Logging;

namespace Streamarr.Plugin;

internal static class StreamarrMetadataClientFactory
{
    private static StreamarrApiClient? _instance;
    private static readonly object SyncRoot = new();

    public static StreamarrApiClient GetClient(IHttpClientFactory httpClientFactory, ILoggerFactory loggerFactory)
    {
        lock (SyncRoot)
        {
            return _instance ??= new StreamarrApiClient(httpClientFactory, loggerFactory.CreateLogger<StreamarrApiClient>());
        }
    }
}

internal static class StreamarrMetadataUtilities
{
    public static bool TryGetProviderId(IDictionary<string, string>? providerIds, out string providerId)
    {
        providerId = string.Empty;
        if (providerIds is null)
        {
            return false;
        }

        if (providerIds.TryGetValue(StreamarrCatalogEntry.ProviderKey, out var value) && !string.IsNullOrWhiteSpace(value))
        {
            providerId = value.Trim();
            return true;
        }

        return false;
    }

    public static string? GetProviderId(IDictionary<string, string>? providerIds)
    {
        return TryGetProviderId(providerIds, out var value) ? value : null;
    }

    public static string? GetSeriesProviderId(IDictionary<string, string>? providerIds)
    {
        if (providerIds is null)
        {
            return null;
        }

        if (providerIds.TryGetValue(StreamarrCatalogEntry.ProviderKey, out var value) && !string.IsNullOrWhiteSpace(value))
        {
            return value.Trim();
        }

        return null;
    }

    public static string? ExtractSeriesSlug(string providerId)
    {
        if (string.IsNullOrWhiteSpace(providerId))
        {
            return null;
        }

        var parts = providerId.Trim().Split(':', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length < 2)
        {
            return null;
        }

        return string.Equals(parts[0], "dizibox", StringComparison.OrdinalIgnoreCase) ? parts[1] : null;
    }
}

public class StreamarrMovieMetadataProvider : IRemoteMetadataProvider<Movie, MovieInfo>
{
    private readonly StreamarrApiClient _apiClient;
    private readonly ILogger<StreamarrMovieMetadataProvider> _logger;

    public StreamarrMovieMetadataProvider(IHttpClientFactory httpClientFactory, ILoggerFactory loggerFactory)
    {
        _apiClient = StreamarrMetadataClientFactory.GetClient(httpClientFactory, loggerFactory);
        _logger = loggerFactory.CreateLogger<StreamarrMovieMetadataProvider>();
    }

    public string Name => "Streamarr";

    public async Task<IEnumerable<RemoteSearchResult>> GetSearchResults(MovieInfo searchInfo, CancellationToken cancellationToken)
    {
        try
        {
            var entry = await ResolveMovieEntryAsync(searchInfo, cancellationToken).ConfigureAwait(false);
            if (entry is null)
            {
                return Array.Empty<RemoteSearchResult>();
            }

            return new[] { entry.ToMovieSearchResult() };
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Streamarr movie search failed for {Name}", searchInfo.Name);
            return Array.Empty<RemoteSearchResult>();
        }
    }

    public async Task<MetadataResult<Movie>> GetMetadata(MovieInfo info, CancellationToken cancellationToken)
    {
        var result = new MetadataResult<Movie> { HasMetadata = false };

        try
        {
            var entry = await ResolveMovieEntryAsync(info, cancellationToken).ConfigureAwait(false);
            if (entry is null)
            {
                return result;
            }

            result.Item = entry.ToMovie();
            result.Provider = Name;
            result.HasMetadata = true;
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Streamarr movie metadata failed for {Name}", info.Name);
        }

        return result;
    }

    public Task<HttpResponseMessage> GetImageResponse(string url, CancellationToken cancellationToken)
        => Task.FromResult(new HttpResponseMessage(HttpStatusCode.NotFound));

    private async Task<StreamarrCatalogEntry?> ResolveMovieEntryAsync(MovieInfo info, CancellationToken cancellationToken)
    {
        string? providerId = StreamarrMetadataUtilities.GetProviderId(info.ProviderIds);
        if (!string.IsNullOrWhiteSpace(providerId))
        {
            var entryById = await _apiClient.GetEntryByIdAsync(providerId, cancellationToken).ConfigureAwait(false);
            if (entryById is not null)
            {
                return entryById;
            }
        }

        var lookup = new MovieInfoLookup(info.Name, info.OriginalTitle, providerId);
        return await _apiClient.FindMovieAsync(lookup, cancellationToken).ConfigureAwait(false);
    }
}

public class StreamarrSeriesMetadataProvider : IRemoteMetadataProvider<Series, SeriesInfo>
{
    private readonly StreamarrApiClient _apiClient;
    private readonly ILogger<StreamarrSeriesMetadataProvider> _logger;

    public StreamarrSeriesMetadataProvider(IHttpClientFactory httpClientFactory, ILoggerFactory loggerFactory)
    {
        _apiClient = StreamarrMetadataClientFactory.GetClient(httpClientFactory, loggerFactory);
        _logger = loggerFactory.CreateLogger<StreamarrSeriesMetadataProvider>();
    }

    public string Name => "Streamarr";

    public async Task<IEnumerable<RemoteSearchResult>> GetSearchResults(SeriesInfo searchInfo, CancellationToken cancellationToken)
    {
        try
        {
            var results = new List<RemoteSearchResult>();

            var providerId = StreamarrMetadataUtilities.GetProviderId(searchInfo.ProviderIds);
            if (!string.IsNullOrWhiteSpace(providerId))
            {
                var entry = await GetSeriesEntryForProviderAsync(providerId, cancellationToken).ConfigureAwait(false);
                if (entry is not null)
                {
                    results.Add(entry.ToSeriesSearchResult());
                }
            }

            if (results.Count == 0)
            {
                var lookup = new SeriesInfoLookup(searchInfo.Name, searchInfo.OriginalTitle, providerId);
                var matches = await _apiClient.FindSeriesMatchesAsync(lookup, cancellationToken).ConfigureAwait(false);
                foreach (var match in matches)
                {
                    if (match.IsEpisode)
                    {
                        results.Add(match.ToSeriesSearchResult());
                    }
                }

                if (results.Count > 1)
                {
                    results = results
                        .GroupBy(result => result.ProviderIds.TryGetValue(StreamarrCatalogEntry.ProviderKey, out var id) ? id : string.Empty, StringComparer.OrdinalIgnoreCase)
                        .Select(group => group.First())
                        .ToList();
                }
            }

            return results;
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Streamarr series search failed for {Name}", searchInfo.Name);
            return Array.Empty<RemoteSearchResult>();
        }
    }

    public async Task<MetadataResult<Series>> GetMetadata(SeriesInfo info, CancellationToken cancellationToken)
    {
        var result = new MetadataResult<Series> { HasMetadata = false };

        try
        {
            var entry = await ResolveSeriesEntryAsync(info, cancellationToken).ConfigureAwait(false);
            if (entry is null)
            {
                return result;
            }

            result.Item = entry.ToSeries();
            result.Provider = Name;
            result.HasMetadata = true;
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Streamarr series metadata failed for {Name}", info.Name);
        }

        return result;
    }

    public Task<HttpResponseMessage> GetImageResponse(string url, CancellationToken cancellationToken)
        => Task.FromResult(new HttpResponseMessage(HttpStatusCode.NotFound));

    private async Task<StreamarrCatalogEntry?> GetSeriesEntryForProviderAsync(string providerId, CancellationToken cancellationToken)
    {
        var entry = await _apiClient.GetEntryByIdAsync(providerId, cancellationToken).ConfigureAwait(false);
        if (entry is not null)
        {
            return entry;
        }

        var slug = StreamarrMetadataUtilities.ExtractSeriesSlug(providerId);
        if (string.IsNullOrWhiteSpace(slug))
        {
            return null;
        }

        var catalog = await _apiClient.GetCatalogAsync(cancellationToken).ConfigureAwait(false);
        return catalog.FirstOrDefault(item => item.IsEpisode && string.Equals(item.SeriesSlug, slug, StringComparison.OrdinalIgnoreCase));
    }

    private async Task<StreamarrCatalogEntry?> ResolveSeriesEntryAsync(SeriesInfo info, CancellationToken cancellationToken)
    {
        var providerId = StreamarrMetadataUtilities.GetProviderId(info.ProviderIds);
        if (!string.IsNullOrWhiteSpace(providerId))
        {
            var entry = await GetSeriesEntryForProviderAsync(providerId, cancellationToken).ConfigureAwait(false);
            if (entry is not null)
            {
                return entry;
            }
        }

        var lookup = new SeriesInfoLookup(info.Name, info.OriginalTitle, providerId);
        var matches = await _apiClient.FindSeriesMatchesAsync(lookup, cancellationToken).ConfigureAwait(false);
        return matches.FirstOrDefault();
    }
}

public class StreamarrEpisodeMetadataProvider : IRemoteMetadataProvider<Episode, EpisodeInfo>
{
    private readonly StreamarrApiClient _apiClient;
    private readonly ILogger<StreamarrEpisodeMetadataProvider> _logger;

    public StreamarrEpisodeMetadataProvider(IHttpClientFactory httpClientFactory, ILoggerFactory loggerFactory)
    {
        _apiClient = StreamarrMetadataClientFactory.GetClient(httpClientFactory, loggerFactory);
        _logger = loggerFactory.CreateLogger<StreamarrEpisodeMetadataProvider>();
    }

    public string Name => "Streamarr";

    public async Task<IEnumerable<RemoteSearchResult>> GetSearchResults(EpisodeInfo searchInfo, CancellationToken cancellationToken)
    {
        try
        {
            var entry = await ResolveEpisodeEntryAsync(searchInfo, cancellationToken).ConfigureAwait(false);
            if (entry is null)
            {
                return Array.Empty<RemoteSearchResult>();
            }

            return new[] { entry.ToEpisodeSearchResult() };
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Streamarr episode search failed for {Episode} S{Season}E{Episode}", searchInfo.Name, searchInfo.ParentIndexNumber, searchInfo.IndexNumber);
            return Array.Empty<RemoteSearchResult>();
        }
    }

    public async Task<MetadataResult<Episode>> GetMetadata(EpisodeInfo info, CancellationToken cancellationToken)
    {
        var result = new MetadataResult<Episode> { HasMetadata = false };

        try
        {
            var entry = await ResolveEpisodeEntryAsync(info, cancellationToken).ConfigureAwait(false);
            if (entry is null)
            {
                return result;
            }

            result.Item = entry.ToEpisode();
            result.Provider = Name;
            result.HasMetadata = true;
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Streamarr episode metadata failed for {Episode} S{Season}E{Episode}", info.Name, info.ParentIndexNumber, info.IndexNumber);
        }

        return result;
    }

    public Task<HttpResponseMessage> GetImageResponse(string url, CancellationToken cancellationToken)
        => Task.FromResult(new HttpResponseMessage(HttpStatusCode.NotFound));

    private async Task<StreamarrCatalogEntry?> ResolveEpisodeEntryAsync(EpisodeInfo info, CancellationToken cancellationToken)
    {
        var providerId = StreamarrMetadataUtilities.GetProviderId(info.ProviderIds);
        if (!string.IsNullOrWhiteSpace(providerId))
        {
            var byId = await _apiClient.GetEntryByIdAsync(providerId, cancellationToken).ConfigureAwait(false);
            if (byId is not null)
            {
                return byId;
            }

            var slug = StreamarrMetadataUtilities.ExtractSeriesSlug(providerId);
            if (!string.IsNullOrWhiteSpace(slug))
            {
                var catalog = await _apiClient.GetCatalogAsync(cancellationToken).ConfigureAwait(false);
                var match = catalog.FirstOrDefault(item =>
                    item.IsEpisode
                    && string.Equals(item.SeriesSlug, slug, StringComparison.OrdinalIgnoreCase)
                    && (!info.ParentIndexNumber.HasValue || item.SeasonNumber == info.ParentIndexNumber)
                    && (!info.IndexNumber.HasValue || item.EpisodeNumber == info.IndexNumber));

                if (match is not null)
                {
                    return match;
                }
            }
        }

        string? seriesProviderId = null;
        var providerIdsProperty = info.GetType().GetProperty("SeriesProviderIds");
        if (providerIdsProperty?.GetValue(info) is IDictionary<string, string> seriesIds)
        {
            seriesProviderId = StreamarrMetadataUtilities.GetSeriesProviderId(seriesIds);
        }

        var lookup = new EpisodeInfoLookup(null, info.ParentIndexNumber, info.IndexNumber, providerId, seriesProviderId);
        return await _apiClient.FindEpisodeAsync(lookup, cancellationToken).ConfigureAwait(false);
    }
}
