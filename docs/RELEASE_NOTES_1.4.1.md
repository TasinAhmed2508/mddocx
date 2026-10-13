# mddocx-native 1.4.1 — Install diagnostics and collision safety

Version 1.4.1 fixes the failures that happen *around* the conversion: an install that silently
resolves to a different project, a documented command that did not exist in the published wheel,
an optional engine that was reported as available when it could not run, and Bangla output that
quietly produced unreadable glyphs on a machine without the configured font.

**Upgrade if** you installed 1.4.0, if you convert Bangla documents, if you rely on equations
without Node.js installed, or if anything on the machine might have pulled in the unrelated PyPI
project named `mddocx`.

**Full Changelog**: https://github.com/TasinAhmed2508/mddocx/compare/v1.4.0...v1.4.1

## At a glance: 1.4.0 → 1.4.1

| Situation | 1.4.0 | 1.4.1 |
|---|---|---|
| The unrelated PyPI `mddocx` is also installed | Both projects overwrite each other; `mddocx` silently runs the other tool | `mddocx` warns with the repair commands, `mddocx doctor` fails with the same diagnosis, and `mddocx-native` refuses rather than running a mixed install |
| `python -m mddocx` after a `PATH` problem | `No module named mddocx.__main__` | Works; the console-script fallback documented in the README exists |
| MathJax sidecar present but Node.js missing | Reported as available; equations fell back silently | Reported as unavailable with the reason, and the engine that actually ran is named |
| Equation engine on a plain install | `mddocx-basic` when no Node.js is present | A real engine is always installed (`latex2mathml` is now a core dependency) |
| Bangla font not installed | Bijoy glyphs written anyway, unreadable in Word | `FONT301` warning with the options, or `--bengali-font auto` to keep Unicode and use an installed font |
| Convert command with no arguments on a terminal | argparse usage error, exit 2 | Opens the guided console; non-interactive callers keep the exit-2 usage error |
| Recoverable warnings | Collected, never shown | Printed to stderr during a conversion |
| Installing optional features | Four extras to choose from | `mddocx-native[all]`, plus `[mathjax]` for a Node.js runtime |
| Document with no Bangla text | Every Word XML part re-parsed and the package rebuilt | The Bangla pass is skipped entirely |

## What changed

### 1. A conflicting install is detected instead of silently winning

The PyPI project named `mddocx` ships the same `mddocx` import package and the same `mddocx`
console script as this distribution. When both are installed they share one directory, so one
project's files overwrite the other's — including `mddocx/cli.py`, which every entry point imports.

- `mddocx` warns on stderr with the exact uninstall and reinstall commands.
- `mddocx doctor` lists the conflict and exits 2.
- `mddocx-native` is a new command whose launcher lives outside the shared package, so it cannot
  be overwritten. It identifies the installed package by its own API, not by version metadata, and
  refuses to run a mixed installation with the repair commands. Set
  `MDDOCX_ALLOW_IMPORT_CONFLICT=1` to bypass the refusal.

The plain `mddocx` command itself cannot be protected, because the other project installs that
script name too; `mddocx-native` is the entry point to use when a machine might have both.

### 2. `python -m mddocx` works in the published artifacts

The 1.4.0 wheel and sdist shipped without `mddocx/__main__.py`, so the fallback the README
recommends for `PATH` problems failed with `No module named mddocx.__main__`. The module is now
part of the release, and the clean-install smoke test exercises `mddocx`, `mddocx-native`, and
`python -m mddocx` from the built wheel.

### 3. Diagnostics describe the machine, not the intention

- `mddocx doctor` converts one equation to prove the pipeline works and reports the engine that
  actually ran.
- A MathJax sidecar script with no JavaScript runtime is no longer reported as available, and
  `mddocx math-check` no longer claims the MathJax engine for equations that fell back to another
  one.
