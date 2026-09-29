#!/usr/bin/env python3
"""Build and run the verb benchmark (report only): one row per case, as a
Markdown table. Timings are single runs of a --native --opt 3 build."""
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
    with tempfile.TemporaryDirectory(prefix="luce-geocore-bench-") as temporary:
        binary = Path(temporary) / "verbs"
        env = dict(os.environ, LUCE_CACHE=str(Path(temporary) / "cache"))
        subprocess.run([args.base, "build", str(ROOT / "tests/bench/verbs.lucb"), "--native", "--opt", args.opt, "-o", str(binary)],
                       check=True, env=env, timeout=900)
        output = subprocess.run([str(binary)], check=True, capture_output=True, text=True, timeout=900).stdout
    print("| Verb run | Time | Faces out | Warning |")
    print("|---|---:|---:|---|")
    for line in output.splitlines():
        name, spent, faces, warning = (line.split("\t") + ["", "", ""])[:4]
        print(f"| {name} | {float(spent):.1f} ms | {int(faces):,} | {warning} |")


if __name__ == "__main__":
    main()
