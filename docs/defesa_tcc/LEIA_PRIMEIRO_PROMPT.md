# Prompt de continuación — Defensa de TCC del SEEDS (para otro Claude)

> **Cómo usar:** copia todo este archivo como primer mensaje para el nuevo Claude y adjunta el ZIP `SEEDS_defesa_kit.zip`
> (y, si puedes, el PDF del artículo: `TCC_BRUNO_OLMEDO_COMPLETO_1.pdf`).

---

## 1. Quién soy y qué estamos haciendo

Soy Bruno, estudiante de Ingeniería de Energía (UNILA, ILATIT, Foz do Iguaçu). El **9/12/2026** defiendo mi TCC, de 30 minutos:
22 de slides, 6 de demostración en vivo del aplicativo y 2 de margen. El trabajo es el **SEEDS**, una plataforma web (Streamlit)
para componer microrredes y probar su gestión energética. Tiene dos contribuciones:

- **A · plataforma modular:** modelos físicos (FV, eólica, batería, PEMFC/H₂, red) en una representación energética común.
- **B · EMS jerárquico MILP–MPC con señal de valor futuro:** un planificador de horizonte largo pasa al MPC el valor de la energía
  guardada (V(E), linear por partes, por reoptimización paramétrica, no por duales).

Hay dos estudios de caso: una **microrred industrial CT-046** conectada a la red (C1–C4: cambia la composición) y una
**embarcación híbrida EMB-H2-120** aislada (C5–C6: cambia la carga inicial de la batería).

**Idioma:** hablamos en español/portuñol; **los slides van en portugués**.

## 2. Estado actual: el deck está completo (38/38 aprobados)

- `defesa_tcc/pptx/SEEDS_Defesa_TCC.pdf` es el deck final aprobado. **Míralo entero antes de hacer cualquier cosa**: es la referencia
  visual de todo.
- El orden y el estado de cada slide están en `defesa_tcc/ROTEIRO.md` (§ «Ordem do deck») y en `defesa_tcc/pptx/deck.py`, que es la
  fuente única del orden, de los títulos y de las falas del orador (`NOTA_EXTRA`).
- Las decisiones de diseño, slide por slide, están en `defesa_tcc/DESIGN.md`. El historial y las preferencias están en
  `defesa_tcc/CONTINUAR.md`.
- Cada slide aprobado es un HTML de 1920×1080 congelado (`slides/slideNN_aprovado.html`, más `capa/` y `slides/divisor0N.html`),
  generado por un script Python `slides/gerar_slideNN*.py`.

## 3. Lo que falta (en este orden)

### 3.1 Slide(s) de REFERENCIAS ← la próxima tarea
- **Solo las referencias que el deck cita** (29 en total), en el **mismo formato (IEEE) y con la misma numeración del artículo**.
  En `referencias_citadas.md` está qué número se cita en cada slide.
- El texto exacto de cada referencia **debe salir del PDF del artículo** (pídemelo si no lo adjunté). El archivo
  `articulo/tcc_texto_extraido.txt` es el texto del artículo extraído en dos columnas: **la sección de referencias quedó mezclada
  entre columnas y NO es confiable**. Úsalo solo como apoyo y confirma todo contra el PDF.
- Hay 29 referencias y el texto tiene que ser legible (≥ 18 px), así que probablemente sean **2 slides**. Pregúntame dónde van:
  después de «Agradecimentos» (lo usual) o antes.
- Hay que registrarlas en `pptx/deck.py` (sección 7 o una sección nueva sin número; pregúntame).

### 3.2 Slides AUXILIARES para la arguición (después de las referencias)
- La base es la tabla «SLIDES AUXILIARES» de `defesa_tcc/ROTEIRO_DETALHADO_v1.md` (A1–A15) y la lista «Perguntas prováveis — respostas
  curtas» del mismo archivo. No se muestran en la presentación: sirven para responder preguntas de la banca.
