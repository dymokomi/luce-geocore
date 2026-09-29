#!/usr/bin/env python3
"""luce-geocore's gate: the Base mesh checks at native optimization levels 0-3
and through the C backend in debug and release."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXE = ".exe" if os.name == "nt" else ""
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base", type=Path, default=Path(os.environ.get("LUCE_BASE", ROOT.parent / f"luce-base/build/luce-base{EXE}")))
parser.add_argument("--opt", type=int, choices=range(4))
args = parser.parse_args()
modes = [["--native", "--opt", str(level)] for level in ([args.opt] if args.opt is not None else range(4))]
if args.opt is None:
    modes += [["--backend=c"], ["--backend=c", "--release"]]
with tempfile.TemporaryDirectory(prefix="luce-geocore-tests-") as temporary:
    env = dict(os.environ, LUCE_CACHE=str(Path(temporary) / "cache"))
    binary = Path(temporary) / f"test{EXE}"
    for flags in modes:
        print("TEST", " ".join(flags), flush=True)
        subprocess.run([str(args.base.resolve()), "build", str(ROOT / "tests/main.lucb"), *flags, "-o", str(binary)],
                       check=True, env=env, timeout=600)
        subprocess.run([str(binary)], check=True, timeout=120)
print("PASS luce-geocore", flush=True)
