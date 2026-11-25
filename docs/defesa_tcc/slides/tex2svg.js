// Requer mathjax-full@3.2.2 (npm). Uso: echo {"id":"tex"} | NODE_PATH=<node_modules> node tex2svg.js
// Lê JSON {id: tex} do stdin e devolve JSON {id: svg} (MathJax 3, saída SVG autocontida, fontCache local).
const { mathjax } = require('mathjax-full/js/mathjax.js');
const { TeX } = require('mathjax-full/js/input/tex.js');
const { SVG } = require('mathjax-full/js/output/svg.js');
const { liteAdaptor } = require('mathjax-full/js/adaptors/liteAdaptor.js');
const { RegisterHTMLHandler } = require('mathjax-full/js/handlers/html.js');
const { AllPackages } = require('mathjax-full/js/input/tex/AllPackages.js');
const adaptor = liteAdaptor(); RegisterHTMLHandler(adaptor);
const doc = mathjax.document('', { InputJax: new TeX({ packages: AllPackages }), OutputJax: new SVG({ fontCache: 'local' }) });
let inp = ''; process.stdin.on('data', d => inp += d).on('end', () => {
  const src = JSON.parse(inp), out = {};
  for (const [k, tex] of Object.entries(src)) {
    const node = doc.convert(tex, { display: true });
    out[k] = adaptor.innerHTML(node);
  }
  process.stdout.write(JSON.stringify(out));
});