- **Cuidado con los datos ya desactualizados en ese plan:**
  - **A5 (curva H₂):** el plan dice «500 pontos». La rodada grabada registra **402** puntos de validación, y el slide 34 usa 402.
    Usa 402. Además, la curva y su error ya están en el slide 34: no la repitas, haz algo complementario.
  - **A14 (rastreabilidad):** C6 se reprodujo en el SEEDS como la rodada `92fa92f2`. La del artículo es `cb1d2da6`, con resultado
    idéntico: 4,163 kg de H₂, 60,00 kWh de la PEMFC y fin en 15,00 kWh. Cita la del artículo.
  - **A9 y A10** ya aparecen en parte en los slides 31 y 32 (R$ 217,31; los efectos se suman). Evita duplicar.
- Propón primero **qué auxiliares valen la pena** (no hace falta hacer los 15) y espera mi aprobación antes de diseñarlos.

### 3.3 Otras cosas que todavía están abiertas (pregúntame antes de tocar cualquiera)
1. **Artículo × deck:** el artículo dice 500 puntos de validación; lo grabado es 402. Tengo que corregir el artículo (no es tarea tuya,
   solo recuérdamelo).
2. **`AUDITORIA_BLOCO_I.md`:** quedan correcciones pendientes en los slides 4 y 6 (y la referencia [4] del slide 3). **No las apliques
   sin preguntarme.**
3. **Validar con el orientador** la redacción de la pregunta guía y de los objetivos (slides 7 y 36).
4. **Preparación de la defensa** (fuera del deck, si te lo pido):
   - ensayo cronometrado;
   - guion de la demo en vivo (abrir C4 sin solver → ejecutar C6 → 4,163 kg);
   - **plan B si falla internet** (video o capturas del aplicativo);
   - el guía `guia/` usa la numeración vieja.

## 4. Cómo trabajo contigo (sigue esto al pie de la letra)

**Flujo:**
1. Lee el material, dime en 3–5 líneas qué tiene que transmitir el slide y espera mi «ok».
2. Genera **3 propuestas distintas** (o 2 cuando haya poco margen). Revisa cada PNG tú mismo: nada superpuesto ni cortado, texto de las
   tarjetas ≥ 22 px. Muéstramelas lado a lado.
3. Yo elijo y pido ajustes. Itera **sobre la propuesta elegida sin cambiar lo que no pedí** (si pido cambiar el color, cambia solo el
   color).
4. Al aprobar:
   - copia a `slides/slideNN_aprovado.html`;
   - añádelo en `pptx/deck.py` con su fala en `NOTA_EXTRA`;
   - corre `python3 deck.py`;
   - actualiza `ROTEIRO.md`, `CONTINUAR.md` y `DESIGN.md`.
5. **No me entregues PDF/PPTX en cada slide** (gasta tokens). Solo cuando yo lo pida.

**Estilo (no negociable):**
- **Identidad:**
  - tipografía: Gelasio en títulos, Manrope en texto;
  - colores base: navy `#14213D`, teal `#1F7A6D`, tarjetas claras `#EEF3F2` con radio 24, gradiente SEEDS `#6DB527 → #1E8A72 → #0072BA`;
  - colores de los recursos: Solar `#D9A21B`, Eólica `#4C8DD6`, PEMFC `#1BA39C`, Batería `#7B6CF6`, Red `#E0524F`;
  - costo futuro `#C0532F`;
  - pie de página: logo UNILA + número grande (función `rodape(n)` en `gerar_slide8.py`).
- **Visual, poco texto, letra grande.** Las frases empiezan con mayúscula y llevan buen interlineado.
- **Nada que parezca hecho por IA:**
  - sin kicker en MAYÚSCULAS + título + subtítulo;
  - sin banda azul de resumen;
  - sin rótulos obvios;
  - sin íconos decorativos en listas;
  - sin subrayados de acento.
