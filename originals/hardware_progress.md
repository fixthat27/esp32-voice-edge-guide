# ESP32-S3 Offline Voice Command — Hardware & Development Progress

> **Project:** `esp32_voice_edge`  
> **Last updated:** 2026-11-13  
> **Target:** Self-trained, offline voice-command recognition on ESP32-S3 using Keras, TensorFlow Lite (INT8) and TensorFlow Lite for Microcontrollers (TFLM).  
> **Primary constraint:** No cloud service or third-party wake-word commissioning is required for the custom TinyML path.

---

## 1. Project objective and system boundary

The project is developing an embedded voice node that listens to a microphone, detects a user-defined wake word, classifies a small set of commands, and triggers local actions. The first target is a self-contained ESP32-S3 implementation. A separate system-level architecture may later use an Orange Pi as a local gateway for more complex ASR/NLU and MQTT processing; that gateway is not a dependency of the standalone TinyML experiment.

There are therefore two related but distinct tracks:

1. **Standalone TinyML track (current learning target):** microphone → audio preprocessing → custom wake-word/command model → confidence check → GPIO action. The inference path runs locally on the ESP32-S3.
2. **Smart-home integration track (system extension):** ESP32-S3 captures audio or recognized intent → local network → Orange Pi/FastAPI → ASR/NLU → MQTT → LogicMachine → KNX/DALI. Internet access is optional, not part of the required local path.

Do not conflate a small-vocabulary command classifier with general-purpose speech recognition. A compact TinyML model can recognize a defined vocabulary; it is not expected to transcribe arbitrary speech like Faster-Whisper.

## 2. Hardware inventory and wiring

### 2.1 Confirmed hardware

| Component | Hardware / interface | Status |
|---|---|---|
| Main MCU | ESP32-S3 N16R8 DevKit, USB-C, 16 MB flash, 8 MB PSRAM | Available |
| Microphone | INMP441 I2S digital MEMS microphone, breakout with L/R select | Available; Stage 1 hardware test completed |
| Speaker amplifier | MAX98357A I2S amplifier + speaker | Available; Stage 1 hardware test completed |
| Display | SSD1306 OLED, 128×64, I2C | Available; Stage 1 hardware test completed |
| Development framework | ESP-IDF, project built with ESP-IDF v6.1 | Configured |
| Development host | Windows, PowerShell; project path `D:\Alpha CCI Home\esp32_voice_edge` | Configured |

### 2.2 Current `board_config.h` pin map

The following is the latest recorded project configuration. Treat the source file in the repository as authoritative if it has since changed.

| Peripheral | Signal | ESP32-S3 GPIO |
|---|---|---:|
| INMP441 | BCLK / SCK | 17 |
| INMP441 | WS / LRCLK | 16 |
| INMP441 | SD / DOUT | 18 |
| MAX98357A | BCLK | 13 |
| MAX98357A | WS / LRC | 14 |
| MAX98357A | DIN | 12 |
| SSD1306 | SDA | 5 |
| SSD1306 | SCL | 4 |

Other recorded configuration:
- Audio sample rate: **16,000 Hz**
- Audio read frame size: **256 samples**
- OLED I2C address: **0x3C**
- OLED resolution: **128×64**
- INMP441 L/R: connect to GND for the left channel when using the corresponding left-channel configuration.
- Connect all module grounds to ESP32-S3 GND. Confirm each module's supply-voltage requirements before powering it.

**Important:** GPIO assignments are board/project configuration, not universal pin recommendations. Do not copy older experimental pin maps into the current firmware without reconciling them with `board_config.h`. In particular, earlier notes contain alternative GPIO assignments; the table above is the current recorded mapping.

### 2.3 Hardware bring-up status

The initial hardware stage has been reported as completed:
- ESP32-S3 build, flash and serial-monitor workflow established.
- OLED basic display test performed.
- INMP441 microphone input / RMS test performed.
- MAX98357A speaker output / tone test performed.

A previous issue was observed where the test tone appeared to repeat or remain active instead of playing for the intended short duration. Treat that as a firmware test issue to re-check if audio playback is reused; do not assume it is relevant to microphone inference.

Typical command used in the project:
```powershell
idf.py -p COM13 flash monitor
```
The COM port can change depending on which USB connector and device interface are used. The ESP32-S3 DevKit may expose more than one USB connection; verify the enumerated COM port before flashing.

## 3. Current software and model workflow

### 3.1 Target inference pipeline

