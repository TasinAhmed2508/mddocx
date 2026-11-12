# mddocx-native 1.4.2 — Flowcharts, tables, and conversion safety

This release fixes missing flowchart and table content, improves mixed-language Bangla output,
and protects source files during conversion.

- Mermaid flowcharts retain labeled connections. Long flowcharts are split into overlapping
  panels, with branch conditions and multilingual node labels also available as editable text.
- HTML `<br>` tags in table cells become Word line breaks, and table headings stay with the
  first data row.
- The default Bangla font setting selects SutonnyMJ when installed, or an installed Unicode
  Bangla font otherwise. The guided theme menu no longer presents a separate Bangla choice.
- Conversion output and diagnostic files are checked against input and other protected files.
  Existing DOCX files are replaced only after a complete temporary output is written.
- Invalid project values produce clearer diagnostics, and batch and interactive conversions
  show warnings.
- Invalid inline math markers are preserved as text instead of interrupting conversion.

## Install from this GitHub release

```bash
python -m pip install --upgrade "https://github.com/TasinAhmed2508/mddocx/releases/download/v1.4.2/mddocx_native-1.4.2-py3-none-any.whl"
```

The `SutonnyMJ` font is not bundled. A document encoded for it needs that font on the computer
opening the document. The flowchart renderer supports a subset of Mermaid syntax.

**Full changelog:** https://github.com/TasinAhmed2508/mddocx/compare/v1.4.1...v1.4.2
