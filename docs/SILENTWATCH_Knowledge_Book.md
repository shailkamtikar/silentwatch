# SILENTWATCH

## Knowledge Book: Intelligent Laptop Presence, Privacy, and Anti-Theft Protection

**Document type:** Technical knowledge base and system design reference\
**Target platform:** Windows 11\
**Primary companion device:** Android phone\
**Primary hardware assumed:** Built-in laptop webcam and Bluetooth
adapter\
**Cost target:** Free/open-source software; no mandatory cloud services
or paid APIs\
**Status:** Research-backed concept and implementation blueprint\
**Last reviewed:** 19 November 2026

------------------------------------------------------------------------

## 1. Executive summary

SILENTWATCH is a privacy-first Windows 11 desktop security application.
Its purpose is to protect an unattended or physically threatened laptop
by combining local camera analysis, owner-presence estimation,
camera-tampering detection, phone proximity signals, Windows security
APIs, and a local event log.

The central use case is:

1.  The owner is using the laptop.
2.  The owner leaves the desk.
3.  Another person approaches from within or outside the webcam's useful
    face-recognition range.
4.  The person covers, obstructs, disables, or interferes with the
    camera.
5.  SILENTWATCH detects a likely camera-integrity incident and locks the
    real Windows session.

The system should not depend on face recognition alone. A face may never
enter the frame; the lens may be covered before a face is visible; the
room may become dark for innocent reasons; and a camera can fail because
of drivers or hardware. SILENTWATCH therefore needs multiple signals,
confidence levels, state transitions, and safe fallback behaviour.

SILENTWATCH is intended to be: - Local-first: camera frames and
biometric templates stay on the laptop by default. - Offline-capable:
core detection and locking do not require internet. - Transparent:
camera and microphone use must be visible and configurable. - Fail-safe
but usable: high-confidence tampering causes a real Windows lock;
ambiguous sensor failures are logged and handled with calibrated
policy. - Modular: camera, presence, Bluetooth, Windows integration,
policy engine, UI, and logging are separate components.

It is a defensive security utility, not a guaranteed anti-theft system.
It cannot guarantee detection of every attacker, prevent access by an
already authenticated administrator, or replace Windows account
security, disk encryption, backups, and physical security.

------------------------------------------------------------------------

## 2. Problem definition and threat model

### 2.1 Primary threats

**Unattended access** - Owner leaves an unlocked laptop. - Another
person sits down or reaches toward the keyboard. - The application
should lock before the person can access files.

**Camera-front approach and obstruction** - A person approaches from
directly in front of the laptop. - Their face may be too close, outside
the camera's useful field of view, turned away, or never detected. -
They place a hand, finger, cloth, paper, or object over the webcam. -
The image becomes partially or completely obscured. - SILENTWATCH should
identify the change as likely camera tampering and lock Windows
according to policy.

**Camera disablement** - Camera is disconnected, disabled, blocked by a
hardware shutter, or becomes unavailable. - This is a security-relevant
event, but software cannot always distinguish deliberate disablement
from a driver crash, privacy setting, app conflict, or hardware fault.

**Shoulder surfing / onlooker** - A second person is near the display
while the owner is working. - The system may warn, dim, obscure
sensitive content, or lock according to user settings.

**Laptop snatch or forced movement** - Laptop is picked up or moved
rapidly while the owner's phone separates from it. - This can be treated
as a suspicious combined event. - Many laptops do not expose a
general-purpose accelerometer; movement detection must be
hardware-checked and cannot be assumed.

**Phone separation** - Owner's Android phone, acting as a proximity
token, moves away from the laptop. - Bluetooth separation can support
walk-away detection, but it is not proof of theft or hijacking.

**Peripheral tampering** - A new USB storage device is connected while
the owner is absent. - The event can be logged and may raise risk.

### 2.2 Security objectives

1.  Lock the actual Windows session, not a simulated fullscreen lock
    screen.
2.  Detect owner absence with tolerable false-positive rates.
3.  Detect camera obstruction even when no face is recognized.
4.  Distinguish camera obstruction from ordinary lighting changes as far
    as practical.
5.  Detect camera loss, feed freeze, and device changes.
6.  Combine independent signals without treating any one noisy signal as
    absolute proof.
7.  Preserve local evidence only when enabled and legally/ethically
    appropriate.
8.  Recover safely after reboot, crash, camera failure, and Windows
    lock/unlock.
9.  Avoid weakening Windows security or collecting unnecessary personal
    data.

### 2.3 Out-of-scope guarantees

SILENTWATCH cannot guarantee: - Detection of an attacker who stays
outside the camera field of view and does not affect monitored
signals. - Reliable identification of physical coercion or a human
hijacking event. - Motion detection on hardware with no accessible
motion sensor. - Protection if an attacker has administrative control
and can stop or uninstall the application. - Protection of data on an
unencrypted disk if the attacker can remove the drive or boot another
operating system. - A photograph of a person who covers the camera
before a usable frame can be captured. - Accurate distance estimation
from a single ordinary webcam in all conditions.

The product should clearly communicate these limitations.

------------------------------------------------------------------------

## 3. User scenarios and expected behaviour

### Scenario A: Owner walks away

-   Owner presence confidence falls.
-   Start a configurable grace period.
-   If absence persists, call the Windows lock API.
-   Continue monitoring only if the camera can be used safely and
    Windows permits it.
-   Record the reason and timestamp.

### Scenario B: Unknown person approaches while owner is absent

-   Person/face detection may identify an unfamiliar person.
-   If identity confidence is low, do not claim certainty.
-   A policy may lock immediately when the owner is already confirmed
    absent.
-   Record a security event.

### Scenario C: Person approaches and covers the webcam without their face entering view

-   Do not wait for face recognition.
-   Detect abrupt or progressive loss of scene structure, image texture,
    brightness distribution, sharpness, and/or a large near-field
    hand/object.
-   Require a short persistence window and multiple features to reduce
    false alarms.
-   If obstruction confidence is high, lock Windows.
-   Record whether the trigger was full obstruction, partial
    obstruction, camera disappearance, or a combination.

### Scenario D: Room light turns off

-   Brightness falls, but image structure may remain.
-   A brightness-only detector must not automatically classify this as
    tampering.
