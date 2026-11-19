"""Evaluate the obstruction detector on synthetic scenarios and any recorded clips.

    python -m silentwatch.tools.evaluate [--write-docs]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from silentwatch.camera.replay import (
    Scenario,
    evaluate_frames,
    load_clip,
    run_synthetic,
    to_markdown,
)
from silentwatch.camera.calibration import baseline_from_images
from silentwatch.config import load_config

CLIPS_DIR = Path("data/clips")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-docs", action="store_true", help="write docs/obstruction-results.md")
    ap.add_argument("--mode", default="balanced")
    args = ap.parse_args(argv)
    cfg = load_config().obstruction

    syn_results = run_synthetic(cfg, args.mode)
    md = ["# Obstruction detector results", "", f"Mode: `{args.mode}`. Synthetic frames prove the logic; they do not replace real-camera clips.", ""]
    md.append(to_markdown(syn_results, "Synthetic scenarios"))

    real = []
    clips = sorted(CLIPS_DIR.glob("*/*.npz")) if CLIPS_DIR.exists() else []
    baseline_clip = next((c for c in clips if c.parent.name == "normal"), None)
    if clips and baseline_clip is not None:
        frames, _ = load_clip(baseline_clip)
        base = baseline_from_images(list(frames[10:]), "camera0", "recorded")
        for c in clips:
            frames, meta = load_clip(c)
            sc = Scenario(meta["scenario"], meta.get("description", ""), meta["expect_confirm"], meta.get("cover_at"))
            real.append(evaluate_frames(list(frames), base, cfg, sc, args.mode))
        md.append(to_markdown(real, "Recorded clips (HP camera)"))
    else:
        md.append("### Recorded clips (HP camera)\n\nNone recorded yet. Record with `python -m silentwatch.tools.record_clip --scenario <name>`; see `docs/manual-verification.md`.\n")

    text = "\n".join(md)
    print(text)
    if args.write_docs:
        Path("docs/obstruction-results.md").write_text(text, encoding="utf-8")
    failed = [r for r in syn_results + real if not r.passed and not r.known_limit]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
