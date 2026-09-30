#!/usr/bin/env python3
"""luce-geocore's memory-safety gate: the Base mesh checks (tests/main.lucb)
through the C backend, built with AddressSanitizer and
UndefinedBehaviorSanitizer (no checks disabled) and run as the gate runs
them: once, with faces over 4 corners on the large-face path, and with pools
of one and two workers. Any report fails."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base", type=Path, default=Path(os.environ.get("LUCE_BASE", ROOT.parent / "luce-base/build/luce-base")))
args = parser.parse_args()
runtime = ROOT.parent / "luce-base/runtime"
env = dict(os.environ, LUCE_STD=os.environ.get("LUCE_STD", str(ROOT.parent / "luce-base/src/std")),
           ASAN_OPTIONS="halt_on_error=1:abort_on_error=1:detect_leaks=0",
           UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
with tempfile.TemporaryDirectory(prefix="luce-geocore-sanitize-") as temporary:
    work = Path(temporary)
    env["LUCE_CACHE"] = str(work / "cache")
    source, binary = work / "checks.c", work / "checks"
    print("BUILD tests/main.lucb --emit=c, ASan + UBSan", flush=True)
    subprocess.run([str(args.base.resolve()), "build", str(ROOT / "tests/main.lucb"), "--emit=c", "-o", str(source)],
                   check=True, env=env, timeout=900)
    subprocess.run([os.environ.get("CC", "cc"), "-std=gnu11", "-O1", "-g", "-w", "-fno-strict-aliasing",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-omit-frame-pointer",
                    "-I", str(runtime), str(source), str(runtime / "lucb_rt.c"), "-pthread", "-lm", "-o", str(binary)],
                   check=True, timeout=1800)
    for extra, workers in [([], None), (["--small-faces", "4"], None), ([], "1"), ([], "2")]:
        run_env = dict(env, LUCE_POOL_WORKERS=workers) if workers else env
        print("TEST sanitized", *extra, f"LUCE_POOL_WORKERS={workers}" if workers else "", flush=True)
        subprocess.run([str(binary), *extra], check=True, env=run_env, timeout=1800)
print("PASS luce-geocore AddressSanitizer + UndefinedBehaviorSanitizer", flush=True)