-   Use texture, edge density, spatial uniformity, temporal change, and
    persistence.
-   If uncertain, log or enter a warning state rather than instantly
    locking, unless the user explicitly chooses strict mode.

### Scenario E: Owner is sitting in front of the laptop and someone covers the camera

-   A sudden high-confidence camera obstruction is suspicious regardless
    of owner recognition.
-   Locking policy should be configurable. Recommended default: lock on
    high-confidence physical obstruction, with a short debounce window.
-   The owner can unlock using normal Windows authentication.

### Scenario F: Camera driver crashes

-   Mark camera as unavailable, not automatically as confirmed attack.
-   Retry initialization with bounded backoff.
-   If the owner is absent or other signals are suspicious, lock.
-   Otherwise show a warning and record the fault.

### Scenario G: Laptop is lifted and phone separates

-   If motion sensing is available, detect a motion event.
-   Independently monitor phone proximity.
-   A short time-window correlation can raise the risk score.
-   Lock when the combined confidence exceeds policy threshold.
-   Do not call this a confirmed hijacking; label it "suspected physical
    movement / device separation."

------------------------------------------------------------------------

## 4. System architecture

``` text
                    SILENTWATCH
                         |
       +-----------------+------------------+
       |                 |                  |
  CAMERA SERVICE    PHONE PROXIMITY     WINDOWS EVENTS
       |                 |                  |
  Frame capture      BLE observations   Lock/session state
       |                 |              USB/device events
       +-----------------+------------------+
                         |
                 SIGNAL NORMALIZER
                         |
              +----------+-----------+
              |                      |
       VISION ANALYSIS          SENSOR ANALYSIS
       - scene baseline         - BLE presence
       - obstruction            - motion (if exposed)
       - hand/object            - camera availability
       - face/person            - USB/device changes
              |                      |
              +----------+-----------+
                         |
                  POLICY ENGINE
             - state machine
             - risk/confidence
             - debounce/cooldowns
             - user-selected mode
                         |
            +------------+-------------+
            |            |             |
        Windows lock   Local log    Notifications
            |            |             |
            +------------+-------------+
                         |
                  DESKTOP UI / TRAY
```

### 4.1 Main software modules

1.  **CameraCaptureService** -- enumerates and opens the webcam;
    supplies frames; handles device loss and reinitialization.
2.  **CameraIntegrityAnalyzer** -- detects obstruction, lens coverage,
    feed freeze, and abrupt scene changes.
3.  **HandApproachDetector** -- optional model-based detector for a hand
    entering the near-camera region.
4.  **PresenceEstimator** -- estimates whether the owner is at the
    laptop using face/person presence and optional Windows presence
    sensor.
5.  **OwnerRecognitionService** -- optional face verification; should be
    opt-in and local.
6.  **BluetoothProximityService** -- monitors the enrolled Android phone
    using BLE where supported.
7.  **MotionSensorService** -- optional Windows sensor access;
    hardware-dependent.
8.  **DeviceMonitor** -- monitors camera/device availability and
    selected USB events.
9.  **SecurityPolicyEngine** -- combines events, state, confidence,
    timing, and user mode.
10. **WindowsLockService** -- invokes the real Windows lock mechanism.
11. **EvidenceStore** -- stores minimal local event metadata and
    optional snapshots.
12. **NotificationService** -- shows local Windows notifications and
    optional authenticated phone alerts.
13. **Settings/UI** -- dashboard, enrollment, policy, privacy controls,
    and event history.

------------------------------------------------------------------------

## 5. Camera tampering detection: detailed design

This is a core differentiator and should be implemented before advanced
AI features.

### 5.1 Why face recognition is insufficient

Face recognition only works when a usable face is visible. A person
can: - Approach with their face outside the frame. - Turn their face
away. - Put a hand over the camera first. - Cover the camera with an
object. - Trigger a camera privacy shutter.

Therefore, camera integrity must be analyzed independently of identity
recognition.

### 5.2 Detection signals

Use a combination of classical computer vision and optional machine
learning.

**A. Brightness statistics** - Mean luminance. - Median luminance. -
Percentage of pixels below a dark threshold. - Histogram distribution. -
Change relative to a rolling baseline.

A covered lens often produces a very dark or nearly uniform image, but
darkness alone is not sufficient. A dark room, exposure adjustment, or
camera auto-exposure can produce similar values.

**B. Spatial uniformity** - Variance of luminance. - Local contrast. -
Standard deviation across image tiles. - Entropy or information
content. - Percentage of image with very low local variance.

A lens covered by a finger, cloth, or opaque object often loses scene
structure. A uniformly dark frame may have low spatial variance, but a
textured finger or fabric may not.

**C. Edge and texture loss** - Sobel/Canny edge density. - Laplacian
variance (a rough sharpness/focus measure). - Local binary patterns or
other texture descriptors if needed. - Compare to the camera's
normal-scene baseline.

A close object can create blur and remove the background. However,
autofocus changes and ordinary defocus can also lower sharpness.

**D. Frame-to-frame change** - Mean absolute frame difference. -
Structural similarity or image-feature difference. - Optical flow
magnitude and distribution. - Abrupt transition from normal scene to a
close, featureless image. - Progressive loss of scene structure over
multiple frames.

**E. Near-field hand/object detection** - MediaPipe Hand Landmarker can
detect hands and landmarks. - A model can detect hands or objects
entering the frame. - Track whether a detected hand grows rapidly in
apparent size or moves toward the lens. - This is useful as an early
warning, not a guaranteed distance measurement.

**F. Camera health** - Frame timestamps. - Repeated identical frames. -
Capture read failures. - Device removal/arrival notifications. -
Unexpected format/resolution changes. - Permission/access errors.

A frozen stream may be a driver issue rather than an attacker. Treat it
as camera failure unless correlated with other signals.

### 5.3 Suggested obstruction classifier

Start with a deterministic, explainable classifier rather than training
a neural network immediately.

For each sampled frame, compute normalized features: -
`brightness_score` - `dark_pixel_ratio` - `local_variance_score` -
`edge_density_score` - `sharpness_score` - `entropy_score` -
`frame_change_score` - `hand_near_lens_score` (optional) -
`camera_health_score`

Compare values with a baseline gathered during a short calibration
period.

