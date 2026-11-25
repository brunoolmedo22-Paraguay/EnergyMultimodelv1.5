// Gera SEEDS_Defesa_TCC.pptx: capa e sumário aprovados (formas nativas) + slides 3–6 aprovados (imagem 3840 × 2160
// de img_hd/, gerada por exportar_bloco1.js a partir dos HTML aprovados) + slides 7–27 em branco (com rodapé).
// Uso: NODE_PATH=<node_modules com pptxgenjs e sharp> node gerar_pptx.js <apply_theme.js>
// Medidas do canvas de referência (1920 × 1080 px) convertidas: 1 px = 1/144 pol. = 0,5 pt.
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");

const AQUI = __dirname;
const A = (f) => path.join(AQUI, "..", "capa", "assets", f);
const OUT = path.join(AQUI, "SEEDS_Defesa_TCC.pptx");
const TMP = path.join(AQUI, ".img"); fs.mkdirSync(TMP, { recursive: true });
const P = (px) => px / 144;          // px → polegadas
const PT = (px) => px / 2;           // px → pontos

const THEME = {
  name: "SEEDS Defesa", headFontFace: "Georgia", bodyFontFace: "Calibri",
  colors: { dk1: "14213D", lt1: "FFFFFF", dk2: "4A5568", lt2: "EEF3F2", accent1: "1F7A6D", accent2: "0072BA",
            accent3: "6DB527", accent4: "C1FF72", accent5: "C0532F", accent6: "DCE3E2", hlink: "1F7A6D", folHlink: "4A5568" },
};
const NAVY = "14213D", SLATE = "4A5568", TEAL = "1F7A6D", LIGHT = "EEF3F2", LIME = "C1FF72";
const SERIF = "Georgia", SANS = "Calibri";

const STOPS = [[0, [0x6D, 0xB5, 0x27]], [0.55, [0x1E, 0x8A, 0x72]], [1, [0x00, 0x72, 0xBA]]];
function cor(t) {
  for (let i = 0; i < STOPS.length - 1; i++) {
    const [a, ca] = STOPS[i], [b, cb] = STOPS[i + 1];
    if (t <= b) { const u = (t - a) / (b - a); return ca.map((x, j) => Math.round(x + (cb[j] - x) * u).toString(16).padStart(2, "0")).join("").toUpperCase(); }
  }
  return "0072BA";
}

// ------------------------------------------------------------------ imagens auxiliares
async function gradiente(nome, w, h, raio) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#6DB527"/><stop offset=".55" stop-color="#1E8A72"/><stop offset="1" stop-color="#0072BA"/></linearGradient></defs><rect width="${w}" height="${h}" rx="${raio}" fill="url(#g)"/></svg>`;
  const f = path.join(TMP, nome); await sharp(Buffer.from(svg)).png().toFile(f); return f;
}
const ICON = {
  sun: '<circle cx="20" cy="20" r="7" fill="none" stroke="C" stroke-width="3"/><g stroke="C" stroke-width="3" stroke-linecap="round"><path d="M20 3v5M20 32v5M3 20h5M32 20h5M8 8l3.5 3.5M28.5 28.5L32 32M8 32l3.5-3.5M28.5 11.5L32 8"/></g>',
  wind: '<g fill="none" stroke="C" stroke-width="3" stroke-linecap="round"><path d="M20 18v19M20 18V4M20 18l12 7M20 18L8 25"/></g><circle cx="20" cy="18" r="3" fill="C"/>',
  bat: '<rect x="6" y="11" width="25" height="18" rx="3" fill="none" stroke="C" stroke-width="3"/><rect x="32" y="16" width="3" height="8" fill="C"/><rect x="10" y="15" width="11" height="10" fill="C"/>',
  grid: '<g fill="none" stroke="C" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M14 37L20 4l6 33M10 12h20M8 20h24M16 29h8"/></g>',
  load: '<g fill="none" stroke="C" stroke-width="3" stroke-linejoin="round"><path d="M6 19L20 7l14 12v16H6z"/><path d="M17 35v-9h6v9"/></g>',
};
async function icone(k, c) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320" viewBox="0 0 40 40">${ICON[k].replace(/"C"/g, `"#${c}"`)}</svg>`;
  const f = path.join(TMP, `ic_${k}.png`); await sharp(Buffer.from(svg)).png().toFile(f); return f;
}

