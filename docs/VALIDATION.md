# Validation and remaining work

Prepared from the supplied documents on 2026-11-13. This is a guided reference implementation, not a hardware-certified release.

## Checks completed

- Portable C MFCC compiled with MSYS2 GCC 14.2.0 using `-O2 -Wall -Wextra -shared` without compiler warnings.
- All 11 host tests passed under Python 3.11.16 and NumPy 1.26.4. See `host_tests.txt` and `host_environment.txt`.
- C/Python MFCC parity passed for silence, broadband random PCM, a 440 Hz tone and a quiet noisy tone. Maximum absolute differences were 0.00002241, 0.00000441, 0.00002098 and 0.00003052 respectively. These are host numerical tests, not ESP32 latency or accuracy measurements.
- Policy tests cover wake gating, repeated detections, cooldown, unknown reset, timeout, ambiguity and non-finite scores.
- Service tests cover authentication, strict boolean schema validation, unsupported targets, low confidence, duplicate suppression, conflicting IDs, uncertain delivery and persistence across service instances.
- Dataset preparation completed on 54 explicitly synthetic clips, 18 in each split. Each split covered all six labels. It produced normalized arrays and metadata. Synthetic tones do not establish speech-recognition quality.
- Python source syntax compilation completed. An explicitly synthetic WAV and its unnormalized MFCC tensor are supplied in `test/inference_vectors/`.

An initial parity failure on the clean tone exposed float FFT roundoff. FFT scratch/window arithmetic was changed to double precision and the same test then passed. This is a correctness baseline; measure its CPU cost before continuous deployment.

The tested FastAPI/Starlette environment emits a deprecation warning about its httpx test-client integration. Tests passed. The warning and installed versions are retained in the evidence files; it does not establish future compatibility.

## Not validated here

- TensorFlow installation did not complete before the interrupted session. A subsequent import reported that TensorFlow was unavailable. CNN training, SavedModel/INT8 conversion, model operator inspection and float/INT8 evaluation were therefore not executed. The pinned ML requirements are proposed, not a tested environment lock.
- No user's speech dataset or trained model was supplied. No trained model, recognition accuracy or false-trigger rate is claimed. The exporter creates required firmware model files only after you train a model.
- ESP-IDF was not available on PATH. Neither capture firmware, optional TFLM inference nor optional HTTP transport was compiled with the ESP32 toolchain.
- The physical ESP32, microphone, amplifier, OLED and LogicMachine were not connected to this workspace. Wiring, I2S alignment, serial capture, embedded golden-vector output, RAM/PSRAM capacity and live behavior remain hardware tests.
- Continuous ring-buffer capture, two-model wake/command scheduling and the C/RTOS port of the host policy are integration work described in the workflow. The supplied firmware runs one-second bench windows with pauses.
- Wi-Fi station provisioning/reconnect must reuse your actual project. The optional queued HTTP transport requires integration and build testing. The included API defaults to shadow mode and has no live MQTT adapter.
- Existing backend route names, service signatures, MQTT topics/payloads, bus mappings, manual-override logic and physical state feedback were not verified because the referenced repositories were unavailable.

## Reproduce host checks

From the extracted bundle root, activate an environment with NumPy and the integration requirements, ensure GCC is on PATH, then run `tools/test_host.ps1`. A skipped C test does not count as parity validation. Follow milestone 5 for device testing and milestone 7 for network/physical testing.

To smoke-test the unverified ML path without collecting speech, create disposable synthetic fixtures with `python tools/smoke_dataset.py --out scratch/synthetic`, prepare them with `--manifest scratch/synthetic/manifest.csv --out scratch/processed`, train with `--data scratch/processed --epochs 1`, export with `--data scratch/processed --firmware scratch/generated`, then evaluate with `--data scratch/processed --split test`. Never deploy those synthetic-trained weights as a voice model.

Archive verification and file hashes are provided in `PACKAGE_MANIFEST.json`. The manifest excludes itself and includes SHA256 hashes for every other distributed file.