Then produce: - `NORMAL` - `POSSIBLE_OBSTRUCTION` -
`PARTIAL_OBSTRUCTION` - `CONFIRMED_OBSTRUCTION` - `CAMERA_UNAVAILABLE` -
`CAMERA_FROZEN` - `UNKNOWN`

Use temporal persistence: a one-frame anomaly should not cause a lock.
For example, require high-confidence obstruction for a configurable
0.5--2 second window, with strict mode allowing shorter delays. Exact
thresholds must be determined through testing on the target laptop and
webcam.

### 5.4 Baseline and calibration

At initial setup: 1. Ask the user to position the laptop normally. 2.
Capture a short set of frames in typical lighting. 3. Estimate baseline
brightness, texture, sharpness, and spatial variation. 4. Store only
numeric calibration values by default. 5. Recalibrate when the camera,
resolution, or environment changes.

Do not assume one universal brightness threshold works across all
webcams.

### 5.5 Limits and bypass considerations

-   Some privacy shutters cause a manufacturer-generated black frame;
    software may not know whether it was deliberate.
-   A person can cover only part of the lens.
-   Transparent or translucent material may not cause strong darkness.
-   A static photograph displayed in front of the camera may fool simple
    motion/presence checks.
-   An attacker may disable camera access through settings or terminate
    the process.
-   Camera access may conflict with Windows Hello, video-call software,
    or another application; test actual hardware behaviour.
-   Some webcams have built-in image processing that changes exposure or
    brightness unpredictably.

### 5.6 Evidence capture

Maintain a short in-memory ring buffer of recent frames if the user
enables evidence capture. When tampering is detected: - Save the last
usable pre-obstruction frame, if available. - Optionally save the first
obstruction frame. - Do not claim to capture the intruder if no
face/person was visible. - Store locally, encrypt if practical, and
provide automatic retention/deletion settings. - Default to
metadata-only logging until the user opts into snapshots.

------------------------------------------------------------------------

## 6. Presence and identity

### 6.1 Presence is not identity

Presence detection asks: "Is someone in front of the laptop?"\
Identity verification asks: "Is that person the enrolled owner?"

Keep these separate. A generic person detector should not be described
as face recognition.

### 6.2 Recommended approach

**MVP** - Face detection or person detection to estimate presence. - No
biometric identity required for basic walk-away locking. - A
configurable absence timer.

**Later** - Optional local face verification. - Enroll several samples
under different lighting and angles. - Use an embedding model and
compare embeddings with a calibrated threshold. - Avoid storing raw face
photos unless required. - Provide a way to delete the enrolled template.

Potential models/libraries: - MediaPipe Face Detector / Face Landmarker
for face location and landmarks. - OpenCV Zoo YuNet for face
detection. - OpenCV Zoo SFace for face feature extraction/recognition. -
InsightFace may offer useful models, but review the license for the
specific code and model weights before distribution.

Do not treat face recognition as secure authentication equivalent to
Windows Hello. It is a sensor signal for policy, not a replacement for
Windows credentials or biometrics.

### 6.3 Owner absence logic

Use a state machine: - `OWNER_PRESENT` - `PRESENCE_UNCERTAIN` -
`OWNER_ABSENT_PENDING` - `OWNER_ABSENT_CONFIRMED` - `LOCK_REQUESTED` -
`LOCKED` - `RECOVERY`

Use hysteresis: - Require several consecutive detections to transition
to present. - Require a longer absence interval to transition to
absent. - Avoid toggling rapidly because of head turns, occlusion, or
camera frame drops.

Example starting values for experiments (not final defaults): - Sample
at 5--10 FPS for presence. - Mark absence pending after 2--3 seconds
without a reliable person/face. - Lock after 5--15 seconds of confirmed
absence. - Let the user configure all timing.

------------------------------------------------------------------------

## 7. Vision libraries and model runtimes

No single library is best for every task. A layered stack is
recommended.

### 7.1 OpenCV

Official documentation: https://docs.opencv.org/

Use for: - Webcam frame acquisition in a Python prototype. - Image
resizing and color conversion. - Brightness and histogram analysis. -
Blur/sharpness measures. - Edge detection. - Frame differencing. -
Optical flow. - Basic tracking and image processing.

Strengths: - Mature, widely used, free, broad functionality. - Excellent
for deterministic image analysis. - Works well as the camera-frame
processing foundation.

Limitations: - It is not, by itself, a high-level semantic AI model. -
Camera backend behaviour varies by device and driver. - Face recognition
and object recognition require suitable models or additional libraries.

License: OpenCV is Apache 2.0 in current 4.x releases; verify the exact
version and bundled third-party components before distribution.

### 7.2 MediaPipe

Official documentation:
https://ai.google.dev/edge/mediapipe/solutions/guide

Use for: - Hand landmarks and hand tracking. - Face detection and
landmarks. - Pose landmarks. - Optional gesture and near-camera hand
cues.

Strengths: - Designed for efficient on-device perception. - Useful for
hand approach detection. - Does not require cloud inference.

Limitations: - A hand landmark model does not directly prove the hand is
covering the camera. - It may fail under occlusion, low light, motion
blur, or unusual angles. - Available APIs and Python packaging can
change; pin and test versions.

License: MediaPipe source is Apache 2.0; inspect model assets and
dependencies separately.

### 7.3 YOLO / Ultralytics

Official documentation: https://docs.ultralytics.com/

Use for: - Person and object detection. - Detecting hands or relevant
objects if a suitable model is available or trained. - Multi-person
detection and tracking.

Strengths: - Fast object detection with suitable hardware/models. -
Useful when generic object categories are needed.

Limitations: - Model choice and speed depend on hardware. - Standard
pretrained models may not include a "camera covered" class. - A custom
dataset and training/evaluation may be needed. - **Licensing:**
Ultralytics offers AGPL-3.0 and enterprise licensing options. Review
obligations before integrating into a closed-source/distributed product.
Do not assume every model or use case is license-free.

### 7.4 PyTorch and Torchvision

Official documentation: https://pytorch.org/docs/stable/index.html

Use for: - Training custom obstruction classifiers. - Experimenting with
image classification or object detection. - Fine-tuning a model on
collected, consented data.

Strengths: - Flexible model development ecosystem. - Broad research and
deployment support.

