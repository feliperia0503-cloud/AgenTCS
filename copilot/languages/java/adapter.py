"""Pack de DESTINO 'java' (Java 21). Verificación con javac/java del JDK, sin Maven ni dependencias:
se compila el núcleo (todo menos `infrastructure/`) junto con un arnés con su propio lector JSON."""
from __future__ import annotations

from pathlib import Path

from copilot.contracts import BuildResult, Case, CaseOutput, NeutralType, PackInfo, PackRole, TypeKind
from copilot.engine.sandbox import run_cmd

from ..base import COMMON_RULES, BaseTarget, read_actual, sources, to_build, write_cases

HARNESS = "AgenTCSHarness.java"
CLASSES = "build/classes"

CONVENTIONS = f"""Destino: Java 21, solo la biblioteca estándar en el núcleo.
- Punto de entrada OBLIGATORIO: `src/main/java/app/Entry.java`, `package app;`, con
  `public static Object run(java.util.Map<String, Object> input)`.
  En `input` los decimales llegan como String (usa `new BigDecimal((String) input.get("x"))`) y los enteros
  como Number (usa `((Number) input.get("n")).intValue()`).
  Devuelve `Map<String, Object>` (LinkedHashMap) con los campos de salida, o `List<Map<String, Object>>` si
  output_is_list. Valores decimales como `BigDecimal` con la escala exacta (setScale + RoundingMode).
- Paquetes: `domain` (records, reglas, sin dependencias externas), `application` (caso de uso),
  `infrastructure` (adaptadores del framework). Todo bajo `src/main/java/`.
- BigDecimal + RoundingMode explícito; intermedios con MathContext.DECIMAL128.
{COMMON_RULES}"""

_TYPES = {TypeKind.DECIMAL: "BigDecimal", TypeKind.INTEGER: "long", TypeKind.FLOAT: "double", TypeKind.STRING: "String",
          TypeKind.DATE: "LocalDate", TypeKind.DATETIME: "LocalDateTime", TypeKind.BOOLEAN: "boolean",
          TypeKind.ENUM: "enum", TypeKind.RECORD: "record"}

