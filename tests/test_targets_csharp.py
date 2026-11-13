"""Pack de destino C#: configuración estática siempre; compilación y arnés reales solo con .NET (en Docker)."""
import shutil

import pytest

from copilot.contracts import Case
from copilot.languages.csharp.adapter import CSPROJ, HARNESS_SOURCE, CSharpTarget

HAS_DOTNET = shutil.which("dotnet") is not None


def test_harness_keeps_integers_as_long():
    # Sin el cast a object el ternario convierte todo entero en decimal y (long)input["x"] falla.
    assert "? (object)l : e.GetDecimal()" in HARNESS_SOURCE


def test_verification_project_excludes_framework_tests_and_program():
    for pattern in ("**/Infrastructure/**", "**/Tests/**", "**/Program.cs"):
        assert pattern in CSPROJ
    assert "<UseAppHost>false</UseAppHost>" in CSPROJ and "<NuGetAudit>false</NuGetAudit>" in CSPROJ


ENTRY = '''using System.Globalization;
namespace App;
public enum Estado { N, M, J }
public static class Entry
{
    public static object? Run(IDictionary<string, object?> input)
    {
        var saldo = decimal.Parse((string)input["saldo"]!, CultureInfo.InvariantCulture);
        var dias = (long)input["dias"]!;
        if (saldo <= 0m)
            return new Dictionary<string, object?> { ["error"] = new Dictionary<string, object?> { ["code"] = "SALDO", ["message"] = "Saldo invalido" } };
        // Regla BR-001 · PAGOMIN.cbl:47
        var interes = Math.Round(saldo * 0.0215m, 2, MidpointRounding.AwayFromZero);
        var estado = dias > 90 ? Estado.J : dias > 30 ? Estado.M : Estado.N;
        return new Dictionary<string, object?> { ["interes"] = interes, ["estado"] = estado, ["corte"] = new DateOnly(2026, 1, 31), ["dias"] = dias };
    }
}
'''


@pytest.mark.skipif(not HAS_DOTNET, reason="requiere .NET 8 SDK (en Docker viene instalado)")
def test_csharp_build_and_harness_end_to_end(tmp_path):
    (tmp_path / "App").mkdir()
    (tmp_path / "App" / "Entry.cs").write_text(ENTRY, encoding="utf-8")
    (tmp_path / "Infrastructure").mkdir()
    (tmp_path / "Infrastructure" / "Api.cs").write_text("using Microsoft.AspNetCore.Mvc; class Api : ControllerBase {}")
    (tmp_path / "Tests").mkdir()
    (tmp_path / "Tests" / "EntryTests.cs").write_text("using Xunit; public class EntryTests { [Fact] public void T() {} }")
    (tmp_path / "Program.cs").write_text("System.Console.WriteLine(\"no debe compilarse\");")
    target = CSharpTarget()
    build = target.build(tmp_path)
    assert build.ok, build.log
    out = target.run_harness(tmp_path, [
        Case(id="c1", input={"saldo": "10000.00", "dias": 45}),
        Case(id="c2", input={"saldo": "0.00", "dias": 0}),
        Case(id="c3", input={"saldo": "1234.57", "dias": 120}),
    ])
    by_id = {o.id: o for o in out}
    assert by_id["c1"].output == {"interes": "215.00", "estado": "M", "corte": "2026-01-31", "dias": 45}
    assert by_id["c2"].error.code == "SALDO" and by_id["c2"].error.message == "Saldo invalido"
    assert by_id["c3"].output["interes"] == "26.54" and by_id["c3"].output["estado"] == "J"