Limitations: - More resource-intensive than simple image processing. -
Not necessary for the first prototype. - Training requires a properly
labeled, representative dataset.

### 7.5 ONNX Runtime

Official documentation: https://onnxruntime.ai/docs/

Use for: - Running exported models locally. - CPU inference. - Optional
hardware acceleration through supported execution providers.

Strengths: - Separates model training from deployment. - Can reduce
deployment overhead for selected models. - Useful for shipping a stable
inference runtime.

Limitations: - It does not supply the model or solve detection by
itself. - Hardware acceleration depends on the execution provider and
drivers.

### 7.6 Recommended vision stack

**First prototype** - OpenCV for camera capture and image metrics. -
MediaPipe for hand/face landmarks where needed. - No YOLO or PyTorch
until tests show a semantic model is needed.

**Later deployment** - OpenCV or Windows MediaCapture for capture. -
MediaPipe for hands/faces. - ONNX Runtime for a custom obstruction model
if rule-based analysis is insufficient. - Optional YOLO only after
license review and benchmark.

------------------------------------------------------------------------

## 8. Windows 11 integration

### 8.1 Locking the real Windows session

Use the Windows `LockWorkStation` Win32 API. It requests the workstation
to lock, showing the normal Windows sign-in/lock experience.

Microsoft API reference:\
https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-lockworkstation

Python can call Win32 APIs through `ctypes` or `pywin32`. The
implementation should: - Check and log the API call result. - Avoid
assuming that a successful call means every subsequent state transition
has completed. - Observe session lock/unlock events where possible. -
Avoid a fake lock-screen overlay as the security boundary.

### 8.2 Camera capture options

**Python prototype** - OpenCV `VideoCapture`. - Enumerate camera indexes
and test available backends. - Handle read failures and camera
contention.

**More native Windows implementation** - Windows `MediaCapture` /
`MediaFrameReader` APIs. - Microsoft documentation: -
https://learn.microsoft.com/en-us/windows/apps/develop/camera/camera -
https://learn.microsoft.com/en-us/uwp/api/windows.media.capture.mediacapture

MediaCapture supports camera capture, device selection, formats, frame
readers, and lifecycle handling. Camera initialization and permission
behaviour need testing in the chosen app packaging model.

Windows camera documentation also describes camera privacy switches,
driver behaviour, and camera pipeline considerations:
https://learn.microsoft.com/en-us/windows-hardware/drivers/stream/

### 8.3 Windows presence sensing

Windows 11 supports native presence-sensing features on compatible
devices, including Lock on Leave and Wake on Approach. It requires
supported presence-sensor hardware; an ordinary webcam alone does not
guarantee support.

Microsoft reference:
https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/sensors-presence-sensing

Check Windows Settings for Presence sensing. SILENTWATCH can complement
native functionality, but should not assume the laptop has the required
sensor or that third-party apps can access every signal.

### 8.4 Sensors and motion

Windows exposes sensor and device APIs, but available sensors depend on
hardware and drivers.

Microsoft overview:
https://learn.microsoft.com/en-us/windows/apps/develop/devices-and-sensors

A laptop may have an accelerometer for drive protection, screen
rotation, or other OEM functions, but it may not be exposed to ordinary
desktop applications. Verify hardware and API access before designing
around it. Do not claim universal laptop snatch detection.

### 8.5 USB and device monitoring

Windows has device enumeration, device notification, and event APIs. A
prototype can monitor selected device arrivals/removals and classify USB
storage devices.

Microsoft references: -
https://learn.microsoft.com/en-us/windows/apps/develop/devices-sensors/enable-device-capabilities -
https://learn.microsoft.com/en-us/windows/win32/api/

Monitoring is not the same as blocking. Blocking USB storage
comprehensively can require policy configuration, elevated privileges,
or enterprise device-control features. The MVP should log and optionally
lock rather than attempt to disable arbitrary devices.

### 8.6 Startup and background operation

Possible options: - User-level startup entry / Startup folder. - Windows
Task Scheduler at user logon. - Packaged app startup task where
appropriate.

Start with a normal user process. Avoid running as administrator unless
a specific feature requires it. A tray application is preferable to a
hidden, unobservable process.

------------------------------------------------------------------------

## 9. Android phone integration

### 9.1 Phone as a proximity token

The Android phone can act as a companion token. The laptop scans for a
known Bluetooth Low Energy advertisement or other supported signal.

Potential Python library: - Bleak:
https://bleak.readthedocs.io/en/stable/

Bleak supports BLE scanning and GATT operations on Windows, subject to
Windows Bluetooth stack, adapter, permissions, and device behaviour.

### 9.2 Important Bluetooth limitations

-   Bluetooth signal strength fluctuates due to walls, body position,
    interference, antenna orientation, and laptop/phone power
    management.
-   A paired Bluetooth connection is not a precise distance measurement.
-   Android may use address randomization and background restrictions.
-   BLE advertising behaviour differs by phone model and OS version.
-   Disconnects can be caused by interference or sleep.
-   A Bluetooth disconnect is not proof of theft.

Recommended policy: - Use a rolling observation window. - Require
several missed observations or a sustained signal drop. - Combine with
owner absence and/or physical movement. - Provide a grace period and a
manual calibration process. - Treat BLE as one risk signal, not as a
sole authentication factor.

### 9.3 Remote emergency lock

A later Android companion app can send an authenticated `LOCK` command
over: - Local Wi-Fi / LAN, or - A direct BLE GATT channel if the
architecture supports it.

Security requirements: - Pairing/enrollment must require local physical
confirmation. - Use cryptographic authentication, not a guessable URL or
unauthenticated UDP packet. - Use a per-device secret or public-key
challenge-response. - Include replay protection (nonce/counter and
timestamp). - Never expose an unauthenticated lock endpoint to the
internet. - Lock command should be one-way and minimal; no remote file
access.

A LAN-only first version is simpler. A phone app is optional; a
command-line test client can validate the protocol.

------------------------------------------------------------------------

## 10. Security policy engine

### 10.1 Why a policy engine is needed

Individual sensors are noisy. A face detector can miss a face; BLE can
drop; lighting can change; camera drivers can fail. Independent modules
should emit events, while one policy engine makes decisions.

