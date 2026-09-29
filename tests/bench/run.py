#!/usr/bin/env python3
"""Build and run the verb and geometry-family benchmarks (report only): one
row per case, as a Markdown table. Timings are single runs of a --native
--opt 3 build."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="luce-base", help="the luce-base compiler")
    parser.add_argument("--opt", default="3")
    args = parser.parse_args()
    output = ""
    with tempfile.TemporaryDirectory(prefix="luce-geocore-bench-") as temporary:
        env = dict(os.environ, LUCE_CACHE=str(Path(temporary) / "cache"))
        for program in ("verbs", "geometry"):
            binary = Path(temporary) / program
            subprocess.run([args.base, "build", str(ROOT / f"tests/bench/{program}.lucb"), "--native", "--opt", args.opt, "-o", str(binary)],
                           check=True, env=env, timeout=900)
            output += subprocess.run([str(binary)], check=True, capture_output=True, text=True, timeout=900).stdout
    print("| Case | Time | Elements out | Warning |")
    print("|---|---:|---:|---|")
    for line in output.splitlines():
        name, spent, faces, warning = (line.split("\t") + ["", "", ""])[:4]
        print(f"| {name} | {float(spent):.1f} ms | {int(faces):,} | {warning} |")


if __name__ == "__main__":
    main()
