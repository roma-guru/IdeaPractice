"""
management command: rundev
Starts Django dev server + Celery worker together.
Ctrl-C shuts both down cleanly.
"""
from __future__ import annotations

import signal
import subprocess
import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Start Django dev server and Celery worker together (dev only)."

    def add_arguments(self, parser):  # type: ignore[override]
        parser.add_argument(
            "--addr",
            default="127.0.0.1:8000",
            help="Address for runserver (default: 127.0.0.1:8000)",
        )
        parser.add_argument(
            "--loglevel",
            default="info",
            choices=["debug", "info", "warning", "error"],
            help="Celery log level (default: info)",
        )

    def handle(self, *args, **options):  # type: ignore[override]
        python = sys.executable
        addr = options["addr"]
        loglevel = options["loglevel"]

        server_cmd = [python, "manage.py", "runserver", addr]
        celery_cmd = [python, "-m", "celery", "-A", "config", "worker", "-l", loglevel]

        self.stdout.write(self.style.SUCCESS("Starting Django dev server…"))
        self.stdout.write(self.style.SUCCESS("Starting Celery worker…"))
        self.stdout.write("Press Ctrl-C to stop both.\n")

        procs: list[subprocess.Popen] = []
        try:
            procs.append(subprocess.Popen(server_cmd))
            procs.append(subprocess.Popen(celery_cmd))
            # Wait for either process to exit
            while True:
                for p in procs:
                    ret = p.poll()
                    if ret is not None:
                        args = p.args
                        name = args[0] if isinstance(args, (list, tuple)) else str(args)
                        self.stderr.write(
                            self.style.ERROR(f"Process {name} exited with code {ret}")
                        )
                        raise SystemExit(ret)
                import time
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.stdout.write("\nShutting down…")
        finally:
            for p in procs:
                if p.poll() is None:
                    if sys.platform == "win32":
                        p.send_signal(signal.CTRL_C_EVENT)
                    else:
                        p.terminate()
            for p in procs:
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
