# Obstruction detector results

Mode: `balanced`. Synthetic frames prove the logic; they do not replace real-camera clips.

### Synthetic scenarios

| Scenario | Expected | Confirmed | Latency (s) | Result | Note |
|---|---|---|---|---|---|
| normal_use | no confirm | no | - | PASS |  |
| dim_room | no confirm | no | - | PASS |  |
| lights_off | no confirm | no | - | PASS |  |
| brightness_swing | no confirm | no | - | PASS |  |
| hand_fast | confirm | yes | 1.0 | PASS |  |
| hand_slow | confirm | yes | 0.7 | PASS |  |
| finger | confirm | yes | 1.0 | PASS |  |
| cloth | confirm | yes | 1.0 | PASS |  |
| paper | confirm | yes | 1.0 | PASS |  |
| shutter | confirm | yes | 1.0 | PASS |  |
| partial | no confirm | no | - | PASS |  |
| translucent | no confirm | no | - | PASS |  |

### Recorded clips (HP camera)

None recorded yet. Record with `python -m silentwatch.tools.record_clip --scenario <name>`; see `docs/manual-verification.md`.
