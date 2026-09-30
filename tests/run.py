#!/usr/bin/env python3
"""luce-geocore's gate: module tests, then the Base mesh checks at native
optimization levels 0-3 and through the C backend in debug and release; the
opt 2 build runs again with faces over 4 corners on the large-face path
(--small-faces 4) and with one and two pool workers."""
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
# Modules with their own `test` blocks.
MODULES = ["core/parallel.lucb"]
modes = [["--native", "--opt", str(level)] for level in ([args.opt] if args.opt is not None else range(4))]
if args.opt is None:
    modes += [["--backend=c"], ["--backend=c", "--release"]]
with tempfile.TemporaryDirectory(prefix="luce-geocore-tests-") as temporary:
    env = dict(os.environ, LUCE_CACHE=str(Path(temporary) / "cache"))
    binary = Path(temporary) / f"test{EXE}"
    for module in MODULES:
        for backend in ["--native", "--backend=c"]:
            print("TEST", module, backend, flush=True)
            subprocess.run([str(args.base.resolve()), "test", str(ROOT / "src/luce_geocore" / module), backend],
                           check=True, cwd=ROOT, env=env, timeout=600)
    for flags in modes:
        print("TEST", " ".join(flags), flush=True)
        subprocess.run([str(args.base.resolve()), "build", str(ROOT / "tests/main.lucb"), *flags, "-o", str(binary)],
                       check=True, env=env, timeout=600)
        subprocess.run([str(binary)], check=True, timeout=120)
        # One build also runs with nearly every face on the large-face (heap)
        # path, and with pools of one and two workers.
        if flags == modes[min(2, len(modes) - 1)]:
            print("TEST", " ".join(flags), "--small-faces 4", flush=True)
            subprocess.run([str(binary), "--small-faces", "4"], check=True, timeout=120)
            for workers in ["1", "2"]:
                print("TEST", " ".join(flags), f"LUCE_POOL_WORKERS={workers}", flush=True)
                subprocess.run([str(binary)], check=True, timeout=300, env=dict(os.environ, LUCE_POOL_WORKERS=workers))
print("PASS luce-geocore", flush=True)