- `latex2mathml` is a core dependency, so equations have a real engine without Node.js; the
  bundled MathJax sidecar is still preferred when a runtime is available. The `mathjax` extra can
  supply that runtime, and `MDDOCX_NODE` selects a specific one.
- SVG support is probed, because CairoSVG installs as a Python package and still fails when the
  native cairo library is missing from the system.

### 4. Bangla output is never unreadable by accident

`SutonnyMJ` output is Bijoy-encoded and the font is not bundled, so on a machine without it the
text was written in a form Word could not display correctly, without any signal.

- A configured Bangla font that is not installed raises a `FONT301` warning naming the options.
- `--bengali-font auto` uses the legacy font when it is installed and an installed Unicode Bangla
  font otherwise, keeping the text Unicode.
- `--bengali-font none` skips the Bangla output pass, and `--bengali-font "Nirmala UI"` selects a
  specific font from the command line. Project manifests accept `render.bengali_font`.
- Defaults are unchanged: with `SutonnyMJ` installed, 1.4.1 output is byte-identical to 1.4.0.

## How to use it

```bash
# Check the machine first: dependencies, JavaScript runtime, math engine, SVG support
mddocx doctor

# Upgrade to the documented extras in one command
python -m pip install --upgrade "mddocx-native[all]"

# Readable Bangla whether or not SutonnyMJ is installed
mddocx bangla.md -o bangla.docx --bengali-font auto
```

```python
from mddocx import FontConfig, RenderConfig, render

config = RenderConfig(fonts=FontConfig(bengali="auto"))
render("bangla.md", "bangla.docx", config=config)
```

## Compatibility

- The v1 Python API, command names, exit codes, and default rendered output are unchanged.
- Warnings are now printed to stderr during a conversion; stdout still carries only the output
  path and the machine-readable reports, so scripting is unaffected.
- `mddocx doctor` exits 2 when the installation is conflicting or the math pipeline cannot run.
- `latex2mathml` becomes a core dependency, which changes the engine used by a document whose
  equations the MathJax sidecar cannot handle on a machine without Node.js.
- `mddocx` with no arguments on an interactive terminal now starts the guided console instead of
  printing a usage error. Redirected or piped invocations keep the previous behaviour.
- The build requires setuptools 77 or newer, matching PEP 639 license metadata.

## Verification

- 476 tests pass (39 of them new, covering the conflict guard and launcher, doctor reporting, the
  sidecar runtime check, Bangla font resolution, warning visibility, and the no-argument path),
  with Ruff and the targeted mypy gate clean.
- The wheel and sdist are built and installed into clean virtual environments, where `mddocx`,
  `mddocx-native`, `python -m mddocx`, `mddocx doctor`, a conversion, `inspect --strict`,
  `math-check --strict`, and `api --json` are all exercised.
- The conflict path is reproduced end to end: after installing the unrelated `mddocx` project,
  `mddocx-native` exits 2 with the repair commands, and both commands return to normal after the
  documented uninstall and reinstall.
- Not covered by this release's verification: the LibreOffice page-render regression suite, which
  needs LibreOffice installed, and a real `[mathjax]` extra download (~45 MB). Both are exercised
  by CI rather than by the machine that prepared this release.

## Known limitations

- `bijoy2unicode` is published as a source distribution only, so environments that forbid source
  builds (`--only-binary=:all:`, some mirrors) cannot install any mddocx release. It remains an
  exact pin, and the README documents the constraint.
- The guarding commands detect a conflicting install; they cannot repair it. The shared directory
  has to be uninstalled and reinstalled as documented.
- DOCX fidelity for Bangla still depends on SutonnyMJ being installed on the machine that opens
  the file. `--bengali-font auto` avoids unreadable output but cannot install the font.

## Follow-up

The next patch should carry the Bangla font policies into the visual regression suite by
installing SutonnyMJ and a Unicode Bangla font on the Linux visual job, so a rendering regression
is caught in page images rather than in DOCX XML alone.