// ------------------------------------------------------------------ roteiro (notas dos slides em branco)
const SECOES = [
  ["I · Contexto e objetivos", [[3, "Contexto"], [4, "Decisões com consequências futuras"], [5, "Trabalhos relacionados"], [6, "Objetivos e contribuições"]]],
  ["II · Fundamentação teórica e desenvolvimento do SEEDS", [[7, "Modelagem dos recursos energéticos"], [8, "Programação linear inteira mista (MILP)"], [9, "Controle preditivo baseado em modelo (MPC)"], [10, "Coordenação hierárquica e valor futuro"], [11, "Arquitetura do SEEDS"], [12, "Representação energética comum"], [13, "Gerenciamento energético hierárquico no SEEDS"], [14, "Verificação e fluxo de execução"]]],
  ["III · Estudos de caso", [[15, "Estudos de caso"], [16, "Microrrede industrial CT-046 (C1–C4)"], [17, "Embarcação híbrida EMB-H2-120 (C5–C6)"]]],
  ["IV · Demonstração do SEEDS", [[18, "Demonstração do SEEDS"]]],
  ["V · Resultados", [[19, "Resultados — custos operacionais (C1–C4)"], [20, "Resultados — operação do armazenamento"], [21, "Resultados — coordenação hierárquica"], [22, "Resultados — embarcação híbrida (C5)"], [23, "Resultados — papel do armazenamento (C4, C5 e C6)"], [24, "Expansibilidade e desempenho computacional"]]],
  ["VI · Conclusões e perspectivas", [[25, "Conclusões"], [26, "Perspectivas"], [27, "Agradecimentos"]]],
];

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";                 // 13,333 × 7,5 pol.
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  pres.title = "SEEDS — Defesa de TCC";
  pres.author = "Bruno Manuel Olmedo Chávez";
  const C = pres.SchemeColor;

  const BUS = await gradiente("barramento.png", 2550, 36, 18);
  const TICK = await gradiente("traco.png", 264, 30, 15);
  const UNILA = A("unila.png"), SEEDS = A("seeds.png");
  const UNILA_AR = 951 / 591, SEEDS_AR = 994 / 309;

  // ---------------------------------------------------------------- layouts
  pres.defineSlideMaster({ title: "CAPA", background: { color: "FFFFFF" }, objects: [] });
  // slides aprovados como imagem de página inteira (rodapé e número já estão na imagem)
  pres.defineSlideMaster({ title: "IMAGEM", background: { color: "FFFFFF" }, objects: [] });
  const NOTAS = JSON.parse(fs.readFileSync(path.join(AQUI, "notas_bloco1.json"), "utf8"));

  const yFt = 1080 - 34 - 28;                  // linha de base aproximada do rodapé
  pres.defineSlideMaster({
    title: "CONTEUDO",
    background: { color: "FFFFFF" },
    margin: [P(130), P(110), P(130), P(110)],
    objects: [
      { line: { x: P(110), y: P(968), w: P(1700), h: 0, line: { color: "E6ECEB", width: 0.75 } } },
      { image: { path: UNILA, x: P(110), y: P(990), w: P(56 * UNILA_AR), h: P(56) } },
      { line: { x: P(226), y: P(1003), w: 0, h: P(30), line: { color: "DCE3E2", width: 0.75 } } },
      { text: { text: "Engenharia de Energia · ILATIT", options: { x: P(240), y: P(998), w: P(260), h: P(40), margin: 0, fontFace: SANS, fontSize: 9, color: "7B8794", valign: "middle" } } },
      { line: { x: P(506), y: P(1003), w: 0, h: P(30), line: { color: "DCE3E2", width: 0.75 } } },
      // "Defesa de TCC" (negrito) mede 105 px a 9 pt em Calibri/Carlito; o restante começa logo depois
      { text: { text: "Defesa de TCC", options: { x: P(520), y: P(998), w: P(112), h: P(40), margin: 0, fontFace: SANS, fontSize: 9, bold: true, color: "5B6675", valign: "middle" } } },
      { text: { text: "· Bruno Manuel Olmedo Chávez", options: { x: P(627), y: P(998), w: P(420), h: P(40), margin: 0, fontFace: SANS, fontSize: 9, color: "7B8794", valign: "middle" } } },
      { image: { path: TICK, x: P(1766), y: P(982), w: P(44), h: P(5) } },
      { placeholder: { options: { name: "title", type: "title", x: P(110), y: P(70), w: P(1700), h: P(100), fontFace: SERIF, fontSize: 30, bold: true, color: NAVY, align: "left", valign: "middle", margin: 0 }, text: "" } },
    ],
    slideNumber: { x: P(1610), y: P(992), w: P(200), h: P(52), fontFace: SERIF, fontSize: 20, bold: true, color: NAVY, align: "right", margin: 0 },
  });

  // ---------------------------------------------------------------- 1 · capa
  pres.addSection({ title: "Abertura" });
  let s = pres.addSlide({ masterName: "CAPA", sectionTitle: "Abertura" });
  s.addImage({ path: UNILA, x: P(110), y: P(60), w: P(150 * UNILA_AR), h: P(150), objectName: "Logo UNILA" });
  s.addText("Foz do Iguaçu, 9 de dezembro de 2026", { x: P(1310), y: P(112), w: P(500), h: P(40), margin: 0, align: "right", fontFace: SANS, fontSize: 11, color: SLATE, isTextBox: true, objectName: "Data" });
  s.addText("SEEDS: Desenvolvimento e Avaliação de um Simulador Modular Expansível com Gerenciamento Energético Hierárquico Baseado em MILP–MPC",
    { x: P(110), y: P(250), w: P(1700), h: P(240), margin: 0, fontFace: SERIF, fontSize: 31, bold: true, color: NAVY, valign: "top", lineSpacingMultiple: 1.1, isTextBox: true, objectName: "Título" });
  s.addText([{ text: "Defesa de TCC", options: { fontSize: 23, bold: true, color: TEAL, breakLine: true } },
             { text: "Engenharia de Energia · ILATIT", options: { fontSize: 12, italic: true, color: SLATE } }],
    { x: P(110), y: P(612), w: P(820), h: P(110), margin: 0, fontFace: SERIF, valign: "top", paraSpaceAfter: 4, isTextBox: true, objectName: "Defesa de TCC" });
  s.addShape(pres.shapes.LINE, { x: P(110), y: P(749), w: P(846), h: 0, line: { color: TEAL, width: 1, dashType: "dash" }, objectName: "Conexão tracejada" });
  s.addText([{ text: "Bruno Manuel Olmedo Chávez", options: { fontSize: 19, bold: true, color: NAVY, breakLine: true } },
             { text: "Orientador: ", options: { fontSize: 12.5, bold: true, color: "2B3648" } }, { text: "Prof. Dr. Jorge Javier Gimenez Ledesma", options: { fontSize: 12.5, color: "2B3648", breakLine: true } },
             { text: "Coorientador: ", options: { fontSize: 12.5, bold: true, color: "2B3648" } }, { text: "Me. Daniel Firmo Kazay", options: { fontSize: 12.5, color: "2B3648" } }],
    { x: P(110), y: P(772), w: P(840), h: P(150), margin: 0, fontFace: SERIF, valign: "top", paraSpaceAfter: 6, isTextBox: true, objectName: "Autor e orientadores" });
  s.addImage({ path: SEEDS, x: P(1160), y: P(548), w: P(460), h: P(460 / SEEDS_AR), objectName: "Logo SEEDS" });
  s.addShape(pres.shapes.LINE, { x: P(1385), y: P(700), w: 0, h: P(40), line: { color: TEAL, width: 1, dashType: "dash" }, objectName: "Conexão logo–barramento" });
  s.addImage({ path: BUS, x: P(960), y: P(744), w: P(850), h: P(12), objectName: "Barramento" });
  const NOS = [["sun", "D9A21B", "Solar", "in"], ["wind", "4C8DD6", "Eólica", "in"], ["h2", "1BA39C", "PEMFC", "in"],
               ["bat", "7B6CF6", "Bateria", "bi"], ["grid", "E0524F", "Rede", "bi"], ["load", NAVY, "Demanda", "out"]];
  const yb = 750, cy = 865;
  for (let i = 0; i < NOS.length; i++) {
    const [k, c, nome, sent] = NOS[i];
    const cx = 960 + 850 * (i + 1) / 7;
    s.addShape(pres.shapes.LINE, { x: P(cx), y: P(yb + 6), w: 0, h: P(cy - 36 - yb - 6), line: { color: c, width: 1.5 }, objectName: `Haste ${nome}` });
    const m = (yb + 6 + cy - 36) / 2;
    const seta = (y, rot) => s.addShape(pres.shapes.ISOSCELES_TRIANGLE, { x: P(cx - 7), y: P(y - 6), w: P(14), h: P(12), rotate: rot, fill: { color: c }, line: { color: c, width: 0 }, objectName: `Sentido ${nome}` });
    if (sent === "in") seta(m, 0); else if (sent === "out") seta(m, 180); else { seta(m - 9, 0); seta(m + 9, 180); }
    s.addShape(pres.shapes.OVAL, { x: P(cx - 7), y: P(yb - 7), w: P(14), h: P(14), fill: { color: "FFFFFF" }, line: { color: c, width: 1.5 }, objectName: `Junção ${nome}` });
    s.addShape(pres.shapes.OVAL, { x: P(cx - 36), y: P(cy - 36), w: P(72), h: P(72), fill: { color: "FFFFFF" }, line: { color: c, width: 1.5 }, objectName: `Nó ${nome}` });
    if (k === "h2") s.addText([{ text: "H" }, { text: "2", options: { subscript: true } }], { x: P(cx - 30), y: P(cy - 20), w: P(60), h: P(40), margin: 0, align: "center", valign: "middle", fontFace: SANS, fontSize: 11, bold: true, color: c, isTextBox: true, objectName: "Ícone PEMFC" });
    else s.addImage({ path: await icone(k, c), x: P(cx - 20), y: P(cy - 20), w: P(40), h: P(40), objectName: `Ícone ${nome}` });
    s.addText(nome, { x: P(cx - 70), y: P(cy + 44), w: P(140), h: P(34), margin: 0, align: "center", fontFace: SANS, fontSize: 10, color: SLATE, isTextBox: true, objectName: `Rótulo ${nome}` });
  }
  s.addNotes("Capa. Abertura: \"Bom dia. Vou apresentar o SEEDS, um simulador modular de microrredes com gerenciamento energético hierárquico, desenvolvido com o professor Jorge e com o Daniel.\"");

  // ---------------------------------------------------------------- 2 · sumário
  s = pres.addSlide({ masterName: "CONTEUDO", sectionTitle: "Abertura" });
  s.addText("Sumário", { placeholder: "title", align: "left" });
  const TIT = ["Contexto e objetivos", "Fundamentação teórica", "Desenvolvimento do\u00A0SEEDS", "Estudos de caso", "Demonstração do\u00A0SEEDS", "Resultados", "Conclusões e perspectivas"];
  const x0 = 110, x1 = 1810, w = 410, h = 250, gap = (x1 - x0 - 4 * w) / 3, yU = 205, yB = 545, yD = 635, H = 40, d = 20, g = 8;
  const up = [0, 1, 2, 3].map((k) => x0 + w / 2 + k * (w + gap));
  const dn = up.slice(0, 3).map((a, k) => (a + up[k + 1]) / 2);
  const xs = [up[0], dn[0], up[1], dn[1], up[2], dn[2], up[3]];
  const bnd = [x0, ...xs.slice(0, -1).map((a, k) => (a + xs[k + 1]) / 2 - d / 2), x1 - d];
  for (let k = 0; k < 7; k++) {
    const a = bnd[k] + (k ? g / 2 : 0), b = bnd[k + 1] - (k < 6 ? g / 2 : 0), c = cor((xs[k] - x0) / (x1 - x0));
    s.addShape(k ? pres.shapes.CHEVRON : pres.shapes.PENTAGON, { x: P(a), y: P(yB - H / 2), w: P(b + d - a), h: P(H), fill: { color: c }, line: { color: c, width: 0 }, objectName: `Etapa ${k + 1}` });
  }
  for (let k = 0; k < 7; k++) {
    const x = xs[k], c = cor((x - x0) / (x1 - x0)), acima = k % 2 === 0, dm = k === 4, top = acima ? yU : yD;
    // conector (10 px)
    s.addShape(pres.shapes.LINE, acima ? { x: P(x), y: P(yU + h - 2), w: 0, h: P(yB - H / 2 - yU - h + 4), line: { color: c, width: 5 } }
                                       : { x: P(x), y: P(yB + H / 2 - 2), w: 0, h: P(yD - yB - H / 2 + 4), line: { color: c, width: 5 } });
    s.addShape(pres.shapes.OVAL, { x: P(x - 7), y: P(yB - 7), w: P(14), h: P(14), fill: { color: "FFFFFF" }, line: { color: "FFFFFF", width: 0 }, objectName: `Nó ${k + 1}` });
    // cartão: base colorida + face clara deslocada 6 px (borda de 6 px embaixo ou em cima)
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: P(x - w / 2), y: P(top), w: P(w), h: P(h), rectRadius: P(24), fill: { color: c }, line: { color: c, width: 0 }, objectName: `Cartão ${k + 1} borda` });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: P(x - w / 2), y: P(acima ? top : top + 6), w: P(w), h: P(h - 6), rectRadius: P(24),
      fill: { color: dm ? NAVY : LIGHT }, line: { color: dm ? NAVY : LIGHT, width: 0 }, objectName: `Cartão ${k + 1}` });
    const yi = acima ? top : top + 6;
    s.addText(String(k + 1).padStart(2, "0"), { x: P(x - w / 2 + 34), y: P(yi + 22), w: P(220), h: P(110), margin: 0, fontFace: SERIF, fontSize: 48, bold: true, color: dm ? LIME : c, valign: "top", isTextBox: true, objectName: `Número ${k + 1}` });
    s.addText(TIT[k], { x: P(x - w / 2 + 34), y: P(yi + 120), w: P(w - 58), h: P(h - 6 - 150), margin: 0, fontFace: SERIF, fontSize: 17, bold: true, color: dm ? "FFFFFF" : NAVY, valign: "bottom", lineSpacingMultiple: 1.05, isTextBox: true, objectName: `Título ${k + 1}` });
    if (dm) {
      s.addShape(pres.shapes.OVAL, { x: P(x + w / 2 - 136), y: P(yi + 33), w: P(24), h: P(24), fill: { color: LIME, transparency: 80 }, line: { color: LIME, width: 0 }, objectName: "Halo ao vivo" });
      s.addShape(pres.shapes.OVAL, { x: P(x + w / 2 - 130), y: P(yi + 39), w: P(12), h: P(12), fill: { color: LIME }, line: { color: LIME, width: 0 }, objectName: "Ponto ao vivo" });
      s.addText("ao vivo", { x: P(x + w / 2 - 108), y: P(yi + 28), w: P(90), h: P(34), margin: 0, fontFace: SANS, fontSize: 10.5, bold: true, color: LIME, valign: "middle", isTextBox: true, objectName: "Ao vivo" });
    }
  }
  s.addNotes("Sumário: sete seções; a 05 é a demonstração ao vivo (reprodução da configuração C6).");

  // ---------------------------------------------------------------- 3–27 · em branco (rodapé + notas com o título planejado)
  for (const [secao, slides] of SECOES) {
    pres.addSection({ title: secao });
    for (const [n, t] of slides) {
      const hd = path.join(AQUI, "img_hd", `slide${String(n).padStart(2, "0")}.png`);
      if (fs.existsSync(hd)) {
        const si = pres.addSlide({ masterName: "IMAGEM", sectionTitle: secao });
        si.addImage({ path: hd, x: 0, y: 0, w: 13.333, h: 7.5, objectName: `Slide ${n} — ${t}`, altText: `Slide ${n}: ${t}` });
        si.addNotes(NOTAS[String(n)] || t);
        continue;
      }
      const sl = pres.addSlide({ masterName: "CONTEUDO", sectionTitle: secao });
      sl.addNotes(`Slide ${n} — título planejado: ${t}. (Em branco; conteúdo a definir — ver docs/defesa_tcc/ROTEIRO.md.)`);
    }
  }

  await pres.writeFile({ fileName: OUT });
  const { applyTheme } = require(process.argv[2]);
  await applyTheme(OUT, THEME);
  fs.rmSync(TMP, { recursive: true, force: true });
  console.log("ok", OUT);
})();
