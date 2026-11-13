# AgenTCS — Migration Studio (interfaz)

React 19 + Vite 8. Diseño en [DESIGN.md](DESIGN.md) y producto en [PRODUCT.md](PRODUCT.md).
Todas las pantallas usan datos reales de la API; no hay datos de demostración en el código.

## Desarrollo
Requiere la API en el puerto 8000 (ver README raíz).

```bash
cd ui
npm ci          # versiones fijadas en package-lock.json
npm run dev     # http://localhost:5173  — /api se redirige a http://localhost:8000
```
Otra URL de API: `AGENTCS_API_URL=http://host:puerto npm run dev`.

## Flujo
1. **Migración**: código legacy por repositorio Git (GitHub, Bitbucket, GitLab, Azure DevOps…) o archivos /
   comprimidos (.zip, .tar.gz), en cualquier lenguaje. "Sugerir configuración" analiza el código con IA.
   Lenguaje, framework y arquitectura destino vienen del catálogo de la API (`/api/catalog`); los destinos
   sin herramientas en el equipo se marcan "requiere Docker".
2. **Iniciar migración** crea la ejecución (`POST /api/runs`) y la interfaz consulta su estado cada 2,5 s.
3. **Reglas de negocio**: aprobar, ajustar o rechazar cada regla con su evidencia; comentario obligatorio si
   la confianza es baja. "Aprobar especificación y generar" lanza la generación y verificación.
4. **Pruebas y código**: equivalencia, similitud, intentos de autocorrección, diferencias, código generado y
   descarga del paquete.

## Módulos
- `src/api/client.js`: llamadas a la API. Los errores traen `code`, `message` y `action`.
- `src/api/adapters.js`: convierte `Rule` del contrato a la forma de las vistas.

El acceso es local: el correo solo identifica al revisor de las reglas (trazabilidad del HITL).
