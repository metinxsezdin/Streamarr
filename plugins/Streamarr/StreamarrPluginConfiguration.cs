using MediaBrowser.Model.Plugins;

namespace Streamarr.Plugin;

public class StreamarrPluginConfiguration : BasePluginConfiguration
{
    public string ResolverBaseUrl { get; set; } = "http://127.0.0.1:5055";

    public string ApiKey { get; set; } = string.Empty;

    public int CatalogCacheMinutes { get; set; } = 10;

    public bool DisableCatalogCache { get; set; }

    public string[] EnabledProviders { get; set; } = { "dizibox", "hdfilm" };
}
