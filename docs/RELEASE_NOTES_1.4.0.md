# mddocx-native 1.4.0 — Multilingual script coverage

Version 1.4 completes the script-aware output boundary. Before this release, only Bengali, CJK
text, and right-to-left text received correct Word font slots and direction — and even those were
applied to body content only. Now every writing system the parser accepts keeps the correct font
slot, and direction reaches every text surface in the document.

**Upgrade if** you convert documents containing Arabic, Hebrew, Persian, Hindi, Bengali, Punjabi,
Gujarati, Oriya, Tamil, Telugu, Kannada, Malayalam, Sinhala, Thai, Lao, Tibetan, Burmese, Khmer,
Amharic, Mongolian, Chinese, Japanese, or Korean text — or any mix of them in one file.

**Full Changelog**: https://github.com/TasinAhmed2508/mddocx/compare/v1.3.1...v1.4.0

## At a glance: 1.3.1 → 1.4.0

| Capability | 1.3.1 | 1.4.0 |
|---|---|---|
| Complex-script font slot (`w:cs`) | Bengali only | Every Word complex script (see the list below) |
| CJK font slot (`w:eastAsia`) | Basic ideographs, Hiragana/Katakana, Hangul syllables | Adds extension planes, Hangul Jamo, compatibility ideographs, Bopomofo, halfwidth Katakana |
| Arabic/Hebrew paragraph direction | Body paragraphs only | Adds title page, abstract, table-of-contents title, captions, bibliography, headers, footers, and notes |
| Arabic/Hebrew run direction | Body runs only | Adds header/footer, caption, bibliography, footnote, and endnote runs |
| Centered RTL title page | Lost center alignment to the direction pass | Keeps explicit center alignment with bidi direction |
| RTL bibliography hyperlinks | No complex-script font or run direction | Emitted with `w:cs` and `w:rtl` |
| Multilingual regression coverage | Bengali layout tests only | 62 dedicated tests plus a polyglot fixture covering 18 scripts |

## What changed

### 1. The complex-script font slot covers every complex script

`--complex-script-font` and `RenderConfig.fonts.complex_script` now apply to Devanagari, Bengali,
Gurmukhi, Gujarati, Oriya, Tamil, Telugu, Kannada, Malayalam, Sinhala, Thai, Lao, Tibetan, Myanmar,
Khmer, Ethiopic, Mongolian, Syriac, Thaana, Arabic, and Hebrew.

Left-to-right complex scripts receive the font slot **without** inheriting bidi direction. In 1.3.1
Hindi, Tamil, Thai, and similar text silently fell back to the Latin body font.

### 2. CJK detection covers the full East Asian range

Chinese, Japanese, and Korean text now uses the `--east-asia-font` slot for the unified ideograph
extension planes, Hangul Jamo and syllables, compatibility ideographs, Bopomofo, and halfwidth
Katakana. Large East Asian documents no longer lose the configured font in these ranges.

### 3. Direction and fonts reach every text surface

The title page, abstract, table-of-contents title, captions, bibliography heading and entries,
headers, footers, footnotes, and endnotes previously bypassed script handling. They now receive the
same paragraph direction, run direction, and font slots as body text. Bibliography hyperlinks in
right-to-left entries are emitted with the correct complex-script font and run direction.

### 4. Bengali behavior is unchanged

The Unicode-to-Bijoy pass still runs only at the `word/*.xml` boundary and only for Bengali code
points. Markdown and the canonical AST stay Unicode, English keeps a Latin font, other scripts are
never re-encoded, and the guard that prevents unbounded memory growth on isolated Bengali vowel
marks is included in this release.

## What improved

- **Hindi, Tamil, Telugu, Kannada, Malayalam, Punjabi, Gujarati, Oriya, Sinhala, Thai, Lao,
  Tibetan, Burmese, Khmer, Amharic, Mongolian, Syriac, and Thaana** documents now render with the
  complex-script font you configure instead of a Latin substitute.
- **Arabic and Hebrew headings, titles, abstracts, captions, references, headers, footers, and
  notes** are right-to-left in Word, not left-to-right Latin paragraphs.
- **Mixed-script documents** — for example a report with Bengali, Arabic, Chinese, and English in
  the same file — keep each script in its own font slot while English stays Latin.
- **Bengali documents** keep the 1.3.1 behavior, including SutonnyMJ/Bijoy output, identity forms,
  photo boxes, and merged layout tables.

## How to use it

```bash
# Complex scripts (Indic, Southeast Asian, Arabic, Hebrew) and CJK
mddocx report.md -o report.docx --complex-script-font "Nirmala UI" --east-asia-font "Microsoft YaHei"

# Arabic or Hebrew document, forced right-to-left
mddocx arabic-report.md -o arabic-report.docx --rtl force

# Bengali document with the legacy SutonnyMJ output boundary
mddocx bangla.md -o bangla.docx --theme bengali-document
```

```python
from mddocx import RenderConfig, render

config = RenderConfig(rtl="auto")
config.fonts.complex_script = "Nirmala UI"
config.fonts.east_asia = "Microsoft YaHei"
config.fonts.bengali = "Nirmala UI"  # Unicode Bangla output instead of Bijoy
render("report.md", "report.docx", config=config)
```

## Compatibility

- The v1 Python API, CLI command names, and exit codes are unchanged; no migration is required.
- `rtl` accepts `off`, `auto` (default), and `force` exactly as before.
- Script detection, font-slot selection, and direction are covered by
  `tests/test_multilingual_output.py` and the `tests/fixtures/multilingual/polyglot.md` fixture.

## Verification

`tests/test_multilingual_output.py` adds 62 tests: complex-script detection across 18 scripts, CJK
plane detection, RTL truth tables, the `off`/`auto`/`force` direction modes, per-run font-slot
selection, native structure preservation in a polyglot document, the Unicode-to-Bijoy boundary for
headers, tables, and notes, and CLI flag plumbing. The release candidate passed the full suite,
Ruff, mypy, `mddocx doctor`, the performance gate, a wheel and sdist build with `twine check`, and a
clean-environment wheel smoke run (render, `inspect --strict`, `math-check --strict`, and the public
API manifest).

## Follow-up

A follow-up patch adds an ASCII fast path to script classification, so Latin-only documents pay
essentially nothing for the new per-run font and direction logic, and it splits the large-document
benchmark budget per platform (30 seconds on Linux, 60 seconds on macOS and Windows runners, which
measured 33.7 s and 44.7 s for the 100-section corpus).