- Las figuras del artículo se reproducen **idénticas**. **Nunca dibujes ilustraciones figurativas a mano en SVG**: quedan horribles
  y ya las rechacé.
- **Datos solo de fuentes verificadas** (artículo, rodadas grabadas). Nunca inventes números, nombres ni procedencias. Marca
  «esquemático» cuando no sea un dato real.
- Las ecuaciones van en LaTeX, numeradas como en el artículo.
- Valoriza el trabajo (tono de defensa) sin esconder las limitaciones.

## 5. Contenido del ZIP

```
LEIA_PRIMEIRO_PROMPT.md         ← este archivo
referencias_citadas.md          ← qué referencia cita cada slide (29 en total)
articulo/tcc_texto_extraido.txt ← texto del artículo (apoyo; referencias NO confiables)
defesa_tcc/
  pptx/SEEDS_Defesa_TCC.pdf     ← DECK FINAL (míralo primero)
  pptx/deck.py                  ← orden, títulos y falas (fuente única) → genera deck.json
  pptx/exportar_deck.js, gerar_pptx.js ← exportación PDF/PPTX (Node + Playwright + pptxgenjs)
  ROTEIRO.md · DESIGN.md · CONTINUAR.md · ROTEIRO_DETALHADO_v1.md · AUDITORIA_BLOCO_I.md · PLANO_BLOCO_II.md
  capa/                         ← portada, sumario, fuentes (assets/fonts.css), logos
  slides/                       ← generadores gerar_slide*.py, HTML aprobados, render.js, tex2svg.js, assets/, dados/
  slides/seeds_fig/             ← extractor de figuras del motor gráfico del SEEDS (solo funciona dentro del repositorio)
  guia/                         ← guía antiguo (numeración vieja)
dados_rodadas/                  ← marcos de datos grabados de las rodadas C1–C6 (JSON «seeds2-trama-frame»), por si un auxiliar los necesita
```

**Archivos clave para reutilizar:**
- `slides/gerar_slide16.py`: CSS común, `div`, `T`, íconos `ic`, colores.
- `slides/gerar_slide8.py`: `rodape(n)`.
- `slides/gerar_slide36.py` y `gerar_slide38.py`: los ejemplos más recientes de tarjetas.

## 6. Cómo ejecutar

Desde `defesa_tcc/slides`:
```bash
PYTHONDONTWRITEBYTECODE=1 python3 gerar_slide38.py
```
```bash
node render.js S38_agradecimentos.html
```
El primero genera el HTML; el segundo lo renderiza a `png/S38_agradecimentos.png`. `render.js` necesita
`require('playwright')` con Chromium.

- **Sin Node/MathJax:** las ecuaciones quedan en caché en `slides/tex_cache_slide8.json` y los generadores funcionan igual.
- **Sin Playwright:** puedes instalarlo con `pip install playwright && python -m playwright install chromium` y hacer un render
  equivalente en Python (viewport 1920×1080, esperar `document.fonts.ready`). Si no hay red, entrégame el HTML para que lo abra en el
  navegador.
- **Deck completo:**
  ```bash
  cd defesa_tcc/pptx && python3 deck.py && node exportar_deck.js
  ```
  Esto genera `img_hd/` y el PDF, y necesita `pdfunite`. Después viene `node gerar_pptx.js <apply_theme.js del skill pptx>`, que necesita
  `pptxgenjs` y `sharp`. El número de página de cada HTML lo reemplaza la exportación según el orden de `deck.py`.
- Las rutas son relativas (`../capa/assets/...`): **mantén la estructura de carpetas del ZIP**.

**Empieza así:** abre el PDF del deck, lee `CONTINUAR.md` y `referencias_citadas.md`, pídeme el PDF del artículo si no lo
adjunté, y propón cómo distribuir las 29 referencias (en 1 o 2 slides) antes de diseñar.
