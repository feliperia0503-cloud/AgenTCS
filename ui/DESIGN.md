---
name: AgenTCS Migration Studio
description: Un sistema operativo sobrio para convertir migraciones legacy en rutas verificables.
colors:
  ink: "#172535"
  navy: "#10253f"
  paper: "#fbfcf8"
  ground: "#f2f3ef"
  line: "#d9ddd8"
  muted: "#617080"
  teal: "#0c7b76"
  teal-dark: "#075f5b"
  amber: "#d89b31"
  focus: "#e8ad42"
  white: "#ffffff"
typography:
  display:
    fontFamily: "Manrope, sans-serif"
    fontSize: "clamp(2.5rem, 4vw, 4.5rem)"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Manrope, sans-serif"
    fontSize: "clamp(2rem, 3vw, 3rem)"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Manrope, sans-serif"
    fontSize: "1.2rem"
    fontWeight: 700
    lineHeight: 1.2
  body:
    fontFamily: "Aptos, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Aptos, Segoe UI, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 750
    lineHeight: 1.2
rounded:
  control: "10px"
  option: "12px"
  panel: "14px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  2xl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.teal}"
    textColor: "{colors.white}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0 17px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.teal-dark}"
    textColor: "{colors.white}"
  button-secondary:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0 17px"
    height: "44px"
  input:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "46px"
  navigation-item:
    backgroundColor: "transparent"
    textColor: "#b8c7d2"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "44px"
  navigation-item-active:
    backgroundColor: "#1e405d"
    textColor: "{colors.white}"
  status-pill:
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "3px 7px"
  surface-container:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "28px"
  migration-route:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.white}"
    rounded: "{rounded.panel}"
    padding: "22px 24px"
---

# Design System: AgenTCS Migration Studio

## Overview

**Creative North Star: "La ruta verificable"**

AgenTCS se siente como una sala de operaciones empresarial: concentrada, precisa y legible, con la suficiente calidez para evitar una interfaz clínica. El shell azul noche contiene el trabajo; las superficies cálidas ordenan información densa; y la jerarquía tipográfica separa decisiones, evidencia y estado sin añadir ruido.

La identidad aparece en una sola idea persistente: cada migración es una ruta trazable que avanza por estaciones nombradas. El sistema privilegia convenciones conocidas, control humano y estados explícitos; el color refuerza la acción y la evidencia, nunca las sustituye.

**Key Characteristics:**

- Azul noche estructural sobre un fondo cálido y superficies de papel.
- Teal reservado a acciones, selección y confirmación operativa.
- Ámbar reservado al recorrido y al foco visible.
- Densidad precisa, radios moderados y jerarquía compacta.
- Estados expresados con texto, posición e iconografía además de color.

## Colors

La paleta combina un armazón bancario azul noche con neutrales cálidos; teal y ámbar tienen responsabilidades distintas y deliberadamente escasas.

### Primary

- **Teal operativo** (`teal`): identifica acciones primarias, selección, progreso cuantitativo y controles activos.
- **Teal profundo** (`teal-dark`): sostiene hover de acciones y texto de enlaces o etiquetas de confianza.

### Secondary

- **Ámbar de tránsito** (`amber`): marca el avance de la migración y los nodos alcanzados; no funciona como color genérico de llamada a la acción.
- **Ámbar de foco** (`focus`): crea el contorno de foco visible y mantiene la navegación por teclado inequívoca.

### Neutral

- **Tinta técnica** (`ink`): texto principal y datos de alta prioridad.
- **Azul noche estructural** (`navy`): sidebar, paneles hero y ruta de migración.
- **Papel operativo** (`paper`): contenedores de trabajo.
- **Suelo cálido** (`ground`): fondo general de la aplicación.
- **Línea silenciosa** (`line`): divisores y bordes estructurales.
- **Pizarra secundaria** (`muted`): descripciones, metadatos y texto de apoyo.
- **Blanco de control** (`white`): fondos de inputs y botones secundarios, y texto sobre acciones teal.

### Named Rules

**The Action and Evidence Rule.** El teal hace; el ámbar narra el recorrido. No intercambies sus funciones.

## Typography

**Display Font:** Manrope (con fallback sans-serif)
**Body Font:** Aptos (con Segoe UI y sans-serif)

**Character:** Manrope aporta autoridad compacta a títulos, métricas y marca; Aptos/Segoe UI conserva velocidad de lectura en formularios, tablas, estados y evidencia. La pareja evita el gesto editorial y se mantiene inequívocamente operativa.

### Hierarchy

- **Display** (800, fluido hasta 4.5rem, 1): proyectos y métricas que deben dominar un panel azul noche.
- **Headline** (700, fluido entre 2rem y 3rem, 1.15): encabezados de vistas operativas.
- **Title** (700, 1.2rem, 1.2): títulos de secciones, paneles e inspectores.
- **Body** (400, 1rem, 1.55): explicación y contenido continuo; los párrafos introductorios se limitan aproximadamente a 68–72 caracteres.
- **Label** (750, 0.75rem, 1.2): controles, navegación, metadatos y estados compactos; los encabezados tabulares reducen tamaño y usan espaciado de letras.

### Named Rules

**The Two Voices Rule.** Usa Manrope para orientación y decisión; usa Aptos/Segoe UI para operación, lectura y datos.

## Layout

En escritorio, el shell se divide en una navegación lateral fija de 246px y un área principal flexible. La barra superior mide 70px; el workspace centra el contenido hasta 1640px y usa padding fluido entre 24px y 48px. Los paneles de trabajo se organizan en una retícula principal de dos columnas con 24px de separación: formulario ancho e inspector estrecho.

