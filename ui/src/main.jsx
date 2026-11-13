import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/manrope/latin-600.css';
import '@fontsource/manrope/latin-700.css';
import '@fontsource/manrope/latin-800.css';
import './styles.css';

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
    menu: <path d="M4 7h16M4 12h16M4 17h16"/>
  };
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
};

const demoRules = [
  { id: 'RN-014', title: 'Límite diario de transferencias', domain: 'Pagos', confidence: 98, severity: 'Alta', detail: 'La suma de transferencias salientes de una cuenta no puede superar el límite diario configurado para su segmento.', source: 'TransferService.java · L184–231', tests: 6 },
  { id: 'RN-027', title: 'Bloqueo por intentos fallidos', domain: 'Seguridad', confidence: 96, severity: 'Crítica', detail: 'Después de tres intentos fallidos consecutivos, el acceso se bloquea durante 30 minutos y se registra un evento de auditoría.', source: 'AuthenticationManager.cs · L92–148', tests: 8 },
  { id: 'RN-031', title: 'Conversión con tasa de cierre', domain: 'Divisas', confidence: 91, severity: 'Media', detail: 'Las operaciones posteriores a las 16:00 usan la tasa de cierre del siguiente día hábil.', source: 'FxCalculator.cob · L440–506', tests: 4 },
  { id: 'RN-046', title: 'Reversión de movimiento pendiente', domain: 'Contabilidad', confidence: 87, severity: 'Alta', detail: 'Una transacción pendiente puede revertirse únicamente antes del proceso de conciliación nocturna.', source: 'REVERSAL.cbl · L118–167', tests: 5 },
];

const testRows = [
  ['TransferLimitSpec', '18', '18', '1.8 s', 'passed'],
  ['AuthenticationPolicySpec', '24', '24', '2.4 s', 'passed'],
  ['FxClosingRateSpec', '12', '11', '1.2 s', 'warning'],
  ['PendingReversalSpec', '16', '16', '1.6 s', 'passed'],
  ['ContractParitySpec', '38', '38', '4.7 s', 'passed'],
];

const languageOptions = [
  { value: 'java', label: 'Java 21' },
  { value: 'csharp', label: 'C# 13' },
  { value: 'typescript', label: 'TypeScript 5' },
  { value: 'kotlin', label: 'Kotlin 2' },
];

const frameworkOptions = {
  java: [
    { value: 'spring', label: 'Spring Boot 3' },
    { value: 'quarkus', label: 'Quarkus 3' },
    { value: 'micronaut', label: 'Micronaut 4' },
  ],
  csharp: [
    { value: 'aspnet', label: 'ASP.NET Core' },
    { value: 'worker', label: '.NET Worker Service' },
  ],
  typescript: [
    { value: 'nestjs', label: 'NestJS 11' },
    { value: 'fastify', label: 'Fastify 5' },
    { value: 'express', label: 'Express 5' },
  ],
  kotlin: [
    { value: 'ktor', label: 'Ktor 3' },
    { value: 'spring-kotlin', label: 'Spring Boot + Kotlin' },
  ],
};

const architectureOptions = [
  { value: 'hexagonal', label: 'Arquitectura hexagonal' },
  { value: 'clean', label: 'Clean Architecture' },
  { value: 'modular', label: 'Monolito modular' },
  { value: 'microservices', label: 'Microservicios' },
  { value: 'event-driven', label: 'Orientada a eventos' },
];

