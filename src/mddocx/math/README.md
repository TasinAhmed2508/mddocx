# Math pipeline

The math package converts Markdown TeX into editable Word OMML. `normalize.py`
performs conservative compatibility repairs, `sidecar.py` defines the optional
MathJax JSONL protocol, `converter.py` selects MathJax, `latex2mathml`, then the
built-in engine, and `validation.py` validates both intermediate MathML and OMML.

Conversion is local and deterministic. Unsupported expressions raise to the
renderer, which applies the configured editable-text fallback or strict policy.

The bundled sidecar supports `\ce` for reactions and `\pu` for physical units.
Standard reaction and equilibrium arrows use portable Unicode glyphs. Specialty
bonds and unequal equilibrium arrows without a Word mapping use the math failure
policy. Chemistry macros require the bundled MathJax runtime.

To regenerate the sidecar, stage `scripts/mathjax-sidecar.mjs` in a temporary
directory and run the following commands there. Copy `mddocx-mathjax.mjs` back
to `src/mddocx/math/bin/`.

```console
npm install --save-exact @mathjax/src@4.1.3 mhchemparser@4.2.1 esbuild@0.27.0
npx esbuild ./mathjax-sidecar.mjs --bundle --platform=node --format=esm --outfile=mddocx-mathjax.mjs
```