La densidad se construye con una base de 8px y escalones recurrentes de 12, 16, 24, 32 y 48px. Los controles miden entre 44 y 46px de alto; los paneles principales usan 24–30px de padding; tablas y listas reducen el espaciado sin perder objetivos táctiles claros.

A 1120px, las columnas se comprimen y los paneles auxiliares simplifican detalle. A 800px, la navegación se convierte en drawer, la barra superior baja a 62px, las retículas se apilan y las acciones principales ocupan todo el ancho cuando corresponde. A 440px se ajustan títulos y listas densas. La ruta de migración nunca pierde estaciones: en móvil pasa a desplazamiento horizontal con columnas mínimas de 112px, conservando nombre y estado de las cinco etapas.

## Elevation & Depth

El sistema usa profundidad ambiental y contenida. El fondo cálido, las superficies de papel y los divisores construyen la mayor parte de la jerarquía; la sombra aparece en paneles, en la acción primaria y en el drawer móvil, sin convertir cada bloque en una tarjeta flotante.

### Shadow Vocabulary

- **Panel ambiental** (`0 8px 30px rgba(26,43,55,.07)`): separa contenedores de trabajo del suelo cálido.
- **Acción primaria** (`0 7px 16px rgba(5,75,72,.2)`): da presencia al botón teal sin aumentar su tamaño.
- **Drawer móvil** (`20px 0 40px rgba(5,20,32,.2)`): distingue navegación y scrim cuando el shell sale del lienzo.

### Named Rules

**The Ground Before Shadow Rule.** Resuelve primero la jerarquía con fondo, borde y espaciado; reserva la sombra para superficies operativas completas o estados temporales.

## Shapes

La forma es suavemente técnica: controles y botones usan esquinas de 10px, opciones y marcas compactas 12px, y paneles principales 14px. Los pills de estado son completamente redondos. Los círculos se reservan para avatares, estados puntuales y estaciones de la ruta; los contenedores rectangulares nunca adoptan radios exagerados.

## Components

### Buttons

- **Shape:** control compacto de 44px de alto con esquinas de 10px y padding horizontal de 17px.
- **Primary:** teal operativo con texto blanco y sombra contenida; su hover pasa a teal profundo.
- **Hover / Focus:** cambios tonales simples; todo control recibe un contorno ámbar de 3px con offset de 3px mediante `:focus-visible`.
- **Secondary:** superficie blanca, texto tinta y borde gris verdoso; en hover solo aclara el fondo y refuerza el borde.
- **Disabled:** mantiene la forma y el texto, reduce opacidad y muestra cursor no permitido.

### Chips

- **Style:** pills compactos con texto de alto peso. Las severidades Alta, Crítica y Media, y los resultados Correcto y Revisar, usan pares de fondo y texto propios.
- **State:** ningún estado depende solo del color: conserva siempre la palabra de severidad o resultado.

### Cards / Containers

- **Corner Style:** radio moderado de 14px.
- **Background:** papel operativo sobre suelo cálido; el hero y la ruta usan azul noche.
- **Shadow Strategy:** aplica la sombra ambiental únicamente al contenedor completo.
- **Border:** divisores de línea silenciosa organizan listas, pestañas y tablas.
- **Internal Padding:** 24–30px en superficies principales; 13–20px en filas densas.

### Inputs / Fields

- **Style:** fondo blanco, borde de 1px, radio de 10px, 46px de alto y padding horizontal de 14px; los inputs con icono reservan 43px a la izquierda.
- **Focus:** halo teal translúcido de 3px y borde teal; el caret usa el mismo acento.
- **Error / Disabled:** los errores usan un contenedor rojo pálido con título y explicación; los controles deshabilitados conservan etiqueta y reducen opacidad.

### Navigation

La navegación vive sobre azul noche. Cada ítem mide al menos 44px, usa radio de 10px y texto gris azulado; hover oscurece el fondo y el estado activo usa un azul elevado con texto blanco. Solo el icono activo toma ámbar. En móvil, la navegación sale del lienzo con scrim y un botón explícito de cierre.

### Migration Route

La firma del producto es una línea de tránsito de cinco estaciones: **Repositorio → Extracción → Validación → Generación → Pruebas**. Se presenta sobre azul noche, con línea y nodos inactivos azul grisáceo; el tramo alcanzado y el borde de cada estación alcanzada usan ámbar. Cada estación conserva número o check, nombre y estado. El ancho progresa con una transición de 500ms; en móvil la ruta se desplaza horizontalmente y nunca se reduce a puntos sin nombre.

## Do's and Don'ts

### Do:

- **Do** conserva teal para acciones, selección y confirmación operativa.
- **Do** conserva ámbar para la ruta de migración y el foco visible.
- **Do** expresa severidad y resultado con texto además de color.
- **Do** mantiene visibles los cinco nombres y estados de la ruta en todos los tamaños.
- **Do** identifica los datos sintéticos con una etiqueta explícita de demostración.

### Don't:

- **Don't** conviertas ámbar en un segundo color de botón primario.
- **Don't** uses sombras en cada bloque; la profundidad pertenece a superficies operativas completas.
- **Don't** ocultes etapas de la ruta para resolver el responsive.
- **Don't** uses Manrope para párrafos, tablas o formularios densos.
- **Don't** suavices la interfaz con radios mayores a los paneles existentes sin una razón funcional.
