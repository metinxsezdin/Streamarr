using System;
using System.Linq;
using MediaBrowser.Common.Plugins;
using MediaBrowser.Model.Plugins;

var type = typeof(BasePlugin<BasePluginConfiguration>);

Console.WriteLine("Properties:");
foreach (var prop in type.GetProperties())
{
    Console.WriteLine($"- {prop.Name} ({prop.PropertyType.Name})");
}

Console.WriteLine("\nMethods:");
foreach (var method in type.GetMethods())
{
    if (method.DeclaringType == type)
    {
        Console.WriteLine($"- {method.Name}");
    }
}