### 10.2 Suggested risk signals

Illustrative initial weights only; they must be tuned with test data.

  -----------------------------------------------------------------------
  Signal                                                   Example weight
  ------------------------------ ----------------------------------------
  Owner absent confirmed                                              +20

  Unknown person detected while                                       +35
  owner absent                   

  Hand approaches lens                                                +20

  High-confidence camera                                              +60
  obstruction                    

  Camera disappears while owner                                       +45
  absent                         

  Phone absent for sustained                                          +20
  interval                       

  Sudden physical movement (if                                        +35
  available)                     

  USB storage added while owner                                       +20
  absent                         

  Camera driver failure                                               +10

  Multiple independent                        Additional confidence bonus
  suspicious signals             
  -----------------------------------------------------------------------

Do not simply add events forever. Each signal should: - Have a
timestamp. - Expire after a defined interval. - Have confidence and
source reliability. - Be deduplicated. - Be cleared or decayed after
recovery.

### 10.3 Suggested policy modes

**Strict** - Lock quickly on confirmed obstruction or high-confidence
suspicious events. - Suitable for controlled testing and users who
prefer security over convenience.

**Balanced (recommended default)** - Lock immediately on high-confidence
physical obstruction. - For uncertain camera or BLE faults, correlate
signals or wait for a short debounce period. - Lock on confirmed owner
absence.

**Adaptive** - Risk score and confidence determine response. - Possible
actions: log, notify, privacy warning, lock. - The user can inspect why
a lock occurred.

### 10.4 Example decision rules

-   `CONFIRMED_OBSTRUCTION` sustained for the debounce window → lock.
-   `PARTIAL_OBSTRUCTION` + `OWNER_ABSENT_CONFIRMED` → lock.
-   `CAMERA_UNAVAILABLE` + owner absent + phone missing → lock.
-   `PHONE_MISSING` alone → wait / log; do not immediately call it a
    theft.
-   `LOW_BRIGHTNESS` alone → do not lock.
-   `CAMERA_FROZEN` alone → retry and log; escalate if correlated.
-   `OWNER_ABSENT_CONFIRMED` beyond configured timeout → lock.
-   Sudden motion + phone separation in a short time window → lock as
    suspected physical movement.

### 10.5 State machine

Suggested states: - `DISABLED` - `INITIALIZING` - `CALIBRATING` -
`MONITORING` - `OWNER_PRESENT` - `OWNER_ABSENT_PENDING` -
`OWNER_ABSENT` - `SUSPICIOUS` - `TAMPERING_CONFIRMED` -
`LOCK_REQUESTED` - `LOCKED` - `CAMERA_ERROR` - `RECOVERY`

State transitions must be logged and tested. The application should not
rapidly oscillate between states.

------------------------------------------------------------------------

## 11. Proposed technology stack

  -----------------------------------------------------------------------
  Layer                   Recommended technology  Reason
  ----------------------- ----------------------- -----------------------
  Language                Python 3.11 or 3.12     Fast development,
                          (pin exact version      Windows ecosystem
                          after compatibility     
                          test)                   

  Camera prototype        OpenCV                  Capture and image
                                                  processing

  Hand/face landmarks     MediaPipe               Efficient on-device
                                                  perception

  Face detection          MediaPipe or OpenCV Zoo Local face location
                          YuNet                   

  Optional face           OpenCV Zoo SFace or     Optional owner
  embeddings              another                 verification
                          license-reviewed model  

  Optional custom ML      PyTorch                 Training experiments

  Model inference         ONNX Runtime            Local model deployment

  Bluetooth LE            Bleak                   Windows BLE scanning

  Windows APIs            `ctypes` / `pywin32`;   Locking, devices,
                          WinRT APIs if required  session events

  Native camera           Windows MediaCapture    Windows camera
  alternative             APIs                    lifecycle and frame
                                                  access

  Database                SQLite                  Local event history and
                                                  settings

  UI                      PySide6 or              Desktop dashboard and
                          CustomTkinter           tray

  Logging                 Python `logging` +      Diagnostics and audit
                          SQLite events           trail

  Packaging               PyInstaller or Nuitka   Windows executable
                          (evaluate)              packaging

  Testing                 pytest                  Unit/integration tests

  Configuration           TOML or JSON            User settings

  Cryptography            Python `cryptography`   Authenticated companion
                                                  protocol and protected
                                                  secrets
  -----------------------------------------------------------------------

### UI recommendation

For a polished desktop application, **PySide6** is a strong choice.
CustomTkinter is simpler for a prototype. Keep the security engine
independent of the UI so the interface can be replaced without rewriting
detection.

### Python version note

Pin dependencies and test them together. Do not blindly install latest
versions in production. Camera, MediaPipe, and Bluetooth packages can
have Python-version and Windows-specific compatibility constraints.

------------------------------------------------------------------------

## 12. Repository structure

Suggested project structure:

``` text
silentwatch/
├── README.md
├── LICENSE
├── pyproject.toml
├── requirements.txt
├── config/
│   └── default.toml
├── assets/
│   └── icons/
├── models/
│   └── README.md
├── src/
│   └── silentwatch/
│       ├── __init__.py
│       ├── main.py
│       ├── app/
│       │   ├── lifecycle.py
│       │   └── tray.py
│       ├── camera/
│       │   ├── capture.py
│       │   ├── integrity.py
│       │   ├── obstruction.py
│       │   ├── hand_detector.py
│       │   └── calibration.py
│       ├── presence/
│       │   ├── estimator.py
│       │   └── owner_recognition.py
│       ├── bluetooth/
│       │   ├── scanner.py
│       │   └── enrollment.py
│       ├── windows/
│       │   ├── lock.py
│       │   ├── session.py
│       │   ├── camera_devices.py
│       │   ├── usb_monitor.py
│       │   └── sensors.py
│       ├── policy/
│       │   ├── engine.py
│       │   ├── states.py
│       │   └── rules.py
│       ├── storage/
│       │   ├── database.py
│       │   ├── events.py
│       │   └── retention.py
│       ├── notifications/
│       │   └── windows_toast.py
│       └── ui/
│           ├── dashboard.py
│           ├── settings.py
│           └── history.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── docs/
    ├── architecture.md
    ├── privacy.md
    ├── threat-model.md
    └── testing.md
```

