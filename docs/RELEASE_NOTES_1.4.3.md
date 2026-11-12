# mddocx-native 1.4.3

This maintenance release speeds up wide tables, repeated equations, and paginated flowcharts.
The Markdown and AST render paths now share layout and DOCX finalization. Validation inspects
the XML parts it already parsed, and the compiler returns the DOCX bytes it just wrote.

Project builds with an explicit render configuration rebuild instead of reusing a cached
document made with another configuration. The first project build after upgrading also
refreshes the saved build state. Project sources and includes now use the same bounded Markdown
reader as single-file conversion.

The wheel and source archive are attached to this release. To upgrade from PyPI, run:

```shell
python -m pip install --upgrade mddocx-native
mddocx-native --version
```

See the [maintenance audit](https://github.com/TasinAhmed2508/mddocx/blob/v1.4.3/docs/MAINTENANCE_AUDIT_1.4.3.md)
and the [full changelog](https://github.com/TasinAhmed2508/mddocx/compare/v1.4.2...v1.4.3).
