# Models

Model weights are **not committed** (see `.gitignore`). Download and verify them with:

```powershell
.\scripts\download_models.ps1
```

| File | Used for | Source | SHA-256 |
|---|---|---|---|
| `blaze_face_short_range.tflite` | Face detection for presence (M4.2). Detects faces only; no identity, no embeddings | Google MediaPipe model storage (`face_detector/blaze_face_short_range`) | `b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f` (recorded on first verified download, 229,746 bytes) |
| `hand_landmarker.task` | Optional hand-approach early warning (M6.1). Never locks by itself | Google MediaPipe model storage (`hand_landmarker/hand_landmarker`) | `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1` (recorded on first verified download, 7,819,105 bytes) |

Check the model licence terms before redistributing a packaged build (see M9.4).
