"""Detached launcher for the Stage 1+2 retrain.

Designed to be started by Windows Task Scheduler so it runs under the Task
Scheduler service, NOT as a child of the Claude Code terminal — every previous
background attempt died because closing the terminal reaped its process tree.

While training runs it holds SetThreadExecutionState(ES_CONTINUOUS |
ES_SYSTEM_REQUIRED) so the machine will not idle-sleep (auto-released on exit;
does not survive a physical lid-close). On finish it writes run2_DONE.txt with
the exit code and timestamp so completion can be confirmed after the fact.

Run (normally via the scheduled task): python training/run_detached.py
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
LOG = PROJECT / "training" / "outputs" / "train_full_run2.log"
DONE = PROJECT / "training" / "outputs" / "run2_DONE.txt"

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def main() -> int:
    if DONE.exists():
        DONE.unlink()
    ctypes.windll.kernel32.SetThreadExecutionState(
        ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    env = dict(os.environ, OMP_NUM_THREADS="6", MKL_NUM_THREADS="6")
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "w", encoding="utf-8") as log:
        log.write(f"===== detached run via Task Scheduler, started {started} =====\n")
        log.flush()
        rc = subprocess.run(
            [sys.executable, "-u", "training/run_stage12.py", "--epochs", "10"],
            cwd=str(PROJECT), env=env, stdout=log, stderr=subprocess.STDOUT,
        ).returncode
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    DONE.write_text(
        f"exit_code={rc}\nstarted={started}\n"
        f"finished={time.strftime('%Y-%m-%d %H:%M:%S')}\n", encoding="utf-8")
    return rc


if __name__ == "__main__":
    sys.exit(main())