HARNESS_SOURCE = r'''import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public class AgenTCSHarness {
    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception {
        String text = new String(Files.readAllBytes(Paths.get(args[0])), StandardCharsets.UTF_8);
        List<Object> cases = (List<Object>) new JsonReader(text).value();
        StringBuilder out = new StringBuilder("[");
        for (int i = 0; i < cases.size(); i++) {
            Map<String, Object> c = (Map<String, Object>) cases.get(i);
            Map<String, Object> r = new LinkedHashMap<>();
            r.put("id", c.get("id"));
            try {
                Object res = app.Entry.run((Map<String, Object>) c.get("input"));
                Object err = res instanceof Map ? ((Map<?, ?>) res).get("error") : null;
                if (err instanceof Map) {
                    Map<String, Object> e = new LinkedHashMap<>();
                    Object code = ((Map<?, ?>) err).get("code"), msg = ((Map<?, ?>) err).get("message");
                    e.put("code", String.valueOf(code));
                    e.put("message", msg == null ? "" : String.valueOf(msg));
                    r.put("error", e);
                } else {
                    r.put("output", res);
                }
            } catch (Throwable t) {
                Map<String, Object> e = new LinkedHashMap<>();
                e.put("code", "EXEC_ERROR");
                e.put("message", t.getClass().getSimpleName() + ": " + t.getMessage());
                r.put("error", e);
            }
            if (i > 0) out.append(',');
            JsonWriter.write(out, r);
        }
        Files.write(Paths.get(args[1]), out.append(']').toString().getBytes(StandardCharsets.UTF_8));
    }
}

final class JsonWriter {
    static void write(StringBuilder b, Object v) {
        if (v == null) { b.append("null"); }
        else if (v instanceof BigDecimal) { str(b, ((BigDecimal) v).toPlainString()); }
        else if (v instanceof Double || v instanceof Float) { str(b, String.valueOf(v)); }
        else if (v instanceof Number || v instanceof Boolean) { b.append(v); }
        else if (v instanceof Map) {
            b.append('{'); boolean first = true;
            for (Map.Entry<?, ?> e : ((Map<?, ?>) v).entrySet()) {
                if (!first) b.append(','); first = false;
                str(b, String.valueOf(e.getKey())); b.append(':'); write(b, e.getValue());
            }
            b.append('}');
        } else if (v instanceof Iterable) {
            b.append('['); boolean first = true;
            for (Object o : (Iterable<?>) v) { if (!first) b.append(','); first = false; write(b, o); }
            b.append(']');
        } else if (v.getClass().isRecord()) {
            Map<String, Object> m = new LinkedHashMap<>();
            try {
                for (var rc : v.getClass().getRecordComponents()) m.put(rc.getName(), rc.getAccessor().invoke(v));
            } catch (ReflectiveOperationException e) { throw new RuntimeException(e); }
            write(b, m);
        } else { str(b, String.valueOf(v)); }
    }

    static void str(StringBuilder b, String s) {
        b.append('"');
        for (char ch : s.toCharArray()) {
            switch (ch) {
                case '"': b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default: if (ch < 0x20) b.append(String.format("\\u%04x", (int) ch)); else b.append(ch);
            }
        }
        b.append('"');
    }
}

final class JsonReader {
    private final String s; private int i = 0;
    JsonReader(String s) { this.s = s; }

    Object value() {
        ws(); char c = s.charAt(i);
        if (c == '{') return object();
        if (c == '[') return array();
        if (c == '"') return string();
        if (s.startsWith("true", i)) { i += 4; return Boolean.TRUE; }
        if (s.startsWith("false", i)) { i += 5; return Boolean.FALSE; }
        if (s.startsWith("null", i)) { i += 4; return null; }
        return number();
    }

    private Map<String, Object> object() {
        Map<String, Object> m = new LinkedHashMap<>(); i++; ws();
        if (s.charAt(i) == '}') { i++; return m; }
        while (true) {
            ws(); String k = string(); ws(); i++; m.put(k, value()); ws();
            if (s.charAt(i++) == '}') return m;
        }
    }

    private List<Object> array() {
        List<Object> l = new ArrayList<>(); i++; ws();
        if (s.charAt(i) == ']') { i++; return l; }
        while (true) { l.add(value()); ws(); if (s.charAt(i++) == ']') return l; }
    }

    private String string() {
        StringBuilder b = new StringBuilder(); i++;
        while (true) {
            char c = s.charAt(i++);
            if (c == '"') return b.toString();
            if (c == '\\') {
                char e = s.charAt(i++);
                switch (e) {
                    case 'n': b.append('\n'); break;
                    case 't': b.append('\t'); break;
                    case 'r': b.append('\r'); break;
                    case 'b': b.append('\b'); break;
                    case 'f': b.append('\f'); break;
                    case 'u': b.append((char) Integer.parseInt(s.substring(i, i + 4), 16)); i += 4; break;
                    default: b.append(e);
                }
            } else b.append(c);
        }
    }

    private Object number() {
        int start = i;
        while (i < s.length() && "+-0123456789.eE".indexOf(s.charAt(i)) >= 0) i++;
        String n = s.substring(start, i);
        if (n.indexOf('.') < 0 && n.indexOf('e') < 0 && n.indexOf('E') < 0) {
            try { return Long.parseLong(n); } catch (NumberFormatException ignored) { }
        }
        return new BigDecimal(n);
    }

    private void ws() { while (i < s.length() && Character.isWhitespace(s.charAt(i))) i++; }
}
'''


class JavaTarget(BaseTarget):
    info = PackInfo(id="java", name="Java 21", role=PackRole.TARGET, extensions=[".java"])
    tools = ["javac", "java"]

    def from_neutral_type(self, t: NeutralType) -> str:
        return f"List<{self.from_neutral_type(t.item)}>" if t.kind == TypeKind.LIST and t.item else _TYPES[t.kind]

    def conventions(self) -> str:
        return CONVENTIONS

    def build(self, project: Path) -> BuildResult:
        if not (project / "src/main/java/app/Entry.java").is_file():
            return BuildResult(ok=False, log="Falta src/main/java/app/Entry.java con public static Object run(Map<String,Object> input).")
        (project / HARNESS).write_text(HARNESS_SOURCE, encoding="utf-8")
        files = [f for f in sources(project, ".java", exclude={HARNESS})]
        return to_build(run_cmd(["javac", "-encoding", "UTF-8", "-d", CLASSES, *files, HARNESS], project))

    def run_harness(self, project: Path, cases: list[Case]) -> list[CaseOutput]:
        write_cases(project, cases)
        result = run_cmd(["java", "-cp", CLASSES, "AgenTCSHarness", "cases.json", "actual.json"], project)
        return read_actual(project, result)