```text
INMP441
   │ I2S
   ▼
16 kHz mono audio capture
   │ PCM samples
   ▼
Framing / windowing
   │
   ▼
MFCC feature extraction
   │
   ▼
Quantized TinyML model (INT8)
   │
   ▼
Class scores + confidence threshold
   │
   ├── low confidence / unknown → reject
   │
   └── accepted command → GPIO action / local event
```

The currently planned feature configuration is:
- Sample rate: **16 kHz**
- Frame/window length: **25 ms** (400 samples)
- Frame stride/hop: **10 ms** (160 samples)
- MFCC coefficients: **13**
- A one-second input window produces approximately **98 frames × 13 coefficients**, depending on exact padding and framing conventions.

The training and firmware implementations must use the same sample rate, framing, window function, mel scale, MFCC normalization, coefficient ordering and quantization parameters. A mismatch between desktop preprocessing and embedded preprocessing can make a correctly trained model perform poorly on the device.

### 3.2 Training-to-firmware workflow

1. **Define labels and recording protocol.** Start with a small, fixed vocabulary. Include `unknown` / background / silence examples so the model is not forced to classify every sound as a valid command.
2. **Collect and label audio.** Record multiple utterances per label, across different sessions, distances, speaking volumes and background conditions. Split training/validation/test by recording session or speaker where possible, not by randomly splitting adjacent frames from the same recording.
3. **Prepare data.** Resample to 16 kHz mono PCM, trim or pad to a fixed duration, and apply the same preprocessing expected by firmware.
4. **Extract features.** Generate MFCC tensors using a reproducible preprocessing implementation. Save configuration and normalization values with the model.
5. **Train in Keras.** Begin with a small CNN; evaluate a DS-CNN (depthwise-separable CNN) if model size and inference cost need improvement.
6. **Evaluate before quantization.** Inspect per-class precision/recall, confusion matrix, false acceptances, false rejections and performance on unknown/background samples.
7. **Convert and quantize.** Convert to TensorFlow Lite with full INT8 quantization using a representative dataset. Verify that input/output tensor types, scales and zero-points are understood.
8. **Validate the exported model on the PC.** Compare float Keras and INT8 TFLite predictions on the same held-out samples. Investigate any material accuracy regression.
9. **Integrate TFLite Micro.** Add the model and required operators to the ESP-IDF firmware. Store the model as a C/C++ byte array or a generated model source file.
10. **Implement embedded preprocessing.** Capture I2S audio, compute the matching MFCC features, quantize them exactly as expected by the model, and invoke the TFLM interpreter.
11. **Add decision logic.** Apply a confidence threshold, optionally require repeated detections, add a cooldown/debounce period, and reject uncertain predictions.
12. **Run on-device tests.** Test from the actual microphone, not only pre-recorded files. Log class scores, latency, memory use and false triggers over repeated trials.

### 3.3 Wake word versus command classification

These are separate tasks and should be developed separately.

- **Keyword spotting (KWS):** detect a custom wake phrase among continuous audio, with background/noise as negative examples. The wake phrase is trained from the user's own recordings and other permitted speakers; no external commissioning service is inherently required for a custom Keras/TFLM model.
- **Command classification:** after wake-word detection, classify a short command from a predefined set such as `light_on`, `light_off`, `music_on`, `music_off`, or `unknown`.
- **Speaker verification:** determining whether the speaker is an enrolled person is a different biometric problem. A wake-word model alone does not authenticate a speaker. Do not treat wake-word recognition as secure identity verification; a replayed recording may trigger it. Any security-sensitive action needs a separate threat model and stronger verification.

For a first experiment, build and measure the command classifier before combining it with continuous wake-word detection. This isolates audio preprocessing and model-inference problems.

## 4. Progress snapshot

| Area | Current status | Evidence / interpretation |
|---|---|---|
| ESP32-S3 hardware setup | Completed initial bring-up | Stage 1 tests reported complete |
| ESP-IDF environment | Set up | ESP-IDF v6.1 build/flash workflow used |
| I2S microphone capture | Basic test completed | INMP441 and RMS test were part of Stage 1 |
| OLED output | Basic test completed | SSD1306 128×64, I2C 0x3C |
| Speaker output | Basic test completed, one test-timing issue noted | MAX98357A tone test; re-verify if reused |
| Board pin configuration | Recorded | Current GPIO map listed in Section 2.2 |
| Dataset for custom model | Not yet confirmed complete | Needs a versioned, labeled dataset |
| Keras model training | Not yet confirmed complete | Planned |
| INT8 TFLite conversion | Not yet confirmed complete | Planned |
| TFLite Micro integration | Not yet confirmed complete | Planned |
| Embedded MFCC parity | Not yet confirmed complete | Critical integration task |
| On-device command inference | Not yet confirmed complete | Main next milestone |
| Custom wake-word model | Design direction selected; implementation pending | Must be trained and evaluated |
| Orange Pi / MQTT integration | Separate later integration track | Not required for standalone TinyML validation |

