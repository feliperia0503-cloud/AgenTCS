"""Pack de DESTINO 'csharp' (C# 12 / .NET 8). Verificación con `dotnet build` de un proyecto de consola
generado por la plataforma (sin paquetes NuGet externos) que excluye `Infrastructure/`."""
from __future__ import annotations

from pathlib import Path

from copilot.contracts import BuildResult, Case, CaseOutput, NeutralType, PackInfo, PackRole, TypeKind
from copilot.engine.sandbox import run_cmd

from ..base import COMMON_RULES, BaseTarget, read_actual, to_build, write_cases

PROJECT = "AgenTCSVerify.csproj"
HARNESS = "AgenTCSHarness.cs"
OUT = "out"

CONVENTIONS = f"""Destino: C# 12 sobre .NET 8, solo la biblioteca estándar en el núcleo.
- Punto de entrada OBLIGATORIO: `App/Entry.cs` con
  `namespace App; public static class Entry {{ public static object? Run(IDictionary<string, object?> input) }}`.
  En `input` los decimales llegan como string (usa `decimal.Parse(s, CultureInfo.InvariantCulture)`) y los
  enteros como long. Devuelve `Dictionary<string, object?>` con los campos de salida, o
  `List<Dictionary<string, object?>>` si output_is_list. Decimales como `decimal` con la escala exacta.
- Carpetas/espacios de nombres: `Domain` (records, reglas), `Application` (caso de uso),
  `Infrastructure` (adaptadores del framework, NO se compila en la verificación).
- `decimal` con `Math.Round(x, n, MidpointRounding.AwayFromZero)` o truncamiento explícito
  (`Math.Truncate(x * 10^n) / 10^n`) según el modo del tipo neutral. OJO: Math.Round por defecto es HALF_EVEN.
- Nullable habilitado. No agregues archivos .csproj, .sln ni Program.cs.
{COMMON_RULES}"""

CSPROJ = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <AssemblyName>AgenTCSVerify</AssemblyName>
    <InvariantGlobalization>true</InvariantGlobalization>
    <StartupObject>AgenTCSHarness</StartupObject>
  </PropertyGroup>
  <ItemGroup>
    <Compile Remove="**/Infrastructure/**;**/infrastructure/**;bin/**;obj/**;out/**" />
  </ItemGroup>
