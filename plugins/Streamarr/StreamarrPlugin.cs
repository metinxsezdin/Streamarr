using MediaBrowser.Common.Configuration;
using MediaBrowser.Common.Plugins;
using MediaBrowser.Model.Plugins;
using MediaBrowser.Model.Serialization;

namespace Streamarr.Plugin;

public class StreamarrPlugin : BasePlugin<StreamarrPluginConfiguration>, IHasWebPages
{
    public static StreamarrPlugin? Instance { get; private set; }

    public override string Name => "Streamarr";

    public override Guid Id { get; } = new("68C71F7D-A14E-4F21-9E10-7C02F51AE7B0");

    public StreamarrPlugin(IApplicationPaths applicationPaths, IXmlSerializer xmlSerializer) : base(applicationPaths, xmlSerializer)
    {
        Instance = this;
    }

    public IEnumerable<PluginPageInfo> GetPages()
    {
        yield return new PluginPageInfo
        {
            Name = "streamarr",
            DisplayName = "Streamarr",
            EmbeddedResourcePath = $"{GetType().Namespace}.Configuration.configPage.html"
        };
    }
}
