# Models

Model weights are **not committed** (see `.gitignore`). Download and verify them with:

```powershell
.\scripts\download_models.ps1
```

| File | Used for | Source | SHA-256 |
|---|---|---|---|
| `blaze_face_short_range.tflite` | Face detection for presence (M4.2). Detects faces only; no identity, no embeddings | Google MediaPipe model storage (`face_detector/blaze_face_short_range`) | `b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f` (recorded on first verified download, 229,746 bytes) |

Check the model licence terms before redistributing a packaged build (see M9.4).
