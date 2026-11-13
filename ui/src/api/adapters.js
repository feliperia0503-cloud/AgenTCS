// Traduce los contratos de la API a la forma que ya usan las vistas de AgenTCS,
// para reemplazar los datos de demostración sin reescribir los componentes.

const SEVERITY_BY_CATEGORY = { CALCULO: 'Alta', VALIDACION: 'Alta', DECISION: 'Media', CONSTANTE: 'Media' };

/** Rule (contrato) -> regla de AgenTCS ({ id, title, domain, confidence, severity, detail, source, tests, ... }) */
export function toUiRule(rule, { domain = 'Negocio', testsByRule = {} } = {}) {
  const [start, end] = rule.source.lines;
  return {
    id: rule.id,
    title: rule.name,
    domain,
    confidence: Math.round(rule.confidence * 100),
    severity: SEVERITY_BY_CATEGORY[rule.category] ?? 'Media',
    detail: rule.description,
    source: `${rule.source.file} · L${start}–${end}`,
    tests: testsByRule[rule.id] ?? 0,
    // Campos adicionales que AgenTCS aún no muestra y la solución real necesita:
    status: rule.status,
    needsAttention: rule.confidence < 0.7,
    condition: rule.condition,
    action: rule.action,
    assumptions: rule.assumptions,
    gherkin: rule.gherkin,
    snippet: rule.source.snippet,
    review: rule.review,
    raw: rule,
  };
}

/** VerificationReport -> filas de la tabla de pruebas de AgenTCS [suite, total, aprobadas, duración, estado] */
export function toUiTestRows(report) {
  if (!report) return [];
  const failingByCase = new Set(report.differences.map(d => d.case_id));
  return [[
    `Equivalencia ${report.source_language} → ${report.target_language} (oráculo ${report.oracle_level})`,
    String(report.total),
    String(report.passed),
    '—',
    failingByCase.size === 0 ? 'passed' : 'warning',
  ]];
}

const PHASE_TO_ROUTE = { 1: 0, 2: 1, 3: 1, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4 };

/** RunState.phases -> progreso 0..100 para la ruta de AgenTCS (Repositorio → … → Pruebas) */
export function toRouteProgress(runState) {
  const phases = Object.entries(runState.phases);
  const done = phases.filter(([, p]) => p.status === 'APROBADA').length;
  return Math.round((done / phases.length) * 100);
}

/** Fase actual (primera no aprobada) e índice de estación en la ruta de AgenTCS. */
export function currentStation(runState) {
  const entry = Object.entries(runState.phases).find(([, p]) => p.status !== 'APROBADA');
  if (!entry) return { phase: 8, station: 4, status: 'APROBADA' };
  const phase = Number(entry[0]);
  return { phase, station: PHASE_TO_ROUTE[phase], status: entry[1].status, message: entry[1].gate_message };
}
