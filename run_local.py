#!/usr/bin/env python3
"""
Local execution of Zerve canvas blocks — mirrors how Zerve runs them on cloud.

Reads <canvas_uuid>/canvas.yaml, walks edges in topological order, and execs
each Python block (type=1) in a SHARED namespace so variables flow downstream
along edges, just like in Zerve. The canvas-level `python_global_imports` is
exec'd once into that namespace before any block runs (equivalent to Zerve
prepending it to every block).

Markdown blocks (type=4) are listed but not executed.

Usage:
    uv run run_local.py                       # run the whole Development layer
    uv run run_local.py --layer Development   # explicit layer
    uv run run_local.py --list                # show topo order
    uv run run_local.py --until "EDA Summary" # stop after a given block
    uv run run_local.py --only "Funnel Stages"  # run that block alone (still
                                                # exec'ing upstream blocks first
                                                # because variables flow via edges)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent
DATAS_DIR = REPO_ROOT / "datas"

TYPE_PYTHON = 1
TYPE_MARKDOWN = 4

EXCLUDE_DIRS = {".git", ".venv", "venv", "datas", "__pycache__", ".idea", ".vscode"}


def find_canvas_dir() -> Path:
    for p in REPO_ROOT.iterdir():
        if not p.is_dir() or p.name in EXCLUDE_DIRS:
            continue
        if (p / "canvas.yaml").exists():
            return p
    sys.exit("No canvas.yaml found under repo root.")


def topo_order(blocks: list[dict], edges: list[dict]) -> list[dict]:
    by_id = {b["id"]: b for b in blocks}
    incoming = {b["id"]: 0 for b in blocks}
    children: dict[str, list[str]] = {b["id"]: [] for b in blocks}
    for e in edges:
        s, t = e["source"], e["target"]
        if s in by_id and t in by_id:
            incoming[t] += 1
            children[s].append(t)

    ready = [bid for bid, n in incoming.items() if n == 0]
    out: list[dict] = []
    while ready:
        # Tie-break by canvas position so output order is stable
        ready.sort(key=lambda bid: (by_id[bid].get("y", 0), by_id[bid].get("x", 0)))
        bid = ready.pop(0)
        out.append(by_id[bid])
        for c in children[bid]:
            incoming[c] -= 1
            if incoming[c] == 0:
                ready.append(c)
    if len(out) != len(blocks):
        sys.exit("Cycle detected in canvas edges.")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--layer", default="Development", help="Layer name to run.")
    ap.add_argument("--list", action="store_true", help="List blocks in execution order and exit.")
    ap.add_argument("--until", default=None, help="Run up to and including this block name.")
    ap.add_argument("--only", default=None, help="Same as --until — kept for clarity.")
    ap.add_argument(
        "--save-figures",
        nargs="?",
        const="figures",
        default=None,
        metavar="DIR",
        help="Switch matplotlib to a non-interactive backend and write each plt.show() to DIR/figure_NN.png (default DIR=figures).",
    )
    args = ap.parse_args()

    canvas_dir = find_canvas_dir()
    canvas = yaml.safe_load((canvas_dir / "canvas.yaml").read_text())

    layers = canvas.get("layers") or []
    layer = next((L for L in layers if L["name"] == args.layer), None)
    if layer is None:
        names = [L["name"] for L in layers]
        sys.exit(f"Layer '{args.layer}' not found. Available: {names}")

    blocks = layer["blocks"]
    edges = layer.get("edges") or []
    ordered = topo_order(blocks, edges)

    if args.list:
        for b in ordered:
            kind = {TYPE_PYTHON: "python", TYPE_MARKDOWN: "markdown"}.get(b["type"], f"type={b['type']}")
            print(f"  [{kind:>8}] {b['name']}")
        return

    stop_at = args.until or args.only

    # If figures are being saved, set non-interactive backend BEFORE any block
    # imports matplotlib, then monkey-patch plt.show to savefig+close.
    save_dir: Path | None = None
    if args.save_figures is not None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        save_dir = (REPO_ROOT / args.save_figures).resolve()
        save_dir.mkdir(parents=True, exist_ok=True)
        counter = {"n": 0}

        def _show(*_a, **_k):
            counter["n"] += 1
            path = save_dir / f"figure_{counter['n']:02d}.png"
            plt.gcf().savefig(path, dpi=120, bbox_inches="tight")
            print(f"  [saved figure] {path}", flush=True)
            plt.close("all")

        plt.show = _show  # type: ignore[assignment]

    # CSV path shim: Zerve runs blocks with the dataset visible at the top of the
    # working directory. Locally it lives in datas/, so chdir there before exec.
    if DATAS_DIR.exists():
        os.chdir(DATAS_DIR)

    layer_dir = canvas_dir / args.layer
    global_prelude = (canvas.get("python_global_imports") or "").strip()

    namespace: dict = {"__name__": "__main__"}
    if global_prelude:
        exec(compile(global_prelude, "<python_global_imports>", "exec"), namespace)

    for b in ordered:
        name = b["name"]
        btype = b["type"]
        if btype == TYPE_MARKDOWN:
            print(f"\n[skip markdown] {name}")
            if stop_at == name:
                break
            continue
        if btype != TYPE_PYTHON:
            print(f"\n[skip type={btype}] {name}")
            if stop_at == name:
                break
            continue

        block_path = layer_dir / f"{name}.py"
        if not block_path.exists():
            sys.exit(f"Missing block source: {block_path}")
        src = block_path.read_text()
        print(f"\n===== running: {name} =====", flush=True)
        exec(compile(src, str(block_path), "exec"), namespace)
        if stop_at == name:
            break


if __name__ == "__main__":
    main()
