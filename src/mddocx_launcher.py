"""Collision-safe entry point for the ``mddocx-native`` command.

This distribution is published as ``mddocx-native``, but it installs the import
package and console script named ``mddocx``. An unrelated PyPI project uses the
name ``mddocx`` for the same two things, so a machine that installs both ends up
with one project's files silently overwriting the other's — including
``mddocx/cli.py``, which every ``mddocx`` entry point imports.

This module deliberately lives *outside* the ``mddocx`` package: the conflicting
project does not ship a file with this name, so it survives the overwrite and can
refuse to run a mixed installation instead of quietly executing the other
program. The package-name helpers here are shared with ``mddocx.doctor`` so the
diagnosis exists in exactly one place.

Set ``MDDOCX_ALLOW_IMPORT_CONFLICT=1`` to bypass the refusal.
"""

from __future__ import annotations

from importlib import metadata
import os
import re
import sys

#: Distribution name this project publishes.
DISTRIBUTION_NAME = "mddocx-native"
#: Import package and console script name both projects provide.
PACKAGE_NAME = "mddocx"
#: Environment variable that turns the refusal below into a warning.
ALLOW_CONFLICT_ENV_VAR = "MDDOCX_ALLOW_IMPORT_CONFLICT"


def _normalized_distribution(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def conflicting_distributions() -> tuple[str, ...]:
    """Other installed distributions that also provide the ``mddocx`` package."""
    try:
        providers = metadata.packages_distributions().get(PACKAGE_NAME, [])
    except Exception:  # pragma: no cover - defensive against broken metadata
        return ()
    conflicts = {
        provider
        for provider in providers
        if provider and _normalized_distribution(provider) != DISTRIBUTION_NAME
    }
    return tuple(sorted(conflicts))


def install_conflict_message(conflicts: tuple[str, ...]) -> str:
    """Explain a conflicting install and the exact commands that repair it."""
    names = ", ".join(conflicts)
    return (
        f"Another installed distribution provides the '{PACKAGE_NAME}' package: {names}.\n"
        f"  Both projects write to the same site-packages/{PACKAGE_NAME} directory and to the\n"
        f"  same '{PACKAGE_NAME}' command, so one of them has overwritten the other's files.\n"
        f"  Fix: python -m pip uninstall -y {' '.join(conflicts)} {DISTRIBUTION_NAME}\n"
        f"       python -m pip install --force-reinstall {DISTRIBUTION_NAME}\n"
        f"  Afterwards use '{DISTRIBUTION_NAME}', which the other project does not provide.\n"
        f"  Set {ALLOW_CONFLICT_ENV_VAR}=1 to run anyway and ignore this check."
    )


#: Public names that only this project's ``mddocx`` package exposes. Package
#: metadata can look clean while the files on disk belong to the other project,
#: so the imported package is identified by its own API instead.
REQUIRED_PACKAGE_ATTRIBUTES = ("render", "render_string", "Compiler")


def verify_installed_package() -> str | None:
    """Return why the imported ``mddocx`` package is not this distribution."""
    try:
        import mddocx
    except Exception as exc:  # noqa: BLE001 - any import failure means corruption
        return f"the mddocx package could not be imported: {type(exc).__name__}: {exc}"
    missing = [name for name in REQUIRED_PACKAGE_ATTRIBUTES if not hasattr(mddocx, name)]
    if missing:
        version = getattr(mddocx, "__version__", "unknown")
        author = getattr(mddocx, "__author__", None)
        detail = f" (version {version}{f', author {author}' if author else ''})"
        return (
            f"the imported mddocx package is not this project{detail}: missing {', '.join(missing)}"
        )
    return None


def main(argv: list[str] | None = None) -> int:
    """Run the command line interface, refusing a corrupted installation."""
    conflicts = conflicting_distributions()
    problem = verify_installed_package() if not conflicts else None
    if conflicts or problem:
        print("ERROR: this mddocx installation is not usable as installed.", file=sys.stderr)
        if conflicts:
            print(install_conflict_message(conflicts), file=sys.stderr)
        if problem:
            print(
                f"  {problem}.\n  Fix: python -m pip install --force-reinstall {DISTRIBUTION_NAME}",
                file=sys.stderr,
            )
        if not os.environ.get(ALLOW_CONFLICT_ENV_VAR):
            return 2
        print(f"Continuing because {ALLOW_CONFLICT_ENV_VAR} is set.", file=sys.stderr)
    try:
        from mddocx.cli import main as cli_main
    except Exception as exc:  # noqa: BLE001 - report instead of a bare traceback
        print(
            f"ERROR: the mddocx command line interface could not be loaded "
            f"({type(exc).__name__}: {exc}).\n"
            f"  Fix: python -m pip install --force-reinstall {DISTRIBUTION_NAME}",
            file=sys.stderr,
        )
        return 2
    return cli_main(argv)


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