------------------------------------------------------------------------

## 13. Data model and local storage

SQLite is sufficient for the first versions.

Suggested tables:

**`events`** - `id` - `timestamp_utc` - `event_type` - `severity` -
`confidence` - `source` - `details_json` - `action_taken`

**`settings`** - `key` - `value` - `updated_at`

**`device_enrollment`** - `device_id` - `device_type` -
`friendly_name` - `public_key_or_protected_token` - `created_at` -
`last_seen_at`

**`camera_calibration`** - `camera_id` - `resolution` -
`baseline_features_json` - `calibrated_at`

**`owner_template`** (only if face recognition is enabled) -
`template_id` - `embedding_ciphertext` - `model_name` - `created_at`

Avoid storing continuous video. Store only event metadata by default. If
snapshots are enabled, use a separate evidence directory with retention
limits and access controls.

------------------------------------------------------------------------

## 14. Privacy and security requirements

1.  Camera use must be disclosed during setup.
2.  The application must show a clear monitoring indicator and tray
    controls.
3.  Do not secretly activate the microphone.
4.  Voice trigger detection is out of scope for the core product unless
    explicitly enabled.
5.  Do not upload camera frames, face templates, or event logs to a
    server.
6.  Face recognition must be optional.
7.  Store only the minimum data required.
8.  Provide "delete all local data" and template deletion controls.
9.  Provide configurable snapshot retention; default to no snapshots.
10. Encrypt sensitive tokens and biometric templates using
    Windows-protected storage or an appropriate OS-backed secret store.
11. Do not store Windows passwords, PINs, or authentication tokens.
12. Do not create a fake lock screen or capture credentials.
13. Do not bypass Windows camera privacy controls.
14. Do not attempt to hide the process from Task Manager or security
    software.
15. Do not require administrator privileges for ordinary camera analysis
    and session locking.
16. Remote lock commands must be authenticated and replay-resistant.
17. Log security-relevant failures without collecting excessive personal
    information.

SILENTWATCH is a defensive application. It should not be designed as
covert surveillance software.

------------------------------------------------------------------------

## 15. Performance and power management

Continuous webcam processing can consume battery, generate heat, and
interfere with video-call software.

Recommended starting strategy: - Capture at a modest resolution (for
example, 640×480) for basic integrity metrics. - Analyze a few frames
per second for presence and obstruction, not necessarily the full camera
frame rate. - Run hand/face models less frequently or only when a cheap
detector flags a change. - Use a small ring buffer rather than saving
continuous video. - Pause or adapt processing when Windows is locked,
asleep, or the user disables monitoring. - Release camera resources
cleanly. - Avoid multiple simultaneous camera handles. - Measure CPU,
memory, battery impact, and camera contention on the actual laptop.

A two-stage pipeline is recommended:

**Stage 1 -- inexpensive checks** - Brightness, contrast, histogram,
edge density, frame difference, camera health.

**Stage 2 -- conditional perception** - MediaPipe hand/face detection or
optional ONNX model when Stage 1 detects suspicious change.

This keeps the normal operating cost low.

------------------------------------------------------------------------

## 16. Failure modes and mitigations

  -----------------------------------------------------------------------
  Failure                 Possible cause          Mitigation
  ----------------------- ----------------------- -----------------------
  False lock in a dark    Brightness-only rule    Use texture/spatial
  room                                            features and
                                                  calibration

  False lock during video Camera in use by        Detect contention;
  call                    another app             define camera ownership
                                                  strategy

  Missed obstruction      Partial/translucent     Multi-feature
                          cover                   classifier and testing

  Hand detector misses    Blur, low light,        Treat hand detection as
  hand                    occlusion               optional evidence

  Camera unavailable      Driver crash, privacy   Distinguish failure
                          switch, permissions     from confirmed
                                                  tampering

  Frozen frame            Driver or backend issue Timestamp and
                                                  frame-hash monitoring

  Bluetooth false         Interference, sleep,    Rolling window and
  disconnect              distance                multi-signal policy

  Face false rejection    Lighting, angle,        Use presence separately
                          glasses                 from identity

  Face spoofing           Photo/video shown to    Do not rely on face
                          camera                  recognition as
                                                  authentication

  Application killed      User/admin/attacker     Startup recovery,
                          terminates process      health monitoring; no
                                                  absolute guarantee

  Lock API fails          Session/system state    Log, retry safely,
                                                  surface error

  High battery usage      Excessive frame         Adaptive sampling and
                          rate/model inference    profiling

  Camera shutter closed   User privacy choice     Ask user to open it or
  at startup                                      disable camera-based
                                                  mode
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 17. Development roadmap

### Phase 0: Hardware and environment audit

-   Identify Windows 11 edition/build.
-   Identify webcam model, supported resolutions, frame rates, and
    privacy shutter.
-   Confirm camera permission settings.
-   Confirm Bluetooth adapter and Android phone BLE behaviour.
-   Check whether Windows Presence Sensing is available.
-   Check for accessible motion sensors.
-   Record CPU, RAM, GPU, and battery characteristics.

### Phase 1: Safe Windows lock proof of concept

-   Build a tiny app that calls `LockWorkStation`.
-   Add a manual test button.
-   Verify that it locks the actual Windows session.
-   Verify normal sign-in unlock.
-   Add basic event logging.

### Phase 2: Camera capture and diagnostics

-   Enumerate webcam devices.
-   Capture frames.
-   Display a local preview and monitoring indicator.
-   Detect camera errors, freeze, and device changes.
-   Test camera contention with Windows Hello and video-call
    applications.

### Phase 3: Camera integrity detection

-   Implement brightness, histogram, local variance, edge density,
    sharpness, entropy, and frame difference.
-   Build calibration.
-   Create a test set: normal room, lights off, hand, finger, cloth,
    paper, partial cover, full cover, lens smear, camera shutter.
-   Tune false-positive/false-negative trade-offs.
-   Add temporal debounce and event logging.

### Phase 4: Automatic lock policy

-   Add owner presence estimation.
-   Add configurable absence timer.
-   Add obstruction lock rule.
-   Add strict, balanced, and adaptive modes.
-   Add safe recovery and diagnostics.

### Phase 5: Hand and face perception

