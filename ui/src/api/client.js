// Cliente de la API del copiloto. Los contratos (forma de los datos) están en
// copilot/contracts/schemas/*.schema.json; aquí se documentan con JSDoc.

/**
 * @typedef {Object} ApiError
 * @property {string} code     Código estable del error (p. ej. RUN_NOT_FOUND)
 * @property {string} message  Mensaje para el usuario
 * @property {string} action   Acción sugerida para corregirlo
 */

export class ApiRequestError extends Error {
  /** @param {number} status @param {ApiError} body */
  constructor(status, body) {
    super(body?.message ?? `Error ${status}`);
    this.status = status;
    this.code = body?.code ?? 'UNKNOWN';
    this.action = body?.action ?? 'Reintenta la operación. Si persiste, revisa los registros de la API.';
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`/api${path}`, options);
  } catch {
    throw new ApiRequestError(0, {
      code: 'API_UNREACHABLE',
      message: 'No se pudo conectar con la API del copiloto.',
      action: 'Verifica que la API esté corriendo (docker compose up o uvicorn en el puerto 8000).',
    });
  }
  const isJson = response.headers.get('content-type')?.includes('application/json');
  const body = isJson ? await response.json() : null;
  if (!response.ok) throw new ApiRequestError(response.status, body?.detail ?? body);
  return body;
}

const json = (method, data) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data),
});

export const api = {
  health: () => request('/health'),

  /**
   * Analiza el código legacy real con el LLM y recomienda lenguaje, framework y arquitectura.
   * Usa los archivos si hay; si no, clona el repositorio Git público (solo lectura).
   * @param {{ files?: File[], repoUrl?: string, branch?: string }} params
   * @returns {Promise<{ suggestion: Object, inventory: Object, sanitized_findings: number, labels: Object }>}
   */
  suggest: ({ files = [], repoUrl, branch }) => {
    const form = new FormData();
    files.forEach(file => form.append('files', file));
    if (repoUrl?.trim()) form.append('repo_url', repoUrl.trim());
    if (branch?.trim()) form.append('branch', branch.trim());
    return request('/suggest', { method: 'POST', body: form });
  },

  /** Packs de lenguaje disponibles: { sources: [...], targets: [...] } */
  languages: () => request('/languages'),

  /** Catálogo de destinos: { languages: [{ id, label, available, missing_tools, frameworks }], architectures } */
  catalog: () => request('/catalog'),

  /**
   * Crea una ejecución real: sube archivos o comprimidos (.zip, .tar.gz) o indica un repositorio Git.
   * @param {{ files?: File[], repoUrl?: string, branch?: string, targetLanguage: string, framework?: string,
   *           architecture?: string, sourceLanguage?: string, domain?: string, demo?: boolean }} params
   * @returns {Promise<Object>} RunState
   */
  createRun: ({ files = [], repoUrl, branch, targetLanguage, framework, architecture, sourceLanguage, domain, demo }) => {
    const form = new FormData();
    files.forEach(file => form.append('files', file));
    form.append('target_language', targetLanguage);
    if (framework) form.append('target_framework', framework);
    if (architecture) form.append('target_architecture', architecture);
    if (repoUrl?.trim()) form.append('repo_url', repoUrl.trim());
    if (branch?.trim()) form.append('branch', branch.trim());
    if (sourceLanguage) form.append('source_language', sourceLanguage);
    if (domain) form.append('domain', domain);
    if (demo !== undefined) form.append('demo', String(demo));
    return request('/runs', { method: 'POST', body: form });
  },

  getRun: (runId) => request(`/runs/${runId}`),

  /**
   * Decisión HITL sobre una regla.
   * @param {string} runId
   * @param {string} ruleId
   * @param {{ action: 'approve'|'adjust'|'reject', by: string, comment?: string, changes?: Object }} decision
   */
  decideRule: (runId, ruleId, decision) => request(`/runs/${runId}/rules/${ruleId}/decision`, json('POST', decision)),

  /** Aprueba la especificación completa y continúa a diseño, generación y verificación. */
  approveSpec: (runId, by) => request(`/runs/${runId}/approve`, json('POST', { by })),

  verification: (runId) => request(`/runs/${runId}/verification`),

  /** URL del paquete de migración (.zip) para un enlace de descarga. */
  packageUrl: (runId) => `/api/runs/${runId}/package`,
};
