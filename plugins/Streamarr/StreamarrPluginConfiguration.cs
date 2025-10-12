using MediaBrowser.Model.Plugins;

namespace Streamarr.Plugin;

public class StreamarrPluginConfiguration : BasePluginConfiguration
{
    public string ResolverBaseUrl { get; set; } = "http://127.0.0.1:5055";

    public string ApiKey { get; set; } = string.Empty;
}
