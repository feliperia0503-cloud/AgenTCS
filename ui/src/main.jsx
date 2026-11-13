import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/manrope/latin-600.css';
import '@fontsource/manrope/latin-700.css';
import '@fontsource/manrope/latin-800.css';
import './styles.css';
import { api } from './api/client.js';
import { toUiRule } from './api/adapters.js';

const Icon = ({ name, size = 20 }) => {
  const paths = {
    home: <><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v10h13V10"/><path d="M9.5 20v-6h5v6"/></>,
    route: <><circle cx="5" cy="6" r="2"/><circle cx="19" cy="18" r="2"/><path d="M7 6h3.5A3.5 3.5 0 0 1 14 9.5v5a3.5 3.5 0 0 0 3.5 3.5H17"/></>,
    rules: <><path d="M5 4h14v16H5z"/><path d="M8 8h8M8 12h8M8 16h5"/></>,
    test: <><path d="M9 3v5l-5 9a2.8 2.8 0 0 0 2.5 4h11a2.8 2.8 0 0 0 2.5-4l-5-9V3"/><path d="M8 3h8M7 15h10"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
    logout: <><path d="M10 4H5v16h5M14 8l4 4-4 4M8 12h10"/></>,
    chevron: <path d="m9 18 6-6-6-6"/>,
    git: <><circle cx="6" cy="5" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="6" cy="19" r="2"/><path d="M6 7v10M8 6h4a4 4 0 0 1 4 4v4.2M16.6 16.2 18 15l1.4 1.2"/></>,
    spark: <><path d="m12 3 1.2 3.8L17 8l-3.8 1.2L12 13l-1.2-3.8L7 8l3.8-1.2L12 3Z"/><path d="m18.5 14 .7 2.3 2.3.7-2.3.7-.7 2.3-.7-2.3-2.3-.7 2.3-.7.7-2.3Z"/></>,
    play: <path d="m8 5 11 7-11 7V5Z"/>,
    check: <path d="m5 12 4 4L19 6"/>,
    close: <path d="m6 6 12 12M18 6 6 18"/>,
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
    arrow: <><path d="M5 12h14M14 7l5 5-5 5"/></>,
    shield: <><path d="M12 3 5 6v5c0 4.6 2.8 8 7 10 4.2-2 7-5.4 7-10V6l-7-3Z"/><path d="m9 12 2 2 4-4"/></>,
    code: <path d="m8 8-4 4 4 4M16 8l4 4-4 4M14 4l-4 16"/>,
    menu: <path d="M4 7h16M4 12h16M4 17h16"/>,
    upload: <><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M5 20h14"/></>,
    download: <><path d="M12 4v12"/><path d="m7 11 5 5 5-5"/><path d="M5 20h14"/></>,
    alert: <><path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 2.5 17.5A2 2 0 0 0 4.2 20.5h15.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></>
  };
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
};

// ---------------------------------------------------------------- estado de la ejecución (RunState)
const POLL_MS = 2500;
const PHASE_NAMES = { 1: 'Ingesta', 2: 'Análisis', 3: 'Extracción de reglas', 4: 'Validación humana', 5: 'Diseño', 6: 'Generación', 7: 'Verificación', 8: 'Empaquetado' };
const STATIONS = [['Código', [1]], ['Extracción', [2, 3]], ['Validación', [4]], ['Generación', [5, 6]], ['Pruebas', [7, 8]]];
const ARCHIVE_ACCEPT = '.zip,.tar,.tgz,.gz,.cbl,.cob,.cpy,.jcl,.pli,.sql,.pks,.pkb,.prc,.fnc,.trg,.pas,.dpr,.dfm,.inc,.rpg,.rpgle,.sqlrpgle,.cs,.vb,.bas,.frm,.cls,.java,.jsp,.abap,.prg,.4gl,.f,.for,.f90,.c,.cpp,.h,.asm,.nsp,.py,.js,.php,.pl,.xml,.config';

const phaseOf = (run, n) => run?.phases?.[n] ?? run?.phases?.[String(n)] ?? { status: 'PENDIENTE', gate_message: '' };
const anyFailed = (run) => run && Object.values(run.phases).some(p => p.status === 'FALLIDA');
const isFinished = (run) => phaseOf(run, 8).status === 'APROBADA';
const awaitingReview = (run) => phaseOf(run, 4).status === 'ESPERANDO_HUMANO';
const needsPolling = (run) => Boolean(run) && !anyFailed(run) && !isFinished(run) && !awaitingReview(run);
const approvedCount = (run) => run ? Object.values(run.phases).filter(p => p.status === 'APROBADA').length : 0;
const failedPhase = (run) => run && Object.entries(run.phases).find(([, p]) => p.status === 'FALLIDA');
const pendingRules = (run) => run?.spec?.rules?.filter(r => r.status === 'PENDIENTE') ?? [];