This table intentionally distinguishes completed hardware tests from model work that has only been planned or discussed. Update each row only after a reproducible test has passed.

## 5. Work to do — recommended order

### Milestone 1 — Freeze the hardware/audio baseline

- [ ] Review the actual `board_config.h` and confirm it matches the physical wiring.
- [ ] Confirm I2S microphone output is 16 kHz, mono, signed PCM with the expected channel selection.
- [ ] Capture several seconds of raw microphone samples and save them as WAV on the host.
- [ ] Check waveform, RMS, clipping, DC offset and channel correctness.
- [ ] Repeat capture under quiet, speech and background-noise conditions.
- [ ] Resolve or isolate the earlier speaker tone timing issue if speaker playback remains in scope.

**Deliverable:** a stable microphone-capture test and a small set of known-good WAV recordings.

### Milestone 2 — Build a reproducible dataset

- [ ] Choose an initial set of 4–7 command labels plus `unknown` and background/noise.
- [ ] Define one fixed recording duration and a consistent label convention.
- [ ] Record multiple examples per class over multiple sessions.
- [ ] Include different distances, speaking volumes and realistic room noise.
- [ ] Keep a speaker/session-aware train, validation and test split.
- [ ] Document sample rate, bit depth, channel count and preprocessing parameters.

**Deliverable:** versioned dataset with a manifest and a reproducible preprocessing script.

### Milestone 3 — Train the first Keras classifier

- [ ] Implement a desktop MFCC extraction pipeline.
- [ ] Visualize MFCC features for several samples and verify labels.
- [ ] Train a small CNN baseline.
- [ ] Record training curves, confusion matrix and per-class metrics.
- [ ] Test unknown/background rejection and inspect false positives.
- [ ] Save the model and the exact preprocessing configuration.

**Deliverable:** baseline Keras model and evaluation report.

### Milestone 4 — Convert to INT8 TFLite

- [ ] Create a representative dataset from training samples.
- [ ] Convert using full integer quantization.
- [ ] Confirm INT8 input/output tensor details and quantization parameters.
- [ ] Compare Keras and TFLite outputs on the held-out test set.
- [ ] Measure model file size and desktop inference latency.

**Deliverable:** validated `.tflite` model and conversion script.

### Milestone 5 — Run inference on ESP32-S3

- [ ] Add TFLite Micro to the ESP-IDF project using a version compatible with the selected ESP-IDF/toolchain.
- [ ] Identify and include only the model operators actually required.
- [ ] Allocate the tensor arena and measure memory requirements.
- [ ] Implement embedded MFCC extraction to match the desktop pipeline.
- [ ] Feed test features to the model before enabling live microphone capture.
- [ ] Compare serial-logged output against desktop TFLite for identical input.
- [ ] Enable live I2S capture and run repeated command tests.
- [ ] Record inference latency, RAM/PSRAM use, flash use and classification metrics.

**Deliverable:** ESP32-S3 classifies commands from the physical microphone without a network connection.

### Milestone 6 — Add custom wake-word detection

- [ ] Choose and document the custom wake phrase.
- [ ] Collect positive examples and hard negative examples (similar-sounding phrases, ordinary conversation, TV/audio playback).
- [ ] Train a dedicated KWS model; do not assume the command classifier can serve as a continuous wake-word detector.
- [ ] Evaluate false accepts per hour and missed detections across realistic conditions.
- [ ] Add a rolling audio buffer and a state machine: idle → wake detected → command window → action → cooldown.
- [ ] Test replay attacks if the wake phrase is intended to gate sensitive actions.

**Deliverable:** custom wake-word detection running locally, with measured false-trigger and miss rates.

### Milestone 7 — Smart-home integration (after standalone validation)

- [ ] Define a compact command/event schema.
- [ ] Decide whether the ESP32 sends only recognized intents or audio chunks to the Orange Pi.
- [ ] Implement a LAN-local transport to the Orange Pi/FastAPI service.
- [ ] If sending audio, use a clear chunk format, sequence/timestamp metadata and reconnect handling.
- [ ] Run ASR/NLU on the Orange Pi and validate the resulting intent.
- [ ] Publish validated events to MQTT; keep LogicMachine/KNX/DALI actuation behind backend authorization and validation.
- [ ] Test broker disconnects, Wi-Fi loss, duplicate messages and safe fallback behavior.

