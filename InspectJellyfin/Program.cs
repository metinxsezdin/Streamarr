using System;
using System.Linq;
using MediaBrowser.Common.Plugins;
using MediaBrowser.Model.Plugins;

Console.WriteLine("BasePlugin properties:");
foreach (var prop in typeof(BasePlugin<BasePluginConfiguration>).GetProperties())
{
    Console.WriteLine($"- {prop.Name} ({prop.PropertyType.Name})");
}

Console.WriteLine("\nInterfaces on BasePlugin:");
foreach (var iface in typeof(BasePlugin<BasePluginConfiguration>).GetInterfaces())
{
    Console.WriteLine($"- {iface.FullName}");
}

var ifaceType = typeof(BasePlugin<BasePluginConfiguration>).Assembly
    .GetTypes()
    .FirstOrDefault(t => t.Name == "IHasWebConfiguration");

if (ifaceType is not null)
{
    Console.WriteLine("\nIHasWebConfiguration members:");
    foreach (var method in ifaceType.GetMethods())
    {
        Console.WriteLine($"- {method.Name} : {method.ReturnType.Name}");
    }
}
else
{
    Console.WriteLine("\nIHasWebConfiguration not found.");
}