function stationState(run, phases) {
  const st = phases.map(n => phaseOf(run, n).status);
  if (st.includes('FALLIDA')) return 'failed';
  if (st.every(s => s === 'APROBADA')) return 'done';
  if (st.some(s => s === 'EN_CURSO' || s === 'ESPERANDO_HUMANO' || s === 'APROBADA')) return 'active';
  return 'pending';
}

function stationLabel(run, name, state) {
  if (!run) return 'Pendiente';
  if (state === 'failed') return 'Requiere atención';
  if (name === 'Código') return state === 'done' ? `${run.files.length} archivo(s)` : 'Cargando';
  if (name === 'Extracción') return state === 'done' ? `${run.spec?.rules?.length ?? 0} reglas` : state === 'active' ? 'En curso' : 'Pendiente';
  if (name === 'Validación') return awaitingReview(run) ? `${pendingRules(run).length} por revisar` : state === 'done' ? 'Aprobada' : 'Pendiente';
  if (name === 'Generación') return state === 'active' ? `Intento ${run.generation_attempts || 1}` : state === 'done' ? `${run.generation_attempts} intento(s)` : 'Pendiente';
  if (name === 'Pruebas') return run.verification ? `${run.verification.passed}/${run.verification.total} casos` : state === 'active' ? 'En curso' : 'Pendiente';
  return '';
}