**Deliverable:** local-network smart-home voice pipeline, with the standalone TinyML path remaining independently testable.

## 6. Suggested repository structure

A possible structure for keeping training code separate from firmware:

```text
esp32_voice_edge/
├── firmware/
│   ├── main/
│   │   ├── app_main.c
│   │   ├── audio/
│   │   ├── features/
│   │   ├── inference/
│   │   └── actions/
│   ├── components/
│   │   └── tflite_micro/
│   ├── models/
│   │   └── command_model_data.cc
│   ├── board_config.h
│   └── CMakeLists.txt
├── ml/
│   ├── data/
│   │   ├── raw/
│   │   └── processed/
│   ├── notebooks/
│   ├── src/
│   │   ├── prepare_dataset.py
│   │   ├── extract_features.py
│   │   ├── train.py
│   │   ├── evaluate.py
│   │   └── convert_tflite.py
│   ├── models/
│   └── requirements.txt
├── test/
│   ├── audio_samples/
│   └── inference_vectors/
├── docs/
│   ├── hardware_and_progress.md
│   └── model_preprocessing.md
└── README.md
```

This is a suggested organization, not a claim that all these folders already exist. Keep generated model binaries and large raw datasets under deliberate version-control/LFS or external dataset policies.

## 7. Learning path and technical references

The following are primary documentation and implementation references. Read them in the order shown; use the official documentation as the source of truth for APIs and compatibility.

### A. ESP32-S3 and ESP-IDF

1. **ESP-IDF Programming Guide** — build system, components, FreeRTOS, peripherals and application structure.  
   https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/
2. **ESP-IDF I2S documentation** — standard-mode I2S configuration, channel setup and DMA audio transfer.  
   https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/i2s.html
3. **ESP32-S3 Technical Reference Manual** — peripheral and hardware details.  
   https://www.espressif.com/sites/default/files/documentation/esp32-s3_technical_reference_manual_en.pdf
4. **ESP-IDF examples** — inspect the I2S and peripheral examples that match the installed ESP-IDF version.  
   https://github.com/espressif/esp-idf/tree/master/examples

### B. Audio and feature extraction

5. **TensorFlow tutorial: Simple audio recognition** — a practical introduction to audio classification and spectrogram-based models.  
   https://www.tensorflow.org/tutorials/audio/simple_audio
6. ** librosa documentation** — useful for desktop-side audio inspection and MFCC experiments. Ensure its MFCC configuration is made equivalent to the embedded implementation before using it as a training pipeline.  
   https://librosa.org/doc/latest/feature.html
7. **TensorFlow Lite Micro** — embedded inference concepts, supported operators and integration guidance.  
   https://www.tensorflow.org/lite/microcontrollers
8. **TFLite Micro source repository** — reference kernels, examples and implementation details.  
   https://github.com/tensorflow/tflite-micro

### C. Keras, conversion and quantization

9. **Keras documentation** — model construction, training, evaluation and serialization.  
   https://keras.io/
10. **TensorFlow Lite post-training quantization** — representative datasets and integer quantization.  
    https://www.tensorflow.org/model_optimization/guide/quantization/post_training
11. **TensorFlow Lite converter guide** — converting a trained TensorFlow/Keras model to `.tflite`.  
    https://www.tensorflow.org/lite/convert

### D. Espressif speech stack — comparison track

12. **ESP-SR repository** — Espressif's speech-recognition framework, including AFE, wake-word and command-recognition components. Study it as a reference or comparison; it is not a replacement for the custom Keras/TFLM experiment.  
    https://github.com/espressif/esp-sr
13. **ESP-SR documentation** — component setup and supported speech features. Check release compatibility with the project's ESP-IDF version before integrating.  
    https://docs.espressif.com/projects/esp-sr/en/latest/

### E. Smart-home integration — later milestone

14. **FastAPI documentation** — local API service on the Orange Pi.  
    https://fastapi.tiangolo.com/
15. **Eclipse Mosquitto documentation** — MQTT broker configuration and operation.  
    https://mosquitto.org/documentation/
16. **MQTT specifications / OASIS** — protocol semantics and interoperability.  
    https://mqtt.org/mqtt-specification/

**Compatibility note:** The project uses ESP-IDF v6.1. Some third-party components and examples may target older ESP-IDF releases. Before adding a component, check its release notes, supported ESP-IDF versions, build instructions and license. Do not assume that a `master` branch example builds unchanged with the installed toolchain.