-   Integrate MediaPipe hand/face models if useful.
-   Add pre-tampering cues.
-   Add optional owner recognition only after privacy and model
    licensing review.

### Phase 6: Android Bluetooth proximity

-   Enroll phone.
-   Scan for BLE signals.
-   Test phone screen on/off, battery saver, background behaviour, and
    different distances.
-   Implement smoothing and disconnect grace periods.
-   Combine phone absence with other events.

### Phase 7: Advanced modules

-   USB storage event monitoring.
-   Windows presence sensor integration if available.
-   Motion sensor support if exposed.
-   Authenticated remote lock.
-   Optional local notifications and evidence snapshots.

### Phase 8: Packaging and release

-   Package as a Windows app.
-   Add signed release process if distributing.
-   Add dependency/model license inventory.
-   Add update mechanism only if securely implemented.
-   Perform privacy, security, performance, and usability testing.

------------------------------------------------------------------------

## 18. Testing plan

### 18.1 Camera obstruction test matrix

Test at minimum: - Normal room lighting. - Dim lighting. - Lights
switched off. - Sunlight changes. - Screen brightness changes. - Hand
covering lens quickly. - Hand covering lens slowly. - Finger covering
lens. - Cloth covering lens. - Paper covering lens. - Partial lens
obstruction. - Translucent material. - Camera privacy shutter. - Camera
unplugged (external camera test). - Camera disabled in Device Manager. -
Driver crash/restart. - Camera feed frozen. - Camera in use by another
app. - Owner visible while another hand covers camera. - Owner absent
while an object covers camera.

Measure: - Detection latency. - False-positive rate. - False-negative
rate. - CPU usage. - Battery impact. - Lock success rate.

### 18.2 Presence test matrix

-   Owner leaves briefly.
-   Owner looks down.
-   Owner turns head.
-   Owner moves outside camera frame but remains nearby.
-   Another person replaces owner.
-   Multiple people in frame.
-   Poor lighting.
-   Face partly occluded.

### 18.3 Bluetooth test matrix

-   Phone on desk beside laptop.
-   Phone in pocket.
-   Phone in another room.
-   Phone screen off.
-   Android battery saver enabled.
-   Bluetooth toggled off.
-   Temporary interference.
-   Laptop sleeps and wakes.
-   Phone reconnects after interruption.

### 18.4 Security tests

-   App crash.
-   Windows restart.
-   User logoff.
-   Windows lock/unlock.
-   Permission revoked.
-   Camera removed.
-   Database locked/corrupted.
-   Storage full.
-   Invalid remote command.
-   Replayed remote command.
-   Unauthorized phone attempting lock command.

Do not claim security effectiveness based on a single successful demo.
Maintain a test log and quantify performance.

------------------------------------------------------------------------

## 19. Licensing and cost

The core project can be developed without paid services.

  -----------------------------------------------------------------------
  Component               Cost model              Important note
  ----------------------- ----------------------- -----------------------
  Python                  Free/open source        Check bundled
                                                  dependencies

  OpenCV                  Free/open source        Verify version and
                                                  third-party components

  MediaPipe               Free/open source        Check model asset terms

  SQLite                  Public domain           Suitable for local
                                                  storage

  Bleak                   Free/open source        BLE support depends on
                                                  hardware/OS

  PySide6                 LGPLv3/GPLv3 or         Follow Qt licensing;
                          commercial terms        evaluate deployment
                                                  obligations

  CustomTkinter           Free/open source        Check current license

  ONNX Runtime            MIT                     Model license is
                                                  separate

  PyTorch                 BSD-style               Check model and dataset
                                                  terms

  Ultralytics             AGPL-3.0 or enterprise  Important for
                          options                 proprietary
                                                  distribution

  Windows APIs            Included in Windows     Windows license and API
                          SDK/runtime             restrictions apply
  -----------------------------------------------------------------------

"Free to use" does not automatically mean "free of all distribution
obligations." Keep a software bill of materials and a license inventory
for every package, model, dataset, and bundled binary.

No paid cloud service is required for the core architecture. A phone
companion app and local LAN communication can also be implemented
without a hosted backend.

------------------------------------------------------------------------

## 20. Existing Windows features and related projects

### Windows 11 Presence Sensing

Microsoft documents built-in presence sensing, including Lock on Leave
and Wake on Approach. It requires compatible hardware. It is worth
checking before implementing a duplicate feature.

Reference:
https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/sensors-presence-sensing

### Windows camera APIs

Microsoft documents camera capture through MediaCapture and related
Windows APIs. A native implementation may provide better device
lifecycle and permission integration than a simple camera-index loop.

References: -
https://learn.microsoft.com/en-us/windows/apps/develop/camera/camera -
https://learn.microsoft.com/en-us/uwp/api/windows.media.capture.mediacapture

### Windows API reference

The Win32 API reference covers locking, devices, sensors, networking,
and other desktop integration points:
https://learn.microsoft.com/en-us/windows/win32/api/

### Open-source project research

Projects previously identified as potentially relevant for design
inspiration: - Desk Guard: https://github.com/Todilo/desk-guard -
CrySence: https://github.com/crymetr/crysence

Treat these as projects to inspect, not as independently validated
security products. Before reusing code, verify repository availability,
recent maintenance, actual feature implementation, license,
dependencies, and security quality. Do not copy claims from project
descriptions without testing.

------------------------------------------------------------------------

## 21. Recommended MVP scope

The first useful release should remain small and dependable.

**Must-have** 1. Windows 11 desktop/tray app. 2. Real Windows session
locking. 3. Webcam capture and health monitoring. 4. Camera obstruction
detection using multiple image features. 5. Camera freeze/unavailable
detection. 6. Configurable owner absence timer. 7. Local event log. 8.
Monitoring indicator and privacy controls. 9. Strict/balanced policy
settings. 10. Diagnostics and test mode.

**Should-have** 1. MediaPipe hand approach detection. 2. Optional
face/person presence. 3. Android BLE proximity. 4. USB storage event
logging. 5. Optional snapshot evidence with retention controls.

**Later / experimental** 1. Owner face recognition. 2. Custom trained
obstruction classifier. 3. Remote Android lock. 4. Hardware motion
sensor support. 5. Shoulder-surfing detection. 6. Adaptive risk scoring.
7. Tamper-evident event logs.