</Project>
"""

HARNESS_SOURCE = r'''using System.Collections;
using System.Globalization;
using System.Text;
using System.Text.Json;

public static class AgenTCSHarness
{
    public static int Main(string[] args)
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(args[0]));
        var sb = new StringBuilder("[");
        var first = true;
        foreach (var c in doc.RootElement.EnumerateArray())
        {
            if (!first) sb.Append(',');
            first = false;
            sb.Append("{\"id\":");
            Str(sb, c.GetProperty("id").GetString());
            try
            {
                var input = (Dictionary<string, object?>)Conv(c.GetProperty("input"))!;
                var res = App.Entry.Run(input);
                if (res is IDictionary d && d.Contains("error") && d["error"] is IDictionary e)
                {
                    sb.Append(",\"error\":{\"code\":");
                    Str(sb, Convert.ToString(e["code"], CultureInfo.InvariantCulture) ?? "");
                    sb.Append(",\"message\":");
                    Str(sb, e.Contains("message") ? Convert.ToString(e["message"], CultureInfo.InvariantCulture) ?? "" : "");
                    sb.Append('}');
                }
                else
                {
                    sb.Append(",\"output\":");
                    Write(sb, res);
                }
            }
            catch (Exception ex)
            {
                sb.Append(",\"error\":{\"code\":\"EXEC_ERROR\",\"message\":");
                Str(sb, ex.GetType().Name + ": " + ex.Message);
                sb.Append('}');
            }
            sb.Append('}');
        }
        File.WriteAllText(args[1], sb.Append(']').ToString());
        return 0;
    }

    static object? Conv(JsonElement e) => e.ValueKind switch
    {
        JsonValueKind.Object => e.EnumerateObject().ToDictionary(p => p.Name, p => Conv(p.Value)),
        JsonValueKind.Array => e.EnumerateArray().Select(Conv).ToList(),
        JsonValueKind.String => e.GetString(),
        JsonValueKind.Number => e.TryGetInt64(out var l) ? l : e.GetDecimal(),
        JsonValueKind.True => true,
        JsonValueKind.False => false,
        _ => null,
    };

    static void Write(StringBuilder sb, object? v)
    {
        switch (v)
        {
            case null: sb.Append("null"); break;
            case string s: Str(sb, s); break;
            case bool b: sb.Append(b ? "true" : "false"); break;
            case decimal m: Str(sb, m.ToString(CultureInfo.InvariantCulture)); break;
            case double or float: Str(sb, Convert.ToString(v, CultureInfo.InvariantCulture)); break;
            case int or long or short or byte or uint or ulong: sb.Append(Convert.ToString(v, CultureInfo.InvariantCulture)); break;
            case IDictionary dict:
                sb.Append('{');
                var f = true;
                foreach (DictionaryEntry kv in dict)
                {
                    if (!f) sb.Append(',');
                    f = false;
                    Str(sb, Convert.ToString(kv.Key, CultureInfo.InvariantCulture));
                    sb.Append(':');
                    Write(sb, kv.Value);
                }
                sb.Append('}');
                break;
            case IEnumerable list:
                sb.Append('[');
                var g = true;
                foreach (var o in list) { if (!g) sb.Append(','); g = false; Write(sb, o); }
                sb.Append(']');
                break;
            default:
                var props = v.GetType().GetProperties().Where(p => p.GetIndexParameters().Length == 0);
                Write(sb, props.ToDictionary(p => p.Name, p => p.GetValue(v)));
                break;
        }
    }

    static void Str(StringBuilder sb, string? s) => sb.Append(JsonSerializer.Serialize(s ?? ""));
}
'''

_TYPES = {TypeKind.DECIMAL: "decimal", TypeKind.INTEGER: "long", TypeKind.FLOAT: "double", TypeKind.STRING: "string",
          TypeKind.DATE: "DateOnly", TypeKind.DATETIME: "DateTime", TypeKind.BOOLEAN: "bool",
          TypeKind.ENUM: "enum", TypeKind.RECORD: "record"}


class CSharpTarget(BaseTarget):
    info = PackInfo(id="csharp", name="C# 12 (.NET 8)", role=PackRole.TARGET, extensions=[".cs"])
    tools = ["dotnet"]

    def from_neutral_type(self, t: NeutralType) -> str:
        return f"List<{self.from_neutral_type(t.item)}>" if t.kind == TypeKind.LIST and t.item else _TYPES[t.kind]

    def conventions(self) -> str:
        return CONVENTIONS

    def build(self, project: Path) -> BuildResult:
        if not any(project.rglob("Entry.cs")):
            return BuildResult(ok=False, log="Falta App/Entry.cs con public static object? Run(IDictionary<string, object?> input).")
        for extra in [*project.rglob("*.csproj"), *project.rglob("*.sln")]:
            extra.unlink()   # la plataforma controla el proyecto de verificación
        (project / PROJECT).write_text(CSPROJ, encoding="utf-8")
        (project / HARNESS).write_text(HARNESS_SOURCE, encoding="utf-8")
        return to_build(run_cmd(["dotnet", "build", PROJECT, "-c", "Release", "-o", OUT, "--nologo", "-v", "q"], project))

    def run_harness(self, project: Path, cases: list[Case]) -> list[CaseOutput]:
        write_cases(project, cases)
        result = run_cmd(["dotnet", f"{OUT}/AgenTCSVerify.dll", "cases.json", "actual.json"], project)
        return read_actual(project, result)
