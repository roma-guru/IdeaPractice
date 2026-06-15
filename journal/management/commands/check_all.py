"""
management command: check_all
Runs all quality checks in sequence: Django system check, ruff, pytest, pyright.
Exits with a non-zero code if any check fails.
"""
from __future__ import annotations

import subprocess
import sys

from django.core.management.base import BaseCommand

_CHECKS = [
    {
        "name": "Django system check",
        "cmd": [sys.executable, "manage.py", "check", "--fail-level", "WARNING"],
    },
    {
        "name": "Ruff linter",
        "cmd": [sys.executable, "-m", "ruff", "check", "."],
    },
    {
        "name": "Tests (pytest)",
        "cmd": [sys.executable, "-m", "pytest", "-q"],
    },
    {
        "name": "Type check (pyright)",
        "cmd": [sys.executable, "-m", "pyright"],
    },
]


class Command(BaseCommand):
    help = "Run all quality checks: django check, ruff, pytest, pyright."

    def add_arguments(self, parser):  # type: ignore[override]
        parser.add_argument(
            "--skip",
            metavar="NAME",
            nargs="*",
            default=[],
            help="Skip checks by name substring, e.g. --skip pyright tests",
        )

    def handle(self, *args, **options):  # type: ignore[override]
        skip = [s.lower() for s in (options["skip"] or [])]
        results: list[tuple[str, bool]] = []

        for check in _CHECKS:
            name: str = check["name"]  # type: ignore[assignment]
            cmd: list[str] = check["cmd"]  # type: ignore[assignment]

            if any(s in name.lower() for s in skip):
                self.stdout.write(self.style.WARNING(f"  SKIP  {name}"))
                continue

            self.stdout.write(f"\n{'-'*60}")
            self.stdout.write(self.style.MIGRATE_HEADING(f">>  {name}"))
            self.stdout.write(f"{'-'*60}")

            result = subprocess.run(cmd)
            passed = result.returncode == 0
            results.append((name, passed))

            if passed:
                self.stdout.write(self.style.SUCCESS(f"OK  {name} passed"))
            else:
                self.stdout.write(self.style.ERROR(f"!!  {name} FAILED (exit {result.returncode})"))

        # Summary
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(self.style.MIGRATE_HEADING("Summary"))
        self.stdout.write(f"{'='*60}")
        all_passed = True
        for name, passed in results:
            mark = self.style.SUCCESS("OK") if passed else self.style.ERROR("!!")
            self.stdout.write(f"  {mark}  {name}")
            if not passed:
                all_passed = False

        if all_passed:
            self.stdout.write(self.style.SUCCESS("\nAll checks passed."))
        else:
            self.stdout.write(self.style.ERROR("\nSome checks failed."))
            sys.exit(1)
