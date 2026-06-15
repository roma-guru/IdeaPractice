"""
management command: compilemessages  (overrides Django's built-in)
Compiles locale/*.po -> *.mo using polib — no GNU gettext required.
"""
from __future__ import annotations

import pathlib

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Compile .po translation files to .mo using polib (no GNU gettext needed)."

    def handle(self, *args, **options):  # type: ignore[override]
        try:
            import polib
        except ImportError:
            self.stderr.write(self.style.ERROR(
                "polib is not installed. Run: uv add --dev polib"
            ))
            return

        locale_paths = list(getattr(settings, "LOCALE_PATHS", []))
        if not locale_paths:
            self.stderr.write(self.style.WARNING("LOCALE_PATHS is empty — nothing to compile."))
            return

        compiled = 0
        for locale_dir in locale_paths:
            for po_path in sorted(pathlib.Path(locale_dir).glob("*/LC_MESSAGES/django.po")):
                po = polib.pofile(str(po_path))
                mo_path = po_path.with_suffix(".mo")
                po.save_as_mofile(str(mo_path))
                lang = po_path.parts[-3]
                self.stdout.write(
                    self.style.SUCCESS(f"  [{lang}] {po_path.name} -> {mo_path.name}")
                )
                compiled += 1

        self.stdout.write(self.style.SUCCESS(f"\nCompiled {compiled} catalogue(s)."))
