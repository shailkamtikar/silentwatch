# Architecture

```
CameraCaptureService -> FeatureExtractor -> ObstructionClassifier --+
        |                                                           |
        +--> PresenceEstimator ------------------------------------+--> PolicyEngine --> WindowsLockService
                                                                    |         |
 (later) BluetoothProximity, HandApproach, USB monitor -------------+         +--> EventStore (SQLite)
```

The `policy/` package is pure logic (no I/O, no camera, no database): signals in, actions out, clock injected.

## Policy state machine

`INITIALIZING -> CALIBRATING -> MONITORING`, then derived from active signals by priority:

1. `LOCKED` (Windows session locked)
2. `LOCK_REQUESTED` (inside the lock cooldown)
3. `RECOVERY` (post-unlock grace period)
4. `TAMPERING_CONFIRMED` (obstruction confirmed)
5. `CAMERA_ERROR` (camera unavailable)
6. `OWNER_ABSENT` (absence confirmed)
7. `SUSPICIOUS` (possible/partial obstruction, hand approaching)
8. `OWNER_ABSENT_PENDING`
9. `OWNER_PRESENT`
10. `MONITORING`

## Lock rules (balanced / strict)

| Rule | Balanced | Strict |
|---|---|---|
| Obstruction confirmed | lock | lock |
| Partial obstruction + owner absent (pending or confirmed) | lock | lock |
| Possible obstruction + owner absent | log | lock |
| Camera unavailable + owner absent confirmed (+ phone missing if a phone is in use) | lock | lock earlier: absence pending is enough |
| Owner absent beyond timeout | lock | lock |
| Low brightness, camera frozen, phone missing alone | never lock | never lock |

A lock is suppressed during the lock cooldown and the post-unlock grace period.
