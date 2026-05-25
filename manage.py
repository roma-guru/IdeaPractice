#!/usr/bin/env python
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Install it and ensure it's available in your environment."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
