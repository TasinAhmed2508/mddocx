import readline from 'node:readline';
import {mathjax} from '@mathjax/src/js/mathjax.js';
import {TeX} from '@mathjax/src/js/input/tex.js';
import {liteAdaptor} from '@mathjax/src/js/adaptors/liteAdaptor.js';
import {RegisterHTMLHandler} from '@mathjax/src/js/handlers/html.js';
import {SerializedMmlVisitor} from '@mathjax/src/js/core/MmlTree/SerializedMmlVisitor.js';
import {STATE} from '@mathjax/src/js/core/MathItem.js';
import '@mathjax/src/js/input/tex/base/BaseConfiguration.js';
import '@mathjax/src/js/input/tex/ams/AmsConfiguration.js';
import '@mathjax/src/js/input/tex/newcommand/NewcommandConfiguration.js';

const adaptor = liteAdaptor({fontSize: 16});
RegisterHTMLHandler(adaptor);
const tex = new TeX({
  packages: ['base', 'ams', 'newcommand'],
  formatError(_jax, error) { throw error; },
});
const document = mathjax.document('', {InputJax: tex});
const visitor = new SerializedMmlVisitor();
const lines = readline.createInterface({input: process.stdin, crlfDelay: Infinity});

for await (const line of lines) {
  if (!line.trim()) continue;
  let request;
  try {
    request = JSON.parse(line);
    if (request.protocol !== 1) throw new Error('Unsupported protocol');
    if (typeof request.tex !== 'string') throw new Error('tex must be a string');
    if (request.tex.length > Math.min(request.max_expression_chars || 100000, 100000)) {
      throw new Error('Equation exceeds maximum length');
    }
    const tree = document.convert(request.tex, {
      display: Boolean(request.display), em: 16, ex: 8,
      containerWidth: 1280, end: STATE.CONVERT,
    });
    tree.walkTree((node) => {
      node.attributes?.unset('data-latex');
      node.attributes?.unset('data-latex-item');
    });
    const mathml = visitor.visitTree(tree, document);
    process.stdout.write(JSON.stringify({
      protocol: 1, version: mathjax.version, mathml,
      normalized_tex: request.tex, warnings: [], packages: ['base', 'ams', 'newcommand'],
    }) + '\n');
  } catch (error) {
    process.stdout.write(JSON.stringify({
      protocol: 1, error: error instanceof Error ? error.message : String(error),
    }) + '\n');
  }
}