## 8. Engineering practices and acceptance criteria

Use measurable criteria rather than treating a successful compile as proof that the system works.

| Test | Minimum evidence to record |
|---|---|
| Microphone capture | Sample rate, channel, sample format, WAV playback, clipping/RMS |
| Feature parity | Same WAV produces matching or acceptably close desktop/embedded MFCC tensors |
| Model quality | Held-out confusion matrix, per-class precision/recall, unknown rejection |
| Quantization | Keras vs INT8 TFLite prediction comparison |
| Embedded inference | Correct labels from known test vectors; latency and tensor-arena size |
| Live command test | Repeated trials from physical mic, false accept and false reject counts |
| Wake-word test | False accepts per hour, miss rate, distance/noise conditions |
| Offline operation | Demonstrate inference and action with Wi-Fi disabled |
| Smart-home integration | MQTT payload validation, reconnect behavior, duplicate handling and safe failure |

Keep a short experiment log for every model version:
- Dataset version and split
- Feature configuration
- Model architecture and training parameters
- Evaluation metrics
- TFLite conversion settings
- Model size and quantization details
- Firmware commit, ESP-IDF version and measured device latency

## 9. Immediate next action

The most useful next step is **not** to start with wake-word training. First establish a reproducible audio dataset path:

1. Confirm the current GPIO map against `board_config.h`.
2. Record raw INMP441 audio at 16 kHz and save it as WAV.
3. Build a Python script that reads the WAV, computes and visualizes MFCC features, and exports fixed-shape tensors.
4. Use those exact tensors to train and evaluate a small Keras command classifier.
5. Only after desktop INT8 validation, port the same preprocessing and model to ESP32-S3/TFLite Micro.

This sequence separates microphone, feature-extraction, model and embedded-runtime errors. It also creates reusable test vectors for verifying that desktop and ESP32-S3 inference agree.

---

## 10. Project status update template

Append one entry whenever a milestone changes:

```text
Date:
Milestone:
Hardware / firmware commit:
Dataset or model version:
What was tested:
Test conditions:
Result / metrics:
Issues:
Next action:
```


---

# 11. MQTT integration — ESP32-S3 to Smart Home backend

> **Integration target:** Reuse the existing `smarthome-edge-poc` FastAPI/MQTT backend.  
> **Known repository path (Windows):** `D:\AlphaKNX\smarthome-edge-poc`  
> **Deployment direction:** validate on the Windows development machine first, then move the backend/broker workload to Orange Pi 3 LTS.

## 11.1 Recommended architecture

The ESP32-S3 should initially send a recognized, structured command to FastAPI over the local network. FastAPI remains the single authority for device mapping, validation and MQTT publishing.

```text
INMP441
   │ I2S audio
   ▼
ESP32-S3
   ├── Wake-word detection
   ├── Voice command classifier (TFLite Micro)
   ├── Confidence / unknown-command rejection
   └── Build structured command
          │
          │ HTTP POST over local Wi-Fi
          ▼
FastAPI — smarthome-edge-poc
   ├── API route (app/main.py)
   ├── Command validation / orchestration
   │      (app/services/command_service.py)
   ├── Device and action → topic/payload mapping
   │      (app/mqtt/topics.py)
   └── MQTT publish client
          (app/mqtt/client.py)
          │
          │ MQTT
          ▼
Mosquitto broker
   │
   │ MQTT
   ▼
LogicMachine MQTT client
   │
   ▼
Mapped LogicMachine object
   │
   ▼
KNX / DALI / physical device
```

The current development setup has used a Mosquitto Docker broker on the Windows machine, with LogicMachine acting as an MQTT client. The longer-term target is to deploy the local backend and broker on the Orange Pi. Keep the broker, API and LogicMachine on a reachable LAN and do not expose the MQTT broker or unauthenticated control API directly to the public internet.

### Why HTTP from ESP32 first?

- The existing backend already owns MQTT connectivity and topic conventions.
- Device names, room mapping, authorization and validation remain centralized.
- Firmware does not need to know LogicMachine-specific topics or payload formats.
- Backend changes can be made without reflashing every ESP32 node.
- HTTP request/response makes it straightforward to return accepted, rejected or failed command status to the device.

Direct ESP32 → MQTT can be evaluated later if there is a concrete requirement for lower overhead or broker-level device messaging. It should not be the first integration path because it duplicates routing and validation responsibilities.

