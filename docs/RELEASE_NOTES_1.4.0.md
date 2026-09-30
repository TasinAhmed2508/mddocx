# mddocx-native 1.4.0

Version 1.4 extends script-aware output beyond Bengali, CJK, and right-to-left text so
documents in every writing system the parser accepts keep the correct Word font slots
and direction.

## Every complex script gets the configured font

- The `w:cs` complex-script font slot now applies to Devanagari, Bengali, Gurmukhi,
  Gujarati, Oriya, Tamil, Telugu, Kannada, Malayalam, Sinhala, Thai, Lao, Tibetan,
  Myanmar, Khmer, Ethiopic, Mongolian, Syriac, Thaana, Arabic, and Hebrew.
- Set the font with `--complex-script-font NAME`, `RenderConfig.fonts.complex_script`,
  or a template style map.
- Left-to-right complex scripts such as Hindi, Tamil, and Thai receive the font slot
  without inheriting bidi paragraph direction.

## East Asian coverage

- CJK detection now covers the unified ideograph extension planes, Hangul Jamo and
  syllables, compatibility ideographs, Bopomofo, and halfwidth Katakana, so
  `--east-asia-font` reaches Chinese, Japanese, and Korean text of any length.

## Direction and fonts on every surface

Right-to-left direction and script fonts now reach surfaces that previously bypassed
them: the title page, abstract, table-of-contents title, captions, bibliography
heading and entries, headers, footers, footnotes, and endnotes. Centered title-page
lines keep their explicit center alignment instead of switching to right alignment.

## Bengali boundary unchanged

The Unicode-to-Bijoy pass remains limited to the `word/*.xml` output boundary and to
Bengali code points. Markdown and the canonical AST stay Unicode, English text keeps a
Latin font, and other scripts are never re-encoded. The isolated-vowel-mark guard that
prevents unbounded memory growth during Bijoy conversion is included in this release.

## Verification

`tests/test_multilingual_output.py` and the `tests/fixtures/multilingual/polyglot.md`
fixture cover script detection, font-slot selection, direction modes (`off`, `auto`,
`force`), native structure preservation, and the Unicode-to-Bijoy boundary for
headers, tables, and notes. The v1 Python entry points, CLI flags, and exit codes are
unchanged.
