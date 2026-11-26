# Performance (M9.2)

Measured with `python scripts/measure.py --config <name> --seconds 180` on the HP laptop (Ryzen 7 7840HS, 16 logical CPUs, 15 GB RAM), **plugged in (AC)**, real HP webcam in a dim room, dry-run, after a 15 s warm-up/calibration. Default settings (640x480 capture, 5 fps analysis).

| Configuration | Frames analysed | CPU (avg, one core) | CPU (all 16 CPUs) | RSS start -> end | Growth (first third -> last third) |
|---|---|---|---|---|---|
| baseline: face presence + obstruction | 795 (4.4/s) | 8.6 % | 0.54 % | 129 -> 136 MB | +4.4 MB |
| + hand model loaded (idle scene, 0 model calls) | 794 (4.4/s) | 8.0 % | 0.50 % | 158 -> 167 MB | +5.9 MB |
| + dashboard with live preview (Qt offscreen) | 798 (4.4/s) | 9.3 % | 0.58 % | 164 -> 166 MB | +2.1 MB |

Budget (suggested in the playbook, adjusted to evidence): average CPU under 5 % of the whole machine and under 300 MB RAM. **Met with a wide margin.** The 4.4 fps (not 5) is the dim-room camera's real unique-frame rate (see D8).

## Honest limits of this measurement

- 3 minutes per configuration, not 30. The small RSS growth (2-6 MB) could be warm-up or a slow leak; it needs the 30-minute soak below to tell.
- **Battery impact was not measured**: the laptop was on AC (battery 100 %, status 2). A 30-minute on-battery comparison is a manual item.
- The dashboard run used Qt's offscreen platform, so real painting cost on screen is not included.
- Hand-model cost under real hand motion was not measured (it is only invoked when stage 1 sees a change; ~8.5 ms per call).
- Detection quality after "tuning": no tuning was needed, so the M3.4 synthetic targets are unchanged (`python -m silentwatch.tools.evaluate` still passes).

## Decision

No sampling-rate or resolution changes were required. Defaults stay at 640x480 / 5 fps.