function useRunPolling(run, setRun, setRunError) {
  useEffect(() => {
    if (!needsPolling(run)) return undefined;
    const timer = setInterval(async () => {
      try {
        setRun(await api.getRun(run.run_id));
      } catch (err) {
        setRunError({ message: err.message, action: err.action });
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [run, setRun, setRunError]);
}

function ErrorBox({ title, error }) {
  if (!error) return null;
  return <div className="inline-error" role="alert"><strong>{title}</strong><span>{error.message}{error.action ? ` ${error.action}` : ''}</span></div>;
}

// ---------------------------------------------------------------- acceso (simulado, sin credenciales reales)
function Login({ onLogin }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const submit = (e) => {
    e.preventDefault();
    const email = String(new FormData(e.currentTarget).get('email') || '').trim();
    if (!email.includes('@')) {
      setError('Escribe un correo corporativo válido.');
      return;
    }
    setError('');
    setLoading(true);
    setTimeout(() => onLogin(email), 300);
  };
  return <main className="login-shell">
    <section className="login-brand" aria-label="Presentación de AgenTCS">
      <div className="brand-mark large"><span>A</span></div>
      <div className="login-copy">
        <h1>Moderniza el código.<br/>Conserva el negocio.</h1>
        <p>AgenTCS convierte sistemas legacy en conocimiento trazable antes de escribir una sola línea del reemplazo.</p>
      </div>
      <div className="continuity-diagram" aria-hidden="true">
        <span className="line-source">LEGACY</span>
        <div className="continuity-line"><i/><i/><i/><i/></div>
        <span className="line-target">OBJETIVO</span>
      </div>
    </section>
    <section className="login-panel">
      <form className="login-form" onSubmit={submit}>
        <div className="mobile-brand"><div className="brand-mark"><span>A</span></div><b>AgenTCS</b></div>
        <h2>Accede a tu espacio</h2>
        <p>Inicia o continúa un proyecto de modernización.</p>
        <label>Correo corporativo<input name="email" type="email" placeholder="nombre@empresa.com" autoComplete="username" required aria-describedby={error ? 'login-error' : undefined}/></label>
        <label>Contraseña<input type="password" placeholder="••••••••" autoComplete="current-password" required /></label>
        {error && <div className="inline-error" id="login-error" role="alert"><strong>No pudimos validar el acceso</strong><span>{error}</span></div>}
        <button className="primary-button full" disabled={loading} aria-live="polite">{loading ? <><span className="spinner"/>Validando acceso</> : <>Entrar al espacio <Icon name="arrow"/></>}</button>
        <p className="security-copy"><Icon name="shield" size={17}/> Acceso local · El correo solo identifica al revisor de las reglas</p>
      </form>
    </section>
  </main>;
}

// ---------------------------------------------------------------- aplicación
function App() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [userEmail, setUserEmail] = useState('');
  const [section, setSection] = useState('migration');
  const [mobileNav, setMobileNav] = useState(false);
  const [catalog, setCatalog] = useState(null);
  const [catalogError, setCatalogError] = useState(null);
  const [repo, setRepo] = useState('');
  const [branch, setBranch] = useState('');
  const [files, setFiles] = useState([]);
  const [language, setLanguage] = useState('');
  const [framework, setFramework] = useState('');
  const [architecture, setArchitecture] = useState('');
  const [suggesting, setSuggesting] = useState(false);
  const [suggestion, setSuggestion] = useState(null);
  const [suggestError, setSuggestError] = useState(null);
  const [run, setRun] = useState(null);
  const [runError, setRunError] = useState(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => { window.scrollTo({ top: 0, behavior: 'auto' }); }, [section]);
  useEffect(() => {
    if (!loggedIn || catalog) return;
    api.catalog().then(setCatalog).catch(err => setCatalogError({ message: err.message, action: err.action }));
  }, [loggedIn, catalog]);
  useRunPolling(run, setRun, setRunError);

  const languageInfo = catalog?.languages.find(l => l.id === language);

  const chooseLanguage = (next) => {
    setLanguage(next);
    const options = catalog?.languages.find(l => l.id === next)?.frameworks ?? [];
    setFramework(options[0]?.id ?? '');
  };

  const suggest = async () => {
    setSuggesting(true);
    setSuggestError(null);
    try {
      const result = await api.suggest({ files, repoUrl: repo, branch });
      setLanguage(result.suggestion.language);
      setFramework(result.suggestion.framework);
      setArchitecture(result.suggestion.architecture);
      setSuggestion(result);
    } catch (err) {
      setSuggestion(null);
      setSuggestError({ message: err.message, action: err.action });
    } finally {
      setSuggesting(false);
    }
  };

  const startMigration = async () => {
    setStarting(true);
    setRunError(null);
    try {
      setRun(await api.createRun({ files, repoUrl: repo, branch, targetLanguage: language, framework, architecture, demo: false }));
    } catch (err) {
      setRunError({ message: err.message, action: err.action });
    } finally {
      setStarting(false);
    }
  };

  const resetRun = () => { setRun(null); setRunError(null); setSuggestion(null); setFiles([]); setRepo(''); setBranch(''); };

  if (!loggedIn) return <Login onLogin={(email) => { setUserEmail(email); setLoggedIn(true); }} />;
  const userName = userEmail.split('@')[0] || 'Usuario';
  const initials = userName.split(/[._-]/).filter(Boolean).map(p => p[0]).join('').slice(0, 2).toUpperCase() || 'U';
  const pending = pendingRules(run).length;
  const navItems = [['home', 'Resumen', 'home'], ['route', 'Migración', 'migration'], ['rules', 'Reglas de negocio', 'rules'], ['test', 'Pruebas y código', 'tests']];
  const shared = { run, setRun, runError, setRunError, setSection, userEmail };

  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? 'open' : ''}`}>
      <div className="sidebar-top"><div className="brand-mark"><span>A</span></div><div className="wordmark"><strong>AgenTCS</strong><small>Migration studio</small></div><button className="icon-button close-nav" onClick={() => setMobileNav(false)} aria-label="Cerrar navegación"><Icon name="close"/></button></div>
      <nav aria-label="Navegación principal">{navItems.map(([icon, label, value]) => <button key={value} className={section === value ? 'active' : ''} onClick={() => { setSection(value); setMobileNav(false); }}><Icon name={icon}/><span>{label}</span>{value === 'rules' && pending > 0 && <em>{pending}</em>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="user-block"><div className="avatar">{initials}</div><div><strong>{userName}</strong><small>{userEmail}</small></div><button className="icon-button" onClick={() => setLoggedIn(false)} aria-label="Cerrar sesión"><Icon name="logout"/></button></div></div>
    </aside>
    {mobileNav && <button className="scrim" onClick={() => setMobileNav(false)} aria-label="Cerrar navegación"/>}
    <main className="main-area">
      <header className="topbar"><button className="icon-button menu-button" onClick={() => setMobileNav(true)} aria-label="Abrir navegación"><Icon name="menu"/></button><div className="breadcrumbs"><span>Proyectos</span><Icon name="chevron" size={16}/><strong>{run?.spec?.program ?? (run ? 'Migración en curso' : 'Nueva migración')}</strong></div><div className="top-actions"><span className="environment"><i/> {needsPolling(run) ? 'Procesando…' : 'Entorno local'}</span><span className="avatar small">{initials}</span></div></header>
      {section === 'tests' ? <TestsView {...shared}/>
        : section === 'rules' ? <RulesView {...shared}/>
        : section === 'home' ? <Overview {...shared}/>
        : <MigrationView {...shared} catalog={catalog} catalogError={catalogError} languageInfo={languageInfo}
            repo={repo} setRepo={setRepo} branch={branch} setBranch={setBranch} files={files} setFiles={setFiles}
            language={language} chooseLanguage={chooseLanguage} framework={framework} setFramework={setFramework}
            architecture={architecture} setArchitecture={setArchitecture} suggesting={suggesting} suggest={suggest}
            suggestion={suggestion} suggestError={suggestError} starting={starting} startMigration={startMigration} resetRun={resetRun}/>}
    </main>
  </div>;
}

// ---------------------------------------------------------------- ruta de migración (5 estaciones)
function MigrationRoute({ run }) {
  const progress = Math.round(approvedCount(run) / 8 * 100);
  return <div className="migration-route" style={{ '--route-progress': `${progress}%` }} role="progressbar" aria-label="Progreso de la migración" aria-valuemin="0" aria-valuemax="100" aria-valuenow={progress}>
    {STATIONS.map(([name, phases], i) => {
      const state = run ? stationState(run, phases) : 'pending';
      return <div className={`route-stop ${state !== 'pending' ? 'reached' : ''} ${state}`} key={name}>
        <span className="stop-dot">{state === 'done' ? <Icon name="check" size={13}/> : state === 'failed' ? '!' : i + 1}</span>
        <div><strong>{name}</strong><small>{stationLabel(run, name, state)}</small></div>
      </div>;
    })}
  </div>;
}

function PhaseList({ run }) {
  return <ol className="phase-list">{Object.keys(PHASE_NAMES).map(n => {
    const p = phaseOf(run, n);
    return <li key={n} className={`phase-item ${p.status.toLowerCase()}`}><span className="phase-dot">{p.status === 'APROBADA' ? '✓' : p.status === 'FALLIDA' ? '!' : p.status === 'EN_CURSO' ? '…' : n}</span><div><strong>{PHASE_NAMES[n]}</strong>{p.gate_message && <small>{p.gate_message}</small>}</div></li>;
  })}</ol>;
}

// ---------------------------------------------------------------- vista de migración
function MigrationView(props) {
  const { run, runError, setSection, catalog, catalogError, languageInfo, repo, setRepo, branch, setBranch, files, setFiles,
    language, chooseLanguage, framework, setFramework, architecture, setArchitecture, suggesting, suggest, suggestion,
    suggestError, starting, startMigration, resetRun } = props;
  const [sourceError, setSourceError] = useState('');
  const hasSource = repo.trim() !== '' || files.length > 0;
  const configured = Boolean(language && framework && architecture);
  const blockedByTools = languageInfo && !languageInfo.available;
  const busy = needsPolling(run) || starting;
  const failed = failedPhase(run);

  const requestSuggestion = () => {
    if (!hasSource) { setSourceError('Indica un repositorio o sube archivos/comprimido antes de pedir una recomendación.'); return; }
    setSourceError('');
    suggest();
  };
  const rec = suggestion?.suggestion;

  return <div className="workspace">
    <section className="page-heading"><div><h1>Configura la migración</h1><p>Conecta el código legacy (cualquier lenguaje), define la tecnología objetivo y conserva cada regla de negocio con evidencia.</p></div>{run && <button className="secondary-button" onClick={resetRun} disabled={busy}>Nueva migración</button>}</section>
    <MigrationRoute run={run}/>
    <div className="work-grid">
      <section className="migration-form-area">
        <div className="section-title"><div><h2>Sistema de origen</h2><p>COBOL, PL/SQL, Delphi, RPG, VB6, C#, Java antiguo u otro. AgenTCS no modifica el origen.</p></div><span className="safe-label"><Icon name="shield" size={16}/> Solo lectura</span></div>
        <div className="repo-row"><label className="field-grow">Repositorio Git (GitHub, Bitbucket, GitLab, Azure DevOps…)<div className="input-with-icon"><Icon name="git"/><input value={repo} onChange={e => setRepo(e.target.value)} placeholder="https://bitbucket.org/organizacion/sistema-legacy.git" disabled={Boolean(run)}/></div></label><label>Rama<input value={branch} onChange={e => setBranch(e.target.value)} placeholder="main" disabled={Boolean(run)}/></label></div>
        <div className="repo-row"><label className="field-grow">O sube archivos o un comprimido (.zip, .tar.gz) <small>— si hay ambos, se usan los archivos</small><input type="file" multiple accept={ARCHIVE_ACCEPT} disabled={Boolean(run)} onChange={e => setFiles(Array.from(e.target.files || []))}/></label></div>
        <div className="repo-facts">{run ? <><span><i className="status-dot ok"/> {run.source_ref}</span><span>Origen detectado: {run.source_language}</span><span>{run.files.length} archivo(s)</span><span>{run.sanitization.length} dato(s) sensible(s) enmascarado(s)</span></>
          : suggestion ? <><span><i className="status-dot ok"/> Código analizado</span><span>{suggestion.inventory.languages.map(l => `${l.name} (${l.files})`).join(' · ')}</span><span>{suggestion.inventory.files} archivos · {suggestion.inventory.lines.toLocaleString('es-CO')} líneas</span><span>{suggestion.sanitized_findings} dato(s) sensible(s) enmascarado(s)</span></>
          : <span>{files.length ? `${files.length} archivo(s) seleccionado(s): ${files.slice(0, 3).map(f => f.name).join(', ')}${files.length > 3 ? '…' : ''}` : 'Aún sin código'}</span>}</div>
        {sourceError && <div className="inline-error compact" role="alert"><strong>Falta el código</strong><span>{sourceError}</span></div>}
        <hr/>
        <div className="section-title target-title"><div><h2>Tecnología objetivo</h2><p>Elige libremente lenguaje, framework y arquitectura, o pide una recomendación basada en tu código.</p></div><button className="secondary-button" onClick={requestSuggestion} disabled={suggesting || Boolean(run)} aria-live="polite">{suggesting ? <><span className="spinner dark"/>Analizando código</> : <><Icon name="spark" size={18}/> Sugerir configuración</>}</button></div>
        <ErrorBox title="No se pudo sugerir la configuración" error={suggestError}/>
        <ErrorBox title="No se pudo cargar el catálogo de destinos" error={catalogError}/>
        <div className="target-config-grid">
          <label>Lenguaje<select value={language} onChange={e => chooseLanguage(e.target.value)} disabled={!catalog || Boolean(run)}><option value="">Selecciona…</option>{catalog?.languages.map(l => <option value={l.id} key={l.id}>{l.label}{l.available ? '' : ' (requiere Docker)'}</option>)}</select><small>Runtime y sintaxis del proyecto destino.</small></label>
          <label>Framework<select value={framework} onChange={e => setFramework(e.target.value)} disabled={!language || Boolean(run)}><option value="">Selecciona…</option>{languageInfo?.frameworks.map(f => <option value={f.id} key={f.id}>{f.label}</option>)}</select><small>Adaptadores en infrastructure/.</small></label>
          <label className="architecture-field">Arquitectura<select value={architecture} onChange={e => setArchitecture(e.target.value)} disabled={!catalog || Boolean(run)}><option value="">Selecciona…</option>{catalog?.architectures.map(a => <option value={a.id} key={a.id}>{a.label}</option>)}</select><small>Organización y límites del sistema.</small></label>
        </div>
        <div className={`target-guidance ${rec ? 'suggested' : ''}`} role="status" aria-live="polite"><Icon name={rec ? 'check' : 'spark'} size={18}/><div>
          <strong>{rec ? `Sugerencia aplicada · confianza ${Math.round(rec.confidence * 100)}%` : 'Configuración manual'}</strong>
          <span>{rec ? <>{rec.source_summary} {rec.rationale}{rec.risks.length > 0 && <> <b>Riesgos:</b> {rec.risks.join(' · ')}</>}{rec.alternatives.length > 0 && <> <b>Alternativas:</b> {rec.alternatives.map(a => `${a.language}/${a.framework}/${a.architecture}: ${a.reason}`).join(' · ')}</>}</> : 'Elige la tecnología destino o solicita una recomendación.'}</span>
          {blockedByTools && <span><b>Este equipo no tiene:</b> {languageInfo.missing_tools.join(', ')}. Ejecuta AgenTCS con Docker para migrar a {languageInfo.label}.</span>}
        </div></div>
        <div className="migration-actions"><p><strong>La migración no sobrescribe el origen.</strong><br/>Extrae reglas, espera tu aprobación, genera el código, lo verifica contra el comportamiento esperado y lo corrige solo.</p>
          <button className="primary-button" onClick={startMigration} disabled={Boolean(run) || starting || !hasSource || !configured || blockedByTools} aria-live="polite">{starting ? <><span className="spinner"/>Cargando código</> : run ? <><Icon name="check" size={18}/> Migración iniciada</> : <><Icon name="play" size={18}/> Iniciar migración</>}</button></div>
        <ErrorBox title="No se pudo continuar" error={runError}/>
        {failed && <div className="inline-error recovery" role="alert"><div><strong>{PHASE_NAMES[failed[0]]} se detuvo</strong><span>{failed[1].gate_message}</span></div><button type="button" onClick={resetRun}>Empezar de nuevo</button></div>}
        {run && awaitingReview(run) && <div className="target-guidance suggested" role="status"><Icon name="rules" size={18}/><div><strong>{run.spec.rules.length} reglas extraídas esperan tu revisión</strong><span>Aprueba, ajusta o rechaza cada una; luego aprueba la especificación para generar el código.</span><button className="text-action" onClick={() => setSection('rules')}>Revisar reglas <Icon name="arrow" size={16}/></button></div></div>}
        {run && isFinished(run) && <div className="target-guidance suggested" role="status"><Icon name="check" size={18}/><div><strong>Migración completada</strong><span>{phaseOf(run, 7).gate_message}</span><button className="text-action" onClick={() => setSection('tests')}>Ver pruebas y código <Icon name="arrow" size={16}/></button></div></div>}
      </section>
      <aside className="rule-inspector">
        <div className="inspector-heading"><div><h2>Estado de la ejecución</h2><p>{run ? `Origen ${run.source_language} → ${run.target_language}` : 'Aparecerá al iniciar la migración'}</p></div></div>
        {run ? <PhaseList run={run}/> : <div className="empty-state"><Icon name="route"/><strong>Sin ejecución activa</strong><span>Conecta el código, elige la tecnología y pulsa Iniciar migración.</span></div>}
      </aside>
    </div>
  </div>;
}

// ---------------------------------------------------------------- reglas de negocio (HITL)
const STATUS_LABEL = { PENDIENTE: 'Pendiente', APROBADA: 'Aprobada', AJUSTADA: 'Ajustada', RECHAZADA: 'Rechazada' };

function RulesView({ run, setRun, setRunError, runError, setSection, userEmail }) {
  const rules = useMemo(() => (run?.spec?.rules ?? []).map(r => toUiRule(r, { domain: run.spec.domain || r.category })), [run]);
  const [query, setQuery] = useState('');
  const [activeId, setActiveId] = useState(null);
  const [comment, setComment] = useState('');
  const [adjusting, setAdjusting] = useState(false);
  const [draft, setDraft] = useState({ condition: '', action: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const filtered = rules.filter(r => `${r.id} ${r.title} ${r.detail} ${r.source}`.toLowerCase().includes(query.toLowerCase()));
  const active = rules.find(r => r.id === activeId) ?? filtered[0];
  const reviewOpen = run && awaitingReview(run);
  const pending = pendingRules(run).length;

  useEffect(() => { setComment(''); setAdjusting(false); setError(null); setDraft({ condition: active?.condition ?? '', action: active?.action ?? '' }); }, [active?.id]);

  if (!run?.spec) {
    return <div className="workspace"><section className="page-heading"><div><h1>Reglas de negocio</h1><p>Las reglas extraídas del código legacy aparecerán aquí con su evidencia.</p></div></section>
      <div className="rules-catalog"><div className="empty-state"><Icon name="rules"/><strong>{run ? 'Extrayendo reglas…' : 'Aún no hay una migración'}</strong><span>{run ? 'El análisis está en curso; esta vista se actualiza sola.' : 'Inicia una migración para extraer las reglas.'}</span>{!run && <button className="text-action" onClick={() => setSection('migration')}>Ir a migración <Icon name="arrow" size={16}/></button>}</div></div></div>;
  }

  const decide = async (action) => {
    setSaving(true);
    setError(null);
    try {
      const changes = action === 'adjust' ? { condition: draft.condition || null, action: draft.action } : undefined;
      setRun(await api.decideRule(run.run_id, active.id, { action, by: userEmail, comment: comment || undefined, changes }));
      setAdjusting(false);
    } catch (err) {
      setError({ message: err.message, action: err.action });
    } finally {
      setSaving(false);
    }
  };

  const approveSpec = async () => {
    setSaving(true);
    setRunError(null);
    try {
      setRun(await api.approveSpec(run.run_id, userEmail));
      setSection('migration');
    } catch (err) {
      setRunError({ message: err.message, action: err.action });
    } finally {
      setSaving(false);
    }
  };

  return <div className="workspace"><section className="page-heading"><div><h1>Reglas de negocio</h1><p>Revisa la lógica recuperada del código y su evidencia. Lo que apruebes es la especificación que guía la generación y las pruebas.</p></div>
    <div className="heading-actions"><span className="demo-note">{rules.length} reglas · {pending} pendientes</span><button className="primary-button" onClick={approveSpec} disabled={!reviewOpen || pending > 0 || saving}><Icon name="check"/> Aprobar especificación y generar</button></div></section>
    <ErrorBox title="No se pudo aprobar la especificación" error={runError}/>
    {run.spec.assumptions.length > 0 && <div className="target-guidance" role="note"><Icon name="alert" size={18}/><div><strong>Supuestos del análisis</strong><span>{run.spec.assumptions.join(' · ')}</span></div></div>}
    <div className="rules-layout"><section className="rules-catalog"><div className="filterbar"><div className="search-field"><Icon name="search"/><input placeholder="Buscar por regla, descripción o evidencia" value={query} onChange={e => setQuery(e.target.value)}/></div></div>
      <div className="catalog-head"><span>Regla</span><span>Estado</span><span>Confianza</span></div>
      {filtered.length ? filtered.map(rule => <button className={active?.id === rule.id ? 'active' : ''} onClick={() => setActiveId(rule.id)} key={rule.id}><span><b>{rule.id}</b><strong>{rule.title}</strong></span><span><em className={`status-badge ${rule.status.toLowerCase()}`}>{STATUS_LABEL[rule.status]}</em></span><span className={`confidence ${rule.needsAttention ? 'low' : ''}`}>{rule.confidence}%</span></button>)
        : <div className="empty-state"><Icon name="search"/><strong>No encontramos coincidencias</strong><span>Prueba con otro término.</span></div>}</section>
      {active && <aside className="rule-focus"><span className={`status-badge ${active.status.toLowerCase()}`}>{STATUS_LABEL[active.status]}</span>{active.needsAttention && <span className="status-badge low">Confianza baja: requiere comentario</span>}
        <h2>{active.title}</h2><p>{active.detail}</p>
        <h3>Lógica (pseudocódigo neutral)</h3>
        {adjusting ? <div className="review-box"><label>Condición<input value={draft.condition} onChange={e => setDraft({ ...draft, condition: e.target.value })}/></label><label>Acción<input value={draft.action} onChange={e => setDraft({ ...draft, action: e.target.value })}/></label></div>
          : <code>{active.condition ? `SI ${active.condition} → ` : ''}{active.action}</code>}
        <h3>Evidencia en el código legacy · {active.source}</h3>
        <pre className="code-block">{active.snippet}</pre>
        <h3>Confianza {active.confidence}%</h3><p>{active.raw.confidence_reason}</p>
        {active.assumptions?.length > 0 && <><h3>Supuestos</h3><ul>{active.assumptions.map(a => <li key={a}>{a}</li>)}</ul></>}
        {active.gherkin && <><h3>Escenario (Gherkin)</h3><pre className="code-block light">{active.gherkin}</pre></>}
        {active.review && <p className="review-note">Revisada por <b>{active.review.by}</b>{active.review.comment ? `: “${active.review.comment}”` : ''}</p>}
        {reviewOpen && <div className="review-box">
          <label>Comentario {active.needsAttention || adjusting ? '(obligatorio)' : '(opcional)'}<textarea rows={3} value={comment} onChange={e => setComment(e.target.value)} placeholder="Justifica la decisión para la trazabilidad"/></label>
          <ErrorBox title="No se pudo guardar la decisión" error={error}/>
          <div className="review-actions">
            {adjusting ? <><button className="primary-button" disabled={saving || !comment.trim() || !draft.action.trim()} onClick={() => decide('adjust')}>Guardar ajuste</button><button className="secondary-button" onClick={() => setAdjusting(false)}>Cancelar</button></>
              : <><button className="primary-button" disabled={saving || (active.needsAttention && !comment.trim())} onClick={() => decide('approve')}><Icon name="check"/> Aprobar</button><button className="secondary-button" disabled={saving} onClick={() => setAdjusting(true)}>Ajustar</button><button className="secondary-button danger" disabled={saving || !comment.trim()} onClick={() => decide('reject')}>Rechazar</button></>}
          </div></div>}
      </aside>}</div>
  </div>;
}

// ---------------------------------------------------------------- pruebas, intentos y código generado
function TestsView({ run, setSection }) {
  const [fileName, setFileName] = useState(null);
  const report = run?.verification;
  const files = Object.keys(run?.generated_files ?? {}).sort();
  const current = fileName && run.generated_files[fileName] !== undefined ? fileName : files[0];
  const attempts = [...(run?.verification_history ?? []), ...(report ? [report] : [])].sort((a, b) => a.attempt - b.attempt);

  if (!report) {
    return <div className="workspace"><section className="page-heading"><div><h1>Validación y pruebas</h1><p>Comprueba que el código migrado conserva el comportamiento del legacy.</p></div></section>
      <div className="test-table"><div className="empty-state"><Icon name="test"/><strong>{run && phaseOf(run, 6).status === 'EN_CURSO' ? phaseOf(run, 6).gate_message || 'Generando y verificando…' : 'Aún no hay resultados'}</strong><span>{run ? 'Los resultados aparecen cuando termina el primer intento de generación.' : 'Inicia una migración y aprueba sus reglas.'}</span>{!run && <button className="text-action" onClick={() => setSection('migration')}>Ir a migración <Icon name="arrow" size={16}/></button>}</div></div></div>;
  }

  const pct = report.total ? Math.round(report.passed / report.total * 1000) / 10 : 0;
  return <div className="workspace"><section className="page-heading"><div><h1>Validación y pruebas</h1><p>{report.oracle_description}</p></div>
    <div className="heading-actions"><span className="demo-note">Oráculo nivel {report.oracle_level}</span>{isFinished(run) && <a className="primary-button" href={api.packageUrl(run.run_id)}><Icon name="download"/> Descargar paquete</a>}</div></section>
    <section className="test-summary"><div className="test-score"><strong>{pct}%</strong><span>Equivalencia funcional</span><small>{report.passed} de {report.total} casos coinciden · intento {report.attempt}</small></div>
      <div className="coverage-bars">
        <div><span><b>Similitud de comportamiento</b><em>{Math.round((report.similarity ?? 0) * 100)}%</em></span><i><u style={{ width: `${Math.round((report.similarity ?? 0) * 100)}%` }}/></i></div>
        <div><span><b>Casos equivalentes</b><em>{report.passed} / {report.total}</em></span><i><u style={{ width: `${pct}%` }}/></i></div>
        <div><span><b>Cobertura de código</b><em>{report.coverage_lines != null ? `${report.coverage_lines}%` : 'No medida aún'}</em></span><i><u style={{ width: `${report.coverage_lines ?? 0}%` }}/></i></div>
      </div></section>
    <section className="test-table"><div className="table-heading"><div><h2>Intentos de autocorrección</h2><p>Cada intento recibe como retroalimentación los casos que fallaron en el anterior. Se conserva la mejor versión.</p></div></div>
      <div className="table-row table-header"><span>Intento</span><span>Casos</span><span>Correctos</span><span>Similitud</span><span>Estado</span></div>
      {attempts.map(a => <div className="table-row" key={a.attempt}><span><Icon name="test" size={18}/><b>Intento {a.attempt}{a.attempt === report.attempt ? ' · mejor versión' : ''}</b></span><span>{a.total}</span><span>{a.passed}</span><span>{Math.round((a.similarity ?? 0) * 100)}%</span><span className={`test-status ${a.passed === a.total ? 'passed' : 'warning'}`}>{a.passed === a.total ? 'Equivalente' : 'Con diferencias'}</span></div>)}
    </section>
    {report.differences.length > 0 && <section className="test-table"><div className="table-heading"><div><h2>Diferencias de la mejor versión</h2><p>Esperado (legacy/oráculo) frente a obtenido (código migrado).</p></div></div>
      <div className="table-row table-header"><span>Caso · campo</span><span>Esperado</span><span>Obtenido</span><span>Regla</span><span></span></div>
      {report.differences.slice(0, 30).map((d, i) => <div className="table-row" key={i}><span><b>{d.case_id}</b> {d.field}</span><span>{JSON.stringify(d.expected)}</span><span>{JSON.stringify(d.actual)}</span><span>{d.rule_ids.join(', ')}</span><span className="test-status warning">Revisar</span></div>)}
    </section>}
    {files.length > 0 && <section className="test-table"><div className="table-heading"><div><h2>Código generado · {run.target_language}{run.target_framework ? ` · ${run.target_framework}` : ''}</h2><p>{files.length} archivo(s) de la mejor versión. Los adaptadores del framework están en infrastructure/.</p></div></div>
      <div className="file-tabs">{files.map(f => <button key={f} className={f === current ? 'active' : ''} onClick={() => setFileName(f)}>{f}</button>)}</div>
      <pre className="code-block tall">{run.generated_files[current]}</pre></section>}
  </div>;
}

// ---------------------------------------------------------------- resumen
function Overview({ run, setSection }) {
  if (!run) {
    return <div className="workspace"><section className="overview-hero"><div><h1>Moderniza tu primer sistema</h1><p>Sube el código legacy (archivos, .zip o repositorio), elige la tecnología destino y AgenTCS extraerá las reglas de negocio, generará el código y demostrará que se comporta igual.</p><div className="hero-actions"><button className="primary-button" onClick={() => setSection('migration')}>Iniciar migración <Icon name="arrow"/></button></div></div><MigrationRoute run={null}/></section></div>;
  }
  const lowPending = (run.spec?.rules ?? []).filter(r => r.status === 'PENDIENTE' && r.confidence < 0.7).length;
  const failed = failedPhase(run);
  return <div className="workspace"><section className="overview-hero"><div><h1>{run.spec?.program ?? 'Migración en curso'}</h1><p>{run.source_language} → {run.target_language}{run.target_framework ? ` · ${run.target_framework}` : ''}{run.target_architecture ? ` · ${run.target_architecture}` : ''} · {run.source_ref}</p>
    <div className="hero-actions"><button className="primary-button" onClick={() => setSection('migration')}>Ver migración <Icon name="arrow"/></button>{run.spec && <button className="secondary-button" onClick={() => setSection('rules')}>Revisar {run.spec.rules.length} reglas</button>}</div></div><MigrationRoute run={run}/></section>
    <section className="attention-list"><div className="attention-title"><h2>Lo que requiere tu atención</h2><span>Actualizado automáticamente</span></div>
      {failed && <button onClick={() => setSection('migration')}><span className="attention-icon red"><Icon name="alert"/></span><span><strong>{PHASE_NAMES[failed[0]]} se detuvo</strong><small>{failed[1].gate_message}</small></span><Icon name="arrow"/></button>}
      {awaitingReview(run) && <button onClick={() => setSection('rules')}><span className="attention-icon amber"><Icon name="rules"/></span><span><strong>{pendingRules(run).length} reglas pendientes de revisión</strong><small>{lowPending} con confianza baja: requieren comentario.</small></span><Icon name="arrow"/></button>}
      {run.verification && <button onClick={() => setSection('tests')}><span className={`attention-icon ${run.verification.passed === run.verification.total ? 'blue' : 'red'}`}><Icon name="test"/></span><span><strong>{run.verification.passed}/{run.verification.total} casos equivalentes</strong><small>{phaseOf(run, 7).gate_message}</small></span><Icon name="arrow"/></button>}
      {run.sanitization.length > 0 && <button onClick={() => setSection('migration')}><span className="attention-icon blue"><Icon name="shield"/></span><span><strong>{run.sanitization.length} dato(s) sensible(s) enmascarado(s) antes de usar IA</strong><small>{[...new Set(run.sanitization.map(f => f.kind))].join(', ')}</small></span><Icon name="arrow"/></button>}
      {!failed && !awaitingReview(run) && !run.verification && <button onClick={() => setSection('migration')}><span className="attention-icon blue"><Icon name="route"/></span><span><strong>Procesando</strong><small>{Object.entries(run.phases).find(([, p]) => p.status === 'EN_CURSO')?.[1]?.gate_message || 'La migración avanza; esta vista se actualiza sola.'}</small></span><Icon name="arrow"/></button>}
    </section></div>;
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>);
