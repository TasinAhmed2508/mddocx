# Math pipeline

The math package converts Markdown TeX into editable Word OMML. `normalize.py`
performs conservative compatibility repairs, `sidecar.py` defines the optional
MathJax JSONL protocol, `converter.py` selects MathJax, `latex2mathml`, then the
built-in engine, and `validation.py` validates both intermediate MathML and OMML.

Conversion is local and deterministic. Unsupported expressions raise to the
renderer, which applies the configured editable-text fallback or strict policy.
