using System;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text.RegularExpressions;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Entities.TV;
using MediaBrowser.Model.Entities;
using MediaBrowser.Model.Providers;

namespace Streamarr.Plugin;

public sealed class StreamarrCatalogEntry
{
    private const string ProviderKeyValue = "Streamarr";

    private static readonly Regex EpisodeIdRegex = new(@"^dizibox:(?<slug>[^:]+):s(?<_season>\d+)e(?<_episode>\d+)$", RegexOptions.IgnoreCase | RegexOptions.Compiled | RegexOptions.CultureInvariant);
    private static readonly Regex SeasonSubtitleRegex = new(@"(?:\b(?:sezon|season)\b)\s*(?<num>\d+)", RegexOptions.IgnoreCase | RegexOptions.Compiled | RegexOptions.CultureInvariant);
    private static readonly Regex EpisodeSubtitleRegex = new(@"(?:\b(?:b\u00F6l\u00FCm|bolum|episode)\b)\s*(?<num>\d+)", RegexOptions.IgnoreCase | RegexOptions.Compiled | RegexOptions.CultureInvariant);

    public string Id { get; set; } = string.Empty;
    public string Site { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string Subtitle { get; set; } = string.Empty;
    public string Url { get; set; } = string.Empty;
    public int Year { get; set; }
    public string Type { get; set; } = string.Empty;
    public string? OriginalTitle { get; set; }
    public string? Poster { get; set; }
    public string? Backdrop { get; set; }
    public string? Overview { get; set; }
    public int? TmdbId { get; set; }

    public bool IsMovie => string.Equals(Type, "movie", StringComparison.OrdinalIgnoreCase);
    public bool IsEpisode => string.Equals(Type, "episode", StringComparison.OrdinalIgnoreCase);

    public string SeriesSlug
    {
        get
        {
            if (!IsEpisode)
            {
                return string.Empty;
            }

            var match = EpisodeIdRegex.Match(Id);
            if (match.Success)
            {
                return match.Groups["slug"].Value;
            }

            return Id;
        }
    }

    public int? SeasonNumber
    {
        get
        {
            if (!IsEpisode)
            {
                return null;
            }

            var match = EpisodeIdRegex.Match(Id);
            if (match.Success && int.TryParse(match.Groups["_season"].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var season))
            {
                return season;
            }

            return ParseNumberFromSubtitle(SeasonSubtitleRegex);
        }
    }

    public int? EpisodeNumber
    {
        get
        {
            if (!IsEpisode)
            {
                return null;
            }

            var match = EpisodeIdRegex.Match(Id);
            if (match.Success && int.TryParse(match.Groups["_episode"].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var episode))
            {
                return episode;
            }

            return ParseNumberFromSubtitle(EpisodeSubtitleRegex);
        }
    }

    private int? ParseNumberFromSubtitle(Regex pattern)
    {
        if (string.IsNullOrWhiteSpace(Subtitle))
        {
            return null;
        }

        var match = pattern.Match(Subtitle);
        if (!match.Success)
        {
            return null;
        }

        return int.TryParse(match.Groups["num"].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var number)
            ? number
            : null;
    }

    private bool MatchesEpisodeNumbers(int? season, int? episode)
    {
        if (season.HasValue && SeasonNumber.HasValue && SeasonNumber.Value != season.Value)
        {
            return false;
        }

        if (episode.HasValue && EpisodeNumber.HasValue && EpisodeNumber.Value != episode.Value)
        {
            return false;
        }

        return true;
    }

    private static string? ExtractSeriesSlug(string? providerId)
    {
        if (string.IsNullOrWhiteSpace(providerId))
        {
            return null;
        }

        var parts = providerId.Split(':', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length < 2)
        {
            return null;
        }

        return string.Equals(parts[0], "dizibox", StringComparison.OrdinalIgnoreCase) ? parts[1] : null;
    }

    public static string ProviderKey => ProviderKeyValue;

    public bool MatchesMovie(MovieInfoLookup lookup)
    {
        if (!IsMovie)
        {
            return false;
        }

        if (!string.IsNullOrWhiteSpace(lookup.ProviderId)
            && string.Equals(lookup.ProviderId, Id, StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        return TitleMatches(lookup.Name) || TitleMatches(lookup.OriginalTitle);
    }

    public bool MatchesSeries(SeriesInfoLookup lookup)
    {
        if (!IsEpisode)
        {
            return false;
        }

        if (!string.IsNullOrWhiteSpace(lookup.ProviderId))
        {
            if (string.Equals(lookup.ProviderId, Id, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            var slug = ExtractSeriesSlug(lookup.ProviderId);
            if (!string.IsNullOrEmpty(slug) && string.Equals(slug, SeriesSlug, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return TitleMatches(lookup.Name) || TitleMatches(lookup.OriginalTitle);
    }

    public bool MatchesEpisode(EpisodeInfoLookup lookup)
    {
        if (!IsEpisode)
        {
            return false;
        }

        if (!string.IsNullOrWhiteSpace(lookup.ProviderId))
        {
            if (string.Equals(lookup.ProviderId, Id, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            var slug = ExtractSeriesSlug(lookup.ProviderId);
            if (!string.IsNullOrEmpty(slug) && string.Equals(slug, SeriesSlug, StringComparison.OrdinalIgnoreCase))
            {
                return MatchesEpisodeNumbers(lookup.SeasonNumber, lookup.EpisodeNumber);
            }
        }

        if (!string.IsNullOrWhiteSpace(lookup.SeriesProviderId))
        {
            var slug = ExtractSeriesSlug(lookup.SeriesProviderId);
            if (!string.IsNullOrEmpty(slug) && string.Equals(slug, SeriesSlug, StringComparison.OrdinalIgnoreCase))
            {
                return MatchesEpisodeNumbers(lookup.SeasonNumber, lookup.EpisodeNumber);
            }
        }

        if (!string.IsNullOrWhiteSpace(lookup.SeriesName) && !TitleMatches(lookup.SeriesName))
        {
            return false;
        }

        return MatchesEpisodeNumbers(lookup.SeasonNumber, lookup.EpisodeNumber);
    }

    private bool TitleMatches(string? query)
    {
        if (string.IsNullOrWhiteSpace(query))
        {
            return false;
        }

        if (string.Equals(Title, query, StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        if (!string.IsNullOrWhiteSpace(OriginalTitle) && string.Equals(OriginalTitle, query, StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        return Title.Contains(query, StringComparison.OrdinalIgnoreCase)
            || (!string.IsNullOrWhiteSpace(OriginalTitle) && OriginalTitle.Contains(query, StringComparison.OrdinalIgnoreCase));
    }

    public RemoteSearchResult ToMovieSearchResult()
    {
        return new RemoteSearchResult
        {
            Name = Title,
            ImageUrl = Poster,
            Overview = Overview,
            SearchProviderName = "Streamarr",
            ProductionYear = Year == 0 ? null : Year,
            ProviderIds = new Dictionary<string, string>
            {
                { ProviderKey, Id }
            }
        };
    }

    public RemoteSearchResult ToSeriesSearchResult()
    {
        return new RemoteSearchResult
        {
            Name = Title,
            ImageUrl = Poster,
            Overview = Overview,
            SearchProviderName = "Streamarr",
            ProviderIds = new Dictionary<string, string>
            {
                { ProviderKey, $"dizibox:{SeriesSlug}" }
            }
        };
    }

    public RemoteSearchResult ToEpisodeSearchResult()
    {
        return new RemoteSearchResult
        {
            Name = Subtitle ?? Title,
            SearchProviderName = "Streamarr",
            ProviderIds = new Dictionary<string, string>
            {
                { ProviderKey, Id }
            }
        };
    }

    public Movie ToMovie()
    {
        var movie = new Movie
        {
            Name = Title,
            OriginalTitle = OriginalTitle ?? Title,
            Overview = Overview,
            ProductionYear = Year == 0 ? null : Year,
            ProviderIds = new Dictionary<string, string> { { ProviderKey, Id } }
        };

        if (!string.IsNullOrWhiteSpace(Poster))
        {
            movie.AddImage(new ItemImageInfo { Path = Poster, Type = ImageType.Primary });
        }

        if (!string.IsNullOrWhiteSpace(Backdrop))
        {
            movie.AddImage(new ItemImageInfo { Path = Backdrop, Type = ImageType.Backdrop });
        }

        return movie;
    }

    public Series ToSeries()
    {
        var series = new Series
        {
            Name = Title,
            OriginalTitle = OriginalTitle ?? Title,
            Overview = Overview,
            ProviderIds = new Dictionary<string, string>
            {
                { ProviderKey, $"dizibox:{SeriesSlug}" }
            }
        };

        if (!string.IsNullOrWhiteSpace(Poster))
        {
            series.AddImage(new ItemImageInfo { Path = Poster, Type = ImageType.Primary });
        }

        if (!string.IsNullOrWhiteSpace(Backdrop))
        {
            series.AddImage(new ItemImageInfo { Path = Backdrop, Type = ImageType.Backdrop });
        }

        return series;
    }

    public Episode ToEpisode()
    {
        var episode = new Episode
        {
            Name = Subtitle ?? Title,
            Overview = Overview,
            SeriesName = Title,
            IndexNumber = EpisodeNumber,
            ParentIndexNumber = SeasonNumber,
            ProviderIds = new Dictionary<string, string> { { ProviderKey, Id } }
        };

        if (!string.IsNullOrWhiteSpace(Poster))
        {
            episode.AddImage(new ItemImageInfo { Path = Poster, Type = ImageType.Primary });
        }

        return episode;
    }
}

public readonly record struct MovieInfoLookup(string? Name, string? OriginalTitle, string? ProviderId);
public readonly record struct SeriesInfoLookup(string? Name, string? OriginalTitle, string? ProviderId);
public readonly record struct EpisodeInfoLookup(string? SeriesName, int? SeasonNumber, int? EpisodeNumber, string? ProviderId, string? SeriesProviderId);

public sealed class StreamarrResolveResponse
{
    public string? Token { get; set; }
    public string? StreamUrl { get; set; }
    public string? ExpiresAt { get; set; }
}