## 11.2 Repository areas to reuse

The following paths are based on the previously established repository layout. Check the current working tree before editing; do not create duplicate services if equivalent functionality already exists.

| Existing file / area | Responsibility in this integration |
|---|---|
| `app/main.py` | FastAPI application and API route registration |
| `app/services/command_service.py` | Validate and execute normalized smart-home commands |
| `app/mqtt/client.py` | MQTT client lifecycle, connection and publish operation |
| `app/mqtt/topics.py` | Central topic naming and MQTT payload/topic mapping |
| `app/config.py` | API, broker and environment configuration |

Existing API functionality has included device-specific control such as the technical-office light toggle. Reuse the existing service path behind that route. If the repository does not yet expose a generic voice-command endpoint, add a thin API route that calls the existing command service rather than implementing a second MQTT publishing path.

A possible generic endpoint is `POST /api/v1/commands`. Treat this as an integration endpoint to verify/add in the repository, not as a confirmed existing route. Keep any existing device-specific routes working during the transition.

## 11.3 Command contract between ESP32 and FastAPI

The ESP32 should send the *recognized intent*, not an MQTT topic. A compact JSON request could look like this:

```json
{
  "request_id": "esp32s3-01-00001234",
  "source": "esp32_tinyml",
  "device_id": "technical-office-light",
  "intent": "device_control",
  "action": "turn_on",
  "value": true,
  "confidence": 0.94,
  "model_version": "command-cnn-v1"
}
```

Field semantics:

| Field | Meaning |
|---|---|
| `request_id` | Unique ID for tracing and duplicate detection |
| `source` | Identifies the originating voice node |
| `device_id` | Logical device identifier understood by the backend |
| `intent` | High-level command category |
| `action` | Normalized action, independent of MQTT topic |
| `value` | Optional typed target value |
| `confidence` | Model confidence, used as one input to backend policy |
| `model_version` | Firmware/model traceability |

This is a proposed contract. Align field names and accepted values with the repository's actual Pydantic schemas and `command_service.py` before implementation. Do not let the model generate arbitrary topic strings. The backend must map an allowlisted `device_id` and `action` to the correct topic and payload.

For a first test, use only one known device and two actions (`turn_on`, `turn_off`). Expand to more devices after the complete round trip is reliable.

## 11.4 End-to-end runtime workflow

1. ESP32-S3 captures audio from INMP441 using I2S.
2. The wake-word detector activates the command-listening state.
3. TFLite Micro classifies the command.
4. Firmware rejects `unknown`, low-confidence and ambiguous predictions. Do not send a control request for a rejected prediction.
5. Firmware maps the accepted class to a fixed command structure. For example, `light_on` becomes `device_id=technical-office-light`, `action=turn_on`, `value=true`.
6. Firmware creates a unique `request_id` and sends an HTTP POST to the FastAPI LAN address.
7. FastAPI validates the request schema, device allowlist, action and any authorization policy.
8. The command service resolves the logical device/action using the existing backend mapping.
9. The MQTT layer publishes the repository-defined topic and payload using the existing MQTT client.
10. LogicMachine receives the MQTT message and updates the mapped object / physical KNX or DALI device.
11. FastAPI returns a result to ESP32. The response must distinguish API acceptance from confirmed physical device state.
12. ESP32 displays or announces the result, then enters a short cooldown to avoid repeated triggers.

```text
Voice → KWS/KWS command model → confidence gate
                                  │
                           accepted command?
                            /           \
                          no             yes
                          │               │
                       ignore       HTTP POST JSON
                                          │
                                      FastAPI
                                          │
                                 validate + authorize
                                          │
                                   command_service
                                          │
                                  topics.py mapping
                                          │
                                    MQTT client
                                          │
                                      Mosquitto
                                          │
                                     LogicMachine
                                          │
                                   KNX / DALI device
                                          │
                                  status / response
                                          │
                                       ESP32
```

## 11.5 API response and state semantics

Use explicit response semantics so firmware does not mistake a successful HTTP request for a successful physical action.

Example accepted response:

```json
{
  "request_id": "esp32s3-01-00001234",
  "status": "accepted",
  "message": "Command accepted for MQTT delivery"
}
```

Example rejected response:

```json
{
  "request_id": "esp32s3-01-00001234",
  "status": "rejected",
  "message": "Unknown device or unsupported action"
}
```

Recommended state distinction:

- `rejected`: validation or authorization failed; do not retry unchanged.
- `accepted`: backend accepted the request; this does not prove that LogicMachine actuated the device.
- `published`: backend MQTT client reports that the message was published/delivered according to its MQTT QoS semantics; this still does not prove the physical device changed state.
- `confirmed`: a separate state report or acknowledgement confirms the device state.
- `failed` / `timeout`: backend or downstream operation did not complete within the defined timeout.

Only display “Light is ON” when a trustworthy state confirmation exists. Otherwise display a message such as “Command sent” or “Command accepted”.

## 11.6 Network and firmware implementation plan

### ESP32-S3 firmware tasks

- [ ] Configure Wi-Fi station mode and reconnect handling.
- [ ] Keep SSID/password and API address in configuration, not hard-coded across source files.
- [ ] Add an HTTP client component using the ESP-IDF HTTP client API compatible with the installed ESP-IDF v6.1.
- [ ] Serialize the normalized command as JSON.
- [ ] Set request timeout and parse HTTP status plus response JSON.
- [ ] Generate a unique request ID for each accepted command.
- [ ] Add bounded retry behavior for transient network errors.
- [ ] Do not blindly retry a command after an ambiguous timeout unless backend idempotency is implemented.
- [ ] Log command class, confidence, request ID, HTTP status and elapsed time.
- [ ] Keep TinyML inference operational when Wi-Fi or backend is unavailable; report that remote execution is unavailable rather than pretending the action succeeded.

### FastAPI repository tasks

- [ ] Inspect `app/main.py` and existing route/schema definitions.
- [ ] Inspect `app/services/command_service.py` to identify the existing command execution entry point.
- [ ] Inspect `app/mqtt/client.py` for connection lifecycle, publish method, QoS and error handling.
- [ ] Inspect `app/mqtt/topics.py` for the actual topic names and payload formats used by LogicMachine.
- [ ] Inspect `app/config.py` and move host/port/credentials to environment configuration where appropriate.
- [ ] Add or adapt a typed request schema for ESP32 voice commands.
- [ ] Add a generic command route only if the existing API does not already provide the required interface.
- [ ] Route the new API through `command_service.py`; do not publish from the route handler directly.
- [ ] Validate device/action pairs against an allowlist.
- [ ] Add request ID logging and duplicate-request handling.
- [ ] Return structured status and error responses.
- [ ] Add tests using a mocked MQTT client before testing against the live broker.

### Broker and LogicMachine tasks

- [ ] Confirm Mosquitto host, port and listener configuration on the Windows Docker setup.
- [ ] Ensure ESP32 and FastAPI can reach the API host over the same LAN.
- [ ] Ensure FastAPI can reach the broker address from its actual runtime environment. `localhost` inside a container refers to that container, not automatically to the Windows host or another container.
- [ ] Confirm the actual MQTT topic and payload expected by LogicMachine from `topics.py` and the LM configuration.
- [ ] Use unique MQTT client IDs. Earlier tests showed that duplicate client IDs (for example, reusing `logicmachine_test`) can cause a session-taken-over disconnect.
- [ ] Configure broker credentials and topic ACLs before moving beyond a trusted development network.
- [ ] Verify LogicMachine reconnect and retained/session behavior rather than assuming delivery from a successful API response.

## 11.7 LAN addressing and deployment

During development, the ESP32 must call the Windows host's LAN IPv4 address, not `127.0.0.1` or `localhost`. Those loopback addresses refer to the ESP32 itself when used by its HTTP client.

Example configuration (replace with the actual development machine address and port):

```c
#define WIFI_SSID       CONFIG_WIFI_SSID
#define API_BASE_URL    "http://192.168.1.50:8000"
#define COMMAND_ENDPOINT "/api/v1/commands"
```

The IP above is illustrative only. Prefer a DHCP reservation or stable hostname if the LAN and ESP-IDF networking setup support it. Ensure Windows Firewall permits inbound API traffic on the selected port, and bind FastAPI to a LAN-reachable interface rather than loopback only.

Deployment stages:

**Stage A — Windows development**
- Mosquitto broker runs in Docker on Windows.
- FastAPI runs on Windows (or in its existing container configuration).
- LogicMachine connects to the broker.
- ESP32-S3 joins the same LAN and sends HTTP commands to FastAPI.
- Validate one light on/off flow end to end.

**Stage B — Orange Pi deployment**
- Move the FastAPI application to Orange Pi 3 LTS.
- Move or configure Mosquitto on the Orange Pi according to the deployment plan.
- Update LogicMachine's broker address and ESP32's API base URL.
- Configure services to start automatically and verify restart/reconnect behavior.
- Repeat the same end-to-end tests without changing the command contract.