Do not begin with a large AI model. First prove that a calibrated
classical-vision detector can reliably distinguish ordinary scene
changes from lens obstruction.

------------------------------------------------------------------------

## 22. Key engineering principles

-   The camera-obstruction detector must work even if no face is ever
    detected.
-   Darkness alone is not proof of obstruction.
-   Camera loss is not automatically proof of malicious tampering.
-   Use a calibrated multi-feature classifier and temporal persistence.
-   Keep presence, identity, camera health, and physical movement as
    separate signals.
-   Use a central policy engine to decide actions.
-   Lock using the real Windows API.
-   Keep all core decisions local.
-   Do not collect or retain continuous video by default.
-   Do not use face recognition as a substitute for Windows
    authentication.
-   Treat Bluetooth as a noisy proximity signal, not a precise
    rangefinder.
-   Treat laptop motion sensing as hardware-dependent.
-   Test on the actual target laptop; webcam behaviour differs
    substantially by manufacturer and driver.
-   Make all automatic locking thresholds configurable.
-   Prefer explainable rules before complex AI.
-   Maintain a dependency and model license inventory.

------------------------------------------------------------------------

## 23. Research references

The following primary documentation is the recommended starting point
for implementation. Product behaviour and package APIs should be
rechecked against the exact versions selected for development.

1.  **Microsoft -- Windows 11 Presence Sensing**\
    https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/sensors-presence-sensing\
    Explains supported presence hardware and Windows features such as
    Lock on Leave and Wake on Approach.

2.  **Microsoft -- Camera development for Windows apps**\
    https://learn.microsoft.com/en-us/windows/apps/develop/camera/camera\
    Camera capture, MediaCapture, frame readers, formats, and camera
    lifecycle guidance.

3.  **Microsoft -- MediaCapture API**\
    https://learn.microsoft.com/en-us/uwp/api/windows.media.capture.mediacapture\
    Windows API for capturing photos, video, and camera frames.

4.  **Microsoft -- Win32 API reference**\
    https://learn.microsoft.com/en-us/windows/win32/api/\
    Primary reference for Windows desktop APIs.

5.  **Microsoft -- Streaming media device driver design**\
    https://learn.microsoft.com/en-us/windows-hardware/drivers/stream/\
    Webcam driver, privacy shutter, and camera pipeline background.

6.  **Microsoft -- Devices and sensors**\
    https://learn.microsoft.com/en-us/windows/apps/develop/devices-and-sensors\
    Windows device, Bluetooth, and sensor integration overview.

7.  **Microsoft -- Device capabilities**\
    https://learn.microsoft.com/en-us/windows/apps/develop/devices-sensors/enable-device-capabilities\
    Camera, USB, HID, and Bluetooth capability considerations.

8.  **Google -- MediaPipe**\
    https://ai.google.dev/edge/mediapipe/solutions/guide\
    On-device perception framework and solution documentation.

9.  **OpenCV documentation**\
    https://docs.opencv.org/\
    Camera capture and image processing operations.

10. **ONNX Runtime documentation**\
    https://onnxruntime.ai/docs/\
    Local model inference and execution providers.

11. **PyTorch documentation**\
    https://pytorch.org/docs/stable/index.html\
    Model training and computer vision development.

12. **Ultralytics documentation**\
    https://docs.ultralytics.com/\
    YOLO model use, training, tracking, and licensing information.

13. **Bleak documentation**\
    https://bleak.readthedocs.io/en/stable/\
    Python BLE scanning and GATT access, including platform-specific
    considerations.

14. **SQLite documentation**\
    https://www.sqlite.org/docs.html\
    Local embedded database reference.

15. **PySide6 documentation**\
    https://doc.qt.io/qtforpython-6/\
    Python bindings for Qt desktop application development.

16. **Python ctypes documentation**\
    https://docs.python.org/3/library/ctypes.html\
    Calling Windows DLL APIs from Python.

17. **Python logging documentation**\
    https://docs.python.org/3/library/logging.html\
    Application and diagnostic logging.

------------------------------------------------------------------------

## 24. Glossary

-   **BLE:** Bluetooth Low Energy, a low-power wireless communication
    technology.
-   **Camera obstruction:** Partial or complete blockage of the camera's
    optical view.
-   **Camera integrity:** Whether the camera stream is available,
    changing normally, and plausibly showing a scene.
-   **Debounce:** Requiring a signal to persist for a short interval
    before acting.
-   **Edge density:** A measure of how much boundary/detail structure
    exists in an image.
-   **Entropy:** A measure of image information or distribution
    complexity.
-   **Face embedding:** A numerical representation generated by a face
    model for similarity comparison.
-   **Hysteresis:** Different thresholds or timing for entering and
    leaving a state, preventing rapid toggling.
-   **Inference:** Running a trained model to produce predictions.
-   **Luminance:** Perceived brightness component of an image.
-   **MediaCapture:** Windows API family for camera and media capture.
-   **ONNX:** Open Neural Network Exchange model format.
-   **Optical flow:** Estimation of apparent motion between image
    frames.
-   **Presence detection:** Estimating whether a person is near or in
    front of the laptop.
-   **Risk score:** A policy-engine value combining multiple signals and
    their confidence.
-   **Session lock:** Windows' real lock state, requiring normal user
    authentication to return.
-   **SFace:** A face feature extraction/recognition model available in
    the OpenCV ecosystem.
-   **YuNet:** A lightweight face detection model in the OpenCV
    ecosystem.

------------------------------------------------------------------------

## 25. Product definition in one paragraph

SILENTWATCH is a free-first, local-first Windows 11 laptop security
application that monitors webcam integrity, user presence, optional
owner identity, and optional Android phone proximity. Its signature
capability is detecting camera obstruction even when an approaching
person never presents their face to the webcam. It combines image
brightness, texture, spatial uniformity, edge structure, temporal
change, camera health, and optional hand detection to identify likely
tampering. A central policy engine evaluates these signals and locks the
real Windows session through the Windows API when configured security
conditions are met. All core processing can run locally, with optional
local event logging and user-controlled evidence retention. The design
prioritizes privacy, explainability, low resource usage, and honest
handling of hardware limitations.
