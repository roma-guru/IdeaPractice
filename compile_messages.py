#!/usr/bin/env python
"""Compile locale/*.po files to *.mo without requiring GNU gettext (uses polib)."""
import pathlib
import polib

root = pathlib.Path(__file__).parent
compiled = 0
for po_path in sorted(root.glob("locale/*/LC_MESSAGES/django.po")):
    po = polib.pofile(str(po_path))
    mo_path = po_path.with_suffix(".mo")
    po.save_as_mofile(str(mo_path))
    lang = po_path.parts[-3]
    print(f"  [{lang}] {po_path} -> {mo_path.name}")
    compiled += 1
print(f"\nCompiled {compiled} catalogue(s).")