Keep the API and broker as separate configurable addresses. Do not assume that they share a host or that a Docker container can reach another service through `localhost`.

## 11.8 Reliability, security and observability

- **Confidence threshold:** establish it from validation data and false-accept testing, not an arbitrary model score. Use a higher threshold for actions with greater consequences.
- **Allowlist:** firmware maps known labels to known logical devices/actions; backend independently validates them.
- **Idempotency:** use `request_id` to prevent duplicate execution when a retry occurs after an uncertain timeout.
- **Timeouts:** set finite connection and response timeouts. Avoid blocking the audio/inference task indefinitely on HTTP.
- **Task separation:** keep I2S capture/inference responsive; queue accepted commands for a network task rather than performing lengthy network operations inside the audio-processing loop.
- **Reconnect:** retry Wi-Fi/API connectivity with bounded backoff. Do not create an unbounded queue of stale control commands.
- **Transport security:** for a trusted isolated LAN prototype, plain HTTP may be used temporarily. Before production, add authentication and appropriate transport protection; never expose an unauthenticated control endpoint to the internet.
- **Logging:** correlate ESP32 serial logs, FastAPI request logs, MQTT publish logs and LogicMachine logs using the same `request_id`.
- **State feedback:** if the UI needs to report actual device state, add a separate state-report path from LogicMachine/backend to ESP32. Command acknowledgement alone is not state feedback.

## 11.9 Integration test plan

| Test | Expected result |
|---|---|
| Valid `light_on` recognized | ESP32 sends one valid HTTP request; backend maps it to the existing MQTT command |
| Valid `light_off` recognized | Same path with OFF action |
| Low-confidence audio | No HTTP request and no device action |
| Unknown command | Rejected locally; no MQTT publish |
| Unsupported device/action in API request | FastAPI rejects it; no MQTT publish |
| FastAPI unavailable | ESP32 reports backend unavailable; inference remains operational |
| Broker unavailable | Backend reports publish failure/timeout; no false success response |
| LogicMachine disconnected | Backend acceptance is not represented as confirmed physical state |
| HTTP response lost after publish | Retry does not execute the same command twice when idempotency is enabled |
| Wi-Fi reconnect | ESP32 reconnects and can send a new command |
| Orange Pi deployment | Same API contract and MQTT mapping work after endpoint/configuration changes |

## 11.10 MQTT integration learning references

1. **ESP-IDF HTTP Client** — implement the ESP32 → FastAPI request path.  
   https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/protocols/esp_http_client.html
2. **ESP-IDF Wi-Fi** — station mode and network event/reconnect handling.  
   https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/wifi.html
3. **FastAPI request bodies** — define and validate the command JSON schema.  
   https://fastapi.tiangolo.com/tutorial/body/
4. **Pydantic models** — typed request/response contracts and validation.  
   https://docs.pydantic.dev/latest/concepts/models/
5. **Eclipse Paho Python client** — MQTT client behavior used by Python backends.  
   https://eclipse.dev/paho/files/paho.mqtt.python/html/
6. **Eclipse Mosquitto** — broker configuration, listeners, authentication and ACLs.  
   https://mosquitto.org/documentation/
7. **MQTT specification** — QoS, session and delivery semantics.  
   https://mqtt.org/mqtt-specification/

## 11.11 Immediate next steps for the MQTT handoff

Before writing ESP32 HTTP code, inspect the current `smarthome-edge-poc` source and record the exact:
- API route and Pydantic request schema;
- command-service method signature;
- MQTT publish method and QoS;
- topic and payload for the technical-office light;
- broker host/port as seen by the FastAPI runtime;
- LogicMachine state-feedback topic/object mapping, if available.

Then implement in this order:

1. Test the existing FastAPI command path from PowerShell or Python without ESP32.
2. Confirm that the command reaches Mosquitto and LogicMachine and changes the physical light.
3. Add/verify a generic voice-command API route that delegates to the existing command service.
4. Test that route using a fixed JSON payload.
5. Implement ESP32 Wi-Fi + HTTP client and send the same payload.
6. Connect the TinyML class labels to the fixed command mapping.
7. Test failures, duplicate requests and state feedback.
8. Move the unchanged API contract to Orange Pi.

**Important repository boundary:** this document uses the previously established repository structure and architecture, but the current repository source files were not attached or inspected in this session. Exact route names, topic strings, payload schemas and function signatures must be verified in the working tree before coding. Do not copy illustrative topic names or assume the proposed `/api/v1/commands` route already exists.