function Login({ onLogin }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const submit = (e) => {
    e.preventDefault();
    const email = new FormData(e.currentTarget).get('email');
    if (email !== 'arquitectura@banco.demo') {
      setError('Para entrar al prototipo, restaura la cuenta de demostración arquitectura@banco.demo.');
      return;
    }
    setError('');
    setLoading(true);
    setTimeout(onLogin, 700);
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
      <p className="demo-note light">Entorno de demostración · Datos sintéticos</p>
    </section>
    <section className="login-panel">
      <form className="login-form" onSubmit={submit}>
        <div className="mobile-brand"><div className="brand-mark"><span>A</span></div><b>AgenTCS</b></div>
        <h2>Accede a tu espacio</h2>
        <p>Continúa con el proyecto de modernización.</p>
        <label>Correo corporativo<input name="email" type="email" defaultValue="arquitectura@banco.demo" required aria-describedby={error ? 'login-error' : undefined}/></label>
        <label>Contraseña<input type="password" defaultValue="AgenTCS-demo" required /></label>
        {error && <div className="inline-error" id="login-error" role="alert"><strong>No pudimos validar el acceso</strong><span>{error}</span></div>}
        <div className="form-meta"><label className="checkbox"><input type="checkbox" defaultChecked/> Mantener sesión</label><button type="button" className="link-button" disabled title="Disponible al conectar el servicio de identidad">Recuperar acceso</button></div>
        <button className="primary-button full" disabled={loading} aria-live="polite">{loading ? <><span className="spinner"/>Validando acceso</> : <>Entrar al espacio <Icon name="arrow"/></>}</button>
        <p className="security-copy"><Icon name="shield" size={17}/> Acceso simulado · Sin conexión externa</p>
      </form>
    </section>
  </main>;
}

function App() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [section, setSection] = useState('migration');
  const [mobileNav, setMobileNav] = useState(false);
  const [repo, setRepo] = useState('https://git.demo.local/core-banking/transfers-legacy');
  const [branch, setBranch] = useState('main');
  const [suggesting, setSuggesting] = useState(false);
  const [suggested, setSuggested] = useState(false);
  const [language, setLanguage] = useState('java');
  const [framework, setFramework] = useState('spring');
  const [architecture, setArchitecture] = useState('hexagonal');
  const [migrating, setMigrating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [migrationFailed, setMigrationFailed] = useState(false);
  const [activeRule, setActiveRule] = useState(demoRules[0]);
  const [ruleQuery, setRuleQuery] = useState('');
  const [runningTests, setRunningTests] = useState(false);
  const [testError, setTestError] = useState('');
  const [testRecovered, setTestRecovered] = useState(false);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, [section]);

  useEffect(() => {
    if (!migrating) return;
    const timer = setInterval(() => setProgress(p => {
      if (p >= 68) {
        clearInterval(timer);
        setMigrating(false);
        setMigrationFailed(true);
        return 72;
      }
      return p + 4;
    }), 180);
    return () => clearInterval(timer);
  }, [migrating]);

  const filteredRules = useMemo(() => demoRules.filter(rule => `${rule.id} ${rule.title} ${rule.domain}`.toLowerCase().includes(ruleQuery.toLowerCase())), [ruleQuery]);

  const suggest = () => {
    setSuggesting(true);
    setTimeout(() => {
      setLanguage('java');
      setFramework('spring');
      setArchitecture('hexagonal');
      setSuggesting(false);
      setSuggested(true);
    }, 900);
  };

  const chooseLanguage = (nextLanguage) => {
    setLanguage(nextLanguage);
    setFramework(frameworkOptions[nextLanguage][0].value);
  };
  const runTests = () => {
    const retrying = Boolean(testError);
    setRunningTests(true);
    if (retrying) setTestError('');
    setTimeout(() => {
      setRunningTests(false);
      if (retrying) {
        setTestRecovered(true);
      } else {
        setTestRecovered(false);
        setTestError('FxClosingRateSpec no respondió para el calendario festivo. Puedes reintentar únicamente ese escenario.');
      }
    }, 1400);
  };

  const startMigration = () => {
    setMigrationFailed(false);
    setProgress(0);
    setMigrating(true);
  };

  const retryMigration = () => {
    setMigrationFailed(false);
    setProgress(100);
  };

  if (!loggedIn) return <Login onLogin={() => setLoggedIn(true)} />;

  const navItems = [
    ['home', 'Resumen', 'home'],
    ['route', 'Migración', 'migration'],
    ['rules', 'Reglas de negocio', 'rules'],
    ['test', 'Pruebas', 'tests'],
  ];

  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? 'open' : ''}`}>
      <div className="sidebar-top"><div className="brand-mark"><span>A</span></div><div className="wordmark"><strong>AgenTCS</strong><small>Migration studio</small></div><button className="icon-button close-nav" onClick={() => setMobileNav(false)} aria-label="Cerrar navegación"><Icon name="close"/></button></div>
      <nav aria-label="Navegación principal">{navItems.map(([icon, label, value]) => <button key={value} className={section === value ? 'active' : ''} onClick={() => {setSection(value); setMobileNav(false);}}><Icon name={icon}/><span>{label}</span>{value === 'rules' && <em>42</em>}</button>)}</nav>
      <div className="sidebar-bottom"><button disabled title="Disponible en la siguiente iteración"><Icon name="settings"/><span>Configuración</span></button><div className="user-block"><div className="avatar">AM</div><div><strong>Ana Martínez</strong><small>Arquitectura</small></div><button className="icon-button" onClick={() => setLoggedIn(false)} aria-label="Cerrar sesión"><Icon name="logout"/></button></div></div>
    </aside>
    {mobileNav && <button className="scrim" onClick={() => setMobileNav(false)} aria-label="Cerrar navegación"/>}
    <main className="main-area">
      <header className="topbar"><button className="icon-button menu-button" onClick={() => setMobileNav(true)} aria-label="Abrir navegación"><Icon name="menu"/></button><div className="breadcrumbs"><span>Proyectos</span><Icon name="chevron" size={16}/><strong>Core Banking Legacy</strong></div><div className="top-actions"><span className="environment"><i/> Simulación local</span><span className="avatar small">AM</span></div></header>
      {section === 'tests' ? <TestsView running={runningTests} onRun={runTests} testError={testError} testRecovered={testRecovered}/> : section === 'rules' ? <RulesView rules={filteredRules} query={ruleQuery} setQuery={setRuleQuery} activeRule={activeRule} setActiveRule={setActiveRule}/> : section === 'home' ? <Overview setSection={setSection}/> : <MigrationView repo={repo} setRepo={setRepo} branch={branch} setBranch={setBranch} suggesting={suggesting} suggested={suggested} suggest={suggest} language={language} setLanguage={chooseLanguage} framework={framework} setFramework={setFramework} architecture={architecture} setArchitecture={setArchitecture} migrating={migrating} startMigration={startMigration} migrationFailed={migrationFailed} retryMigration={retryMigration} progress={progress} activeRule={activeRule} setActiveRule={setActiveRule} setSection={setSection}/>} 
    </main>
  </div>;
}

function MigrationRoute({ progress }) {
  const complete = progress >= 100;
  const steps = [
    ['Repositorio', progress > 0 ? 'Conectado' : 'Preparando'],
    ['Extracción', progress >= 28 ? '42 reglas' : progress > 0 ? 'En curso' : 'Pendiente'],
    ['Validación', complete ? 'Validada' : progress >= 50 ? 'En curso' : 'Pendiente'],
    ['Generación', complete ? 'Generado' : progress >= 75 ? 'En curso' : 'Pendiente'],
    ['Pruebas', complete ? 'Correctas' : progress >= 95 ? 'En curso' : 'Pendiente'],
  ];
  return <div className="migration-route" style={{'--route-progress': `${Math.min(progress,100)}%`}} role="progressbar" aria-label="Progreso de la migración" aria-valuemin="0" aria-valuemax="100" aria-valuenow={progress}>{steps.map((step, i) => <div className={`route-stop ${progress >= [0,28,50,75,95][i] ? 'reached' : ''}`} key={step[0]}><span className="stop-dot">{progress >= [28,50,75,95,101][i] ? <Icon name="check" size={13}/> : i + 1}</span><div><strong>{step[0]}</strong><small>{step[1]}</small></div></div>)}</div>;
}

function MigrationView({ repo, setRepo, branch, setBranch, suggesting, suggested, suggest, language, setLanguage, framework, setFramework, architecture, setArchitecture, migrating, startMigration, migrationFailed, retryMigration, progress, activeRule, setActiveRule, setSection }) {
  const [repoError, setRepoError] = useState('');
  const requestSuggestion = () => {
    if (!repo.trim()) {
      setRepoError('Indica un repositorio antes de solicitar una recomendación.');
      return;
    }
    setRepoError('');
    suggest();
  };
  return <div className="workspace">
    <section className="page-heading"><div><h1>Configura la migración</h1><p>Conecta el sistema origen, define la tecnología objetivo y conserva cada regla de negocio con evidencia.</p></div><span className="demo-note">Datos de demostración</span></section>
    <MigrationRoute progress={progress}/>
    <div className="work-grid">
      <section className="migration-form-area">
        <div className="section-title"><div><h2>Sistema de origen</h2><p>AgenTCS analizará la estructura sin modificar el repositorio.</p></div><span className="safe-label"><Icon name="shield" size={16}/> Solo lectura</span></div>
        <div className="repo-row"><label className="field-grow">Repositorio Git<div className="input-with-icon"><Icon name="git"/><input value={repo} onChange={e => setRepo(e.target.value)}/></div></label><label>Rama<select value={branch} onChange={e => setBranch(e.target.value)}><option>main</option><option>develop</option><option>release/24.10</option></select></label></div>
        <div className="repo-facts"><span><i className="status-dot ok"/> Acceso verificado</span><span>Java 8 · COBOL</span><span>1.284 archivos</span><span>Último cambio hace 3 días</span></div>
        <hr/>
        <div className="section-title target-title"><div><h2>Tecnología objetivo</h2><p>Elige libremente el lenguaje, framework y arquitectura. La sugerencia es opcional.</p></div><button className="secondary-button" onClick={requestSuggestion} disabled={suggesting} aria-live="polite">{suggesting ? <><span className="spinner dark"/>Analizando</> : <><Icon name="spark" size={18}/> Sugerir configuración</>}</button></div>
        {repoError && <div className="inline-error compact" role="alert"><strong>Falta el repositorio</strong><span>{repoError}</span><button type="button" onClick={() => {setRepo('https://git.demo.local/core-banking/transfers-legacy'); setRepoError('');}}>Restaurar ejemplo</button></div>}
        <div className="target-config-grid">
          <label>Lenguaje<select value={language} onChange={e => setLanguage(e.target.value)}>{languageOptions.map(option => <option value={option.value} key={option.value}>{option.label}</option>)}</select><small>Runtime y sintaxis del proyecto destino.</small></label>
          <label>Framework<select value={framework} onChange={e => setFramework(e.target.value)}>{frameworkOptions[language].map(option => <option value={option.value} key={option.value}>{option.label}</option>)}</select><small>Estructura técnica y ecosistema base.</small></label>
          <label className="architecture-field">Arquitectura<select value={architecture} onChange={e => setArchitecture(e.target.value)}>{architectureOptions.map(option => <option value={option.value} key={option.value}>{option.label}</option>)}</select><small>Organización y límites del sistema.</small></label>
        </div>
        <div className={`target-guidance ${suggested ? 'suggested' : ''}`} role="status" aria-live="polite"><Icon name={suggested ? 'check' : 'spark'} size={18}/><div><strong>{suggested ? 'Sugerencia aplicada como punto de partida' : 'Configuración manual activa'}</strong><span>{suggested ? 'Java 21, Spring Boot 3 y arquitectura hexagonal ofrecen menor riesgo para este ejemplo. Puedes cambiar cualquier selección.' : 'Puedes iniciar la migración con tus selecciones actuales o solicitar una recomendación opcional.'}</span></div></div>
        <div className="migration-actions"><p><strong>La migración no sobrescribirá el origen.</strong><br/>Se creará una rama nueva con el código, la documentación y las pruebas.</p><button className="primary-button" onClick={startMigration} disabled={migrating || progress === 100 || !repo.trim()} aria-live="polite">{migrating ? <><span className="spinner"/>Migración en curso · {progress}%</> : progress === 100 ? <><Icon name="check" size={18}/> Validación recuperada</> : <><Icon name="play" size={18}/> Iniciar migración</>}</button></div>
        {migrationFailed && <div className="inline-error recovery" role="alert"><div><strong>La validación se detuvo al 72%</strong><span>FxClosingRateSpec no pudo confirmar el calendario festivo. El código generado permanece intacto.</span></div><button type="button" onClick={retryMigration}>Reintentar validación</button></div>}
      </section>
      <aside className="rule-inspector">
        <div className="inspector-heading"><div><h2>Reglas extraídas</h2><p>42 detectadas · 7 requieren revisión</p></div><button className="icon-button" onClick={() => setSection('rules')} aria-label="Ver todas las reglas"><Icon name="arrow"/></button></div>
        <div className="rule-tabs"><button className="active">Prioritarias</button><button disabled title="Disponible en la vista completa de reglas">Todas</button></div>
        <div className="rule-list">{demoRules.slice(0,3).map(rule => <button className={activeRule.id === rule.id ? 'active' : ''} onClick={() => setActiveRule(rule)} key={rule.id}><span><b>{rule.id}</b><em className={`severity ${rule.severity.toLowerCase()}`}>{rule.severity}</em></span><strong>{rule.title}</strong><small>{rule.domain} · Confianza {rule.confidence}%</small></button>)}</div>
        <div className="rule-detail"><span className="rule-id">{activeRule.id}</span><h3>{activeRule.title}</h3><p>{activeRule.detail}</p><dl><div><dt>Evidencia</dt><dd>{activeRule.source}</dd></div><div><dt>Pruebas asociadas</dt><dd>{activeRule.tests} casos generados</dd></div></dl><button className="text-action" onClick={() => setSection('rules')}>Abrir trazabilidad <Icon name="arrow" size={16}/></button></div>
      </aside>
    </div>
  </div>;
}

function RulesView({ rules, query, setQuery, activeRule, setActiveRule }) {
  return <div className="workspace"><section className="page-heading"><div><h1>Reglas de negocio</h1><p>Revisa la lógica recuperada del sistema y su evidencia antes de generar el código objetivo.</p></div><div className="heading-actions"><span className="demo-note">Datos de demostración</span><button className="secondary-button" disabled title="Disponible al conectar un repositorio real">Exportar inventario</button></div></section>
    <div className="rules-layout"><section className="rules-catalog"><div className="filterbar"><div className="search-field"><Icon name="search"/><input placeholder="Buscar por regla, dominio o evidencia" value={query} onChange={e => setQuery(e.target.value)}/></div><select aria-label="Filtrar por dominio" disabled title="Disponible en la siguiente iteración"><option>Todos los dominios</option><option>Pagos</option><option>Seguridad</option></select></div><div className="catalog-head"><span>Regla</span><span>Dominio</span><span>Confianza</span></div>{rules.length ? rules.map(rule => <button className={activeRule.id === rule.id ? 'active' : ''} onClick={() => setActiveRule(rule)} key={rule.id}><span><b>{rule.id}</b><strong>{rule.title}</strong></span><span>{rule.domain}</span><span className="confidence">{rule.confidence}%</span></button>) : <div className="empty-state"><Icon name="search"/><strong>No encontramos coincidencias</strong><span>Prueba con otro término o elimina los filtros.</span></div>}</section><aside className="rule-focus"><span className={`severity ${activeRule.severity.toLowerCase()}`}>Prioridad {activeRule.severity}</span><h2>{activeRule.title}</h2><p>{activeRule.detail}</p><h3>Fuente detectada</h3><code>{activeRule.source}</code><h3>Criterios generados</h3><ul><li>Escenario nominal cubierto</li><li>Validación de límite y excepción</li><li>Registro de auditoría verificado</li></ul><button className="primary-button full" disabled title="Disponible al conectar el flujo de aprobación"><Icon name="check"/> Aprobar regla</button></aside></div>
  </div>;
}

function TestsView({ running, onRun, testError, testRecovered }) {
  return <div className="workspace"><section className="page-heading"><div><h1>Validación y pruebas</h1><p>Comprueba que la aplicación modernizada conserva el comportamiento observado en el sistema legacy.</p></div><div className="heading-actions"><span className="demo-note">Datos de demostración</span><button className="primary-button" onClick={onRun} disabled={running} aria-live="polite">{running ? <><span className="spinner"/>Ejecutando suite</> : <><Icon name="play"/> Ejecutar todas</>}</button></div></section>
    {testError && <div className="inline-error recovery" role="alert"><div><strong>El runner terminó con una diferencia</strong><span>{testError}</span></div><button type="button" onClick={onRun} disabled={running}>Reintentar escenario</button></div>}
    <section className="test-summary"><div className="test-score"><strong>{running ? '—' : testRecovered ? '100%' : '98.7%'}</strong><span>Equivalencia funcional</span><small>{running ? 'Validando contratos…' : testRecovered ? '108 de 108 escenarios coinciden' : '107 de 108 escenarios coinciden'}</small></div><div className="coverage-bars"><div><span><b>Reglas cubiertas</b><em>39 / 42</em></span><i><u style={{width:'93%'}}/></i></div><div><span><b>Cobertura de código</b><em>84%</em></span><i><u style={{width:'84%'}}/></i></div><div><span><b>Contratos de API</b><em>38 / 38</em></span><i><u style={{width:'100%'}}/></i></div></div></section>
    <section className="test-table"><div className="table-heading"><div><h2>Suites de prueba</h2><p>Última ejecución hoy, 10:42 · 11.7 segundos</p></div><button className="secondary-button" disabled title="Disponible al conectar el runner de pruebas">Ver registro</button></div><div className="table-row table-header"><span>Suite</span><span>Casos</span><span>Correctos</span><span>Duración</span><span>Estado</span></div>{testRows.map(row => { const recoveredRow = testRecovered && row[0] === 'FxClosingRateSpec'; const status = recoveredRow ? 'passed' : row[4]; return <div className="table-row" key={row[0]}><span><Icon name="test" size={18}/><b>{row[0]}</b></span><span>{row[1]}</span><span>{recoveredRow ? row[1] : row[2]}</span><span>{row[3]}</span><span className={`test-status ${status}`}>{status === 'passed' ? 'Correcto' : 'Revisar'}</span></div>; })}</section>
  </div>;
}

function Overview({ setSection }) {
  return <div className="workspace"><section className="overview-hero"><div><h1>Core Banking Legacy</h1><p>La extracción está lista para revisión. Antes de generar el proyecto objetivo, confirma las reglas prioritarias y define la tecnología que prefieres.</p><div className="hero-actions"><button className="primary-button" onClick={() => setSection('migration')}>Continuar migración <Icon name="arrow"/></button><button className="secondary-button" onClick={() => setSection('rules')}>Revisar 42 reglas</button></div></div><MigrationRoute progress={48}/></section><section className="attention-list"><div className="attention-title"><h2>Lo que requiere tu atención</h2><span>Datos de demostración</span></div><button onClick={() => setSection('rules')}><span className="attention-icon amber"><Icon name="rules"/></span><span><strong>7 reglas tienen confianza menor al 90%</strong><small>Revisa la evidencia y confirma la intención del negocio.</small></span><Icon name="arrow"/></button><button onClick={() => setSection('tests')}><span className="attention-icon red"><Icon name="test"/></span><span><strong>1 escenario presenta una diferencia funcional</strong><small>FxClosingRateSpec no coincide para días festivos.</small></span><Icon name="arrow"/></button><button onClick={() => setSection('migration')}><span className="attention-icon blue"><Icon name="code"/></span><span><strong>Tecnología objetivo pendiente</strong><small>Elige lenguaje, framework y arquitectura; la sugerencia es opcional.</small></span><Icon name="arrow"/></button></section></div>;
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>);
