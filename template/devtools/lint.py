import subprocess

from funlog import log_calls
from rich import get_console, print as rprint, reconfigure

# Update as needed. These paths must match the tool configs in pyproject.toml
# ([tool.ruff.lint.isort] known-first-party, [tool.ty.src] include, ...).
SRC_PATHS = ["src", "tests", "devtools", "scripts"]
DOC_PATHS = ["README.md", "docs", "CONTRIBUTING.md"]

# Files worth spell-checking that are neither source nor docs.
OTHER_SPELL_PATHS = ["pyproject.toml", "Makefile", "mkdocs.yml"]


reconfigure(emoji=not get_console().options.legacy_windows)  # No emojis on legacy windows.


def main() -> int:
    rprint()

    errcount = 0
    errcount += run(["codespell", "--write-changes", *SRC_PATHS, *DOC_PATHS, *OTHER_SPELL_PATHS])
    # Fix what can be fixed, then let the formatter and type checker work on
    # the result; the last ruff pass reports anything left over.
    errcount += run(["ruff", "check", "--fix", *SRC_PATHS])
    errcount += run(["ruff", "format", *SRC_PATHS])
    errcount += run(["ruff", "check", *SRC_PATHS])
    # ty reads [tool.ty] in pyproject.toml, so it needs no paths to stay in sync
    # with the config (passing paths would silently include/exclude files).
    errcount += run(["ty", "check"])
    errcount += run(["vulture", *SRC_PATHS])

    rprint()

    if errcount != 0:
        rprint(f"[bold red]:x: Lint failed with {errcount} errors.[/bold red]")
    else:
        rprint("[bold green]:white_check_mark: Lint passed![/bold green]")
    rprint()

    return errcount


@log_calls(level="warning", show_timing_only=True)
def run(cmd: list[str]) -> int:
    rprint()
    rprint(f"[bold green]>> {' '.join(cmd)}[/bold green]")
    errcount = 0
    try:
        subprocess.run(cmd, text=True, check=True)
    except KeyboardInterrupt:
        rprint("[yellow]Keyboard interrupt - Cancelled[/yellow]")
        errcount = 1
    except subprocess.CalledProcessError as e:
        rprint(f"[bold red]Error: {e}[/bold red]")
        errcount = 1

    return errcount


if __name__ == "__main__":
    raise SystemExit(main())
