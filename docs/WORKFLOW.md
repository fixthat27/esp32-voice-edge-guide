# Guided workflow from the current milestone

## 0. Establish what is known

Read `originals/hardware_progress.md` sections 2 through 5. It reports successful OLED, microphone RMS, speaker and build/flash bring-up. It does not provide recordings, trained weights, test metrics or the repositories. Treat those hardware results as reported history, not results from this bundle.

The order is capture, dataset, float model, INT8 model, embedded inference, wake word, then smart-home integration. Do not advance just because a script exits successfully. Save the evidence listed at each gate in `docs/EXPERIMENT_LOG.md`.

Use version control in your own project before copying files. Compare `board_config.h` with the pins below. This bundle places it in `firmware/main/` for the reference build; your existing project may use a different location.

| Peripheral | Signal | GPIO |
|---|---|---:|
| INMP441 | BCLK/SCK | 5 |
| INMP441 | WS/LRCLK | 4 |
| INMP441 | SD/DOUT to MCU DIN | 6 |
| MAX98357A | BCLK | 15 |
| MAX98357A | WS/LRC | 16 |
| MAX98357A | DIN | 7 |
| SSD1306 | SDA | 41 |
| SSD1306 | SCL | 42 |

Ground the microphone L/R pin for the left slot. Use 3.3 V for the INMP441 and common ground. Verify breakout supply requirements separately for the amplifier and OLED. The microphone datasheet recommends a 100 kOhm pull-down on SD. The reference capture firmware leaves the amplifier and display unused, so an earlier repeated-tone bug cannot contaminate these recordings.

Record `idf.py --version`, the IDF Git revision, board markings and COM port. In an IDF terminal, `git -C $env:IDF_PATH rev-parse HEAD` records the checkout. Use Device Manager or `python -m serial.tools.list_ports` to identify the current serial interface. COM13 is the recorded example, not a permanent address.

## 1. Freeze the microphone baseline

Theory to read: audio sampling and I2S in `THEORY.md`, then the I2S and INMP441 sources in `REFERENCES.md`.

Build the capture project in an ESP-IDF terminal:

```powershell
cd firmware
idf.py set-target esp32s3
idf.py build
idf.py -p COM13 flash
cd ..
```

The reference project uses 32-bit stereo I2S slots at 16 kHz and extracts the left word from each pair. The meaningful microphone bits occupy the upper 24 bits of a 32-bit slot. An arithmetic right shift by 16 creates PCM16 without digital gain. Confirm this assumption with your recordings before changing shifts or adding gain.

Close `idf.py monitor` before opening the capture script. Only one program should own the port. Activate the Python environment and run:

```powershell
python tools/capture_serial.py --port COM13 --out test/audio_samples/quiet_001.wav
python tools/inspect_wav.py test/audio_samples/quiet_001.wav
```

The board prints `READY`, waits two seconds, warms the microphone capture for about 64 ms, then records one second. For a speech recording, start your short phrase just after that delay and keep it within the second. Initial timing takes practice; listen to every early clip. The firmware then stops I2S and dumps indexed hexadecimal PCM lines. At 115200 baud the dump takes several seconds. This is expected. The host validates offsets and sample counts and refuses to overwrite a file. A corrupt or missing line means discard the clip and repeat.

Repeat with a command, room background and a loud nearby utterance. Open the WAV in your usual audio player or waveform editor. A file containing 16000 samples proves the declared duration, not the physical clock rate; inspect WS at 16 kHz with a logic analyzer if timing is suspect. BCLK should be 64 times WS, or 1.024 MHz.

Interpret the WAV report:

- Quiet RMS should be lower than speech RMS in the same setup. No universal RMS threshold distinguishes valid wiring from all rooms.
- A flat zero waveform suggests wrong channel, supply or wiring. Random large jumps suggest format/alignment or signal-integrity problems.
- DC offset should be small relative to speech amplitude. Inspect the raw samples before adding a high-pass filter.
- Clipping should be absent in ordinary speech. If values reach the limits repeatedly, fix gain or placement. A digitally boosted clipped recording cannot be repaired by lowering it afterward.
- Listen for intelligibility and the entire phrase. A correct RMS value cannot detect a cut-off command.

Gate: keep at least three reviewed WAVs for quiet, speech and background; record wiring, sample format, metrics and listening result. The bundle's raw reader requires exactly one second at mono PCM16/16 kHz. Normalize other source formats before adding them. Do not silently resample in one pipeline but not another.

If speaker feedback is later needed, test it separately. Use a counted finite buffer, wait for TX completion and disable the TX channel. Check that no loop re-enqueues the tone. Disable capture while playing for the first prototype; otherwise the speaker can retrigger its own microphone.

## 2. Make the dataset reproducible

Start with the labels in `ml/labels.json`: four commands, unknown and silence. Change them now if your spoken commands differ; keep machine labels stable and record the exact spoken phrases and language in a dataset note. Vietnamese phrases are acceptable. The model learns acoustic examples, not the English spelling of `light_on`.

As a planning target, collect 100 to 200 reviewed examples per command across at least five sessions. This is an initial collection budget, not a guarantee of accuracy. Include slow/fast speech, normal/soft voices, microphone angles, and measured distances such as 0.3, 1 and 2 meters. If commands cannot fit naturally in one second, increase the input length consistently in DSP, model, buffers and tests instead of chopping off syllables.

Record unknown speech that resembles the commands, unrelated conversation and TV speech. Silence means realistic room ambience and non-command environmental noise, not thousands of identical zero arrays. Keep distinct original background recordings in different splits. Obtain permission for other people's recordings and keep source/license information for any public dataset.

Suggested layout:

```text
ml/data/
  manifest.csv
  raw/s01_day1/light_on_001.wav
  raw/s01_day1/unknown_001.wav
  raw/s01_day2/...
  raw/s02_day3/...
```

Copy `ml/manifest.example.csv` to `ml/data/manifest.csv` and replace its illustrative rows. Paths are relative to the manifest directory. Every clip has a label, speaker, session, group and split. For a personal device, hold out complete sessions. For a multi-speaker claim, use the speaker ID as the group and hold out speakers entirely. The code enforces the supplied group, not a guessed grouping. Approximately 70/15/15 is a starting distribution; coverage per label and group separation matter more than exact percentages.

```powershell
python ml/src/pipeline.py prepare --manifest ml/data/manifest.csv
```

This rejects incorrect WAV format, duplicate PCM, group overlap and missing labels in any split. It computes features and derives coefficient means and standard deviations from training data only. It saves processed arrays and metadata containing audio and manifest hashes. Do not change label order after training. Save a copy of the manifest and hashes with each model.

Augmentation is optional and deliberately absent from the baseline. Add modest noise/gain/time shifts only after this pipeline works, only to training data, and keep each augmented clip with its parent group. Use original, untouched validation/test examples. Gate: inspect class counts, review representative recordings and confirm no session/speaker leakage according to your evaluation goal.

## 3. Train and evaluate the floating-point baseline

Read the CNN and evaluation sections of `THEORY.md`. Install the ML requirements under Python 3.11. The proposed TensorFlow 2.16.1 environment is an explicit starting pin, not a claim that every newer converter is compatible. If conversion fails, preserve the error and package versions before changing them.

```powershell
python ml/src/pipeline.py train --epochs 60
```

The small CNN takes `[batch,98,13,1]`. It uses 8 and 16 filters, one pooling layer, global average pooling and a softmax classifier. Early stopping uses validation loss and restores the best weights. The fixed random seed helps repeat experiments but does not guarantee identical results across hardware and libraries. The output is `ml/data/processed/command.keras`.

Training accuracy alone is not a gate. A model can memorize a speaker, room or recording session. If validation quality is poor, inspect the recordings and labels first. Add hard negatives or improve capture before increasing network size. Use the later evaluation command after export to compare float and INT8 predictions on the exact same examples.

## 4. Export INT8 and compare it on the PC

```powershell
python ml/src/pipeline.py export *> ml/export_log.txt
python ml/src/pipeline.py evaluate --split val --threshold 0.85 --margin 0.15
```

The exporter first creates an inference SavedModel from the trained Keras model, then uses the TensorFlow Lite SavedModel converter. It calibrates on a balanced subset of training features, requests built-in INT8 operators and INT8 I/O, writes the model byte array and normalization header, and saves a golden input/output vector. Review `ml/export_log.txt` for actual operator types and versions. The supplied firmware resolver anticipates CONV_2D, MAX_POOL_2D, MEAN, FULLY_CONNECTED, SOFTMAX and possible RESHAPE. If the converter emits another operator, investigate before adding it. Full integer models still use integer biases and shape tensors wider than eight bits.

`report_val.json` contains float accuracy, INT8 accuracy, prediction disagreement, a confusion matrix, per-class precision/recall/F1 and rejected/accepted clip counts. Matrix rows are true classes and columns are predicted classes. A missed or wrong positive includes both rejection and classification as the wrong command.

Tune threshold and top-two margin on validation data. Values 0.85 and 0.15 are illustrative starting points, not established confidence requirements. Favor rejection over a wrong action. Once the model and thresholds are fixed, run:

```powershell
python ml/src/pipeline.py evaluate --split test --threshold 0.85 --margin 0.15
```

Do not repeatedly tune on the test results. Propose acceptance targets before looking at them, such as at least 90% per-command recall under stated conditions, no more than two percentage points of INT8 accuracy loss, and a measured false-activation rate acceptable for your light-control experiment. These are suggested project goals, not achieved results. Clip metrics do not measure false triggers per hour in continuous listening.

Gate: archive `.keras`, `.tflite`, export log, both reports, labels, preprocessing metadata, package freeze and SHA256. If float works but INT8 does not, check calibration coverage, normalization, saturation and operator conversion before retraining.

## 5. Prove preprocessing and inference on ESP32-S3

First run the host C parity test:

```powershell
powershell -ExecutionPolicy Bypass -File tools/test_host.ps1
```

This assumes GCC is installed and on PATH. The test compares the same C code linked into firmware with an independent NumPy implementation. It exercises silence, tones and noisy inputs. See `VALIDATION.md` for the measured host result. Host parity is necessary but does not replace a device test with its compiler settings.

The C implementation keeps roughly 56 KiB of tables/scratch in static storage. It is single-caller code. Do not run two feature tasks concurrently on it. The one-second PCM buffer uses 32000 bytes, feature output 5096 bytes and the provisional arena 256 KiB. These allocations plus I2S, RTOS, kernels and network buffers may exceed convenient internal-memory budgets. N16R8 capacity does not mean all memory is interchangeable. Start without Wi-Fi, inspect the linker map and measure free internal RAM. Enable and verify the correct octal PSRAM configuration for your actual board before deliberately relocating suitable buffers. Do not assume PSRAM is configured by this example.

Add the component only after the model files exist:

```powershell
cd firmware
idf.py add-dependency "espressif/esp-tflite-micro==1.4.3"
idf.py menuconfig
# Voice reference -> Enable trained model inference instead of capture
idf.py build
idf.py -p COM13 flash monitor
```

Keep the generated manifest and `dependencies.lock`. The v6.1/TFLM combination needs a real build. If it fails, isolate a minimal TFLM example and inspect the exact compiler/component error. A tested v6.0 release can be a separate compatibility experiment, not an unexplained downgrade of your main project.

Before live inference, the application copies the exported `golden_input.h` bytes into the input tensor, invokes once and prints every expected and actual output byte. It stops if any byte differs. This bypasses microphone and MFCC and tests only model/runtime. The same vector is saved in `golden_vector.npz`. Exact equality is preferable; investigate differences before relaxing this gate for an optimized kernel. Do not silently ignore a mismatch.

Next, feed a stored PCM clip into `mfcc_compute`, print features in frame/coefficient order and compare to `features.mfcc`. Compare the normalized and quantized input too. A good float MFCC match can still cross quantization boundaries near half steps. Finally enable live mic inference. The firmware logs MFCC time, invoke time, best class, score and used arena. It remains in shadow mode. Keep Wi-Fi disabled to demonstrate independent offline inference.

Measure at least 20 trials per command under each chosen distance/noise condition. Record failures instead of keeping only successful demonstrations. The bench firmware has two-second pauses and a non-overlapping one-second window; its output is not a latency claim for continuous listening. Gate: known-vector parity, reviewed live predictions, memory headroom and recorded latency, with no resets or allocation failures.

## 6. Add a separately trained wake word

Choose a phrase distinguishable from ordinary speech, with a duration that fits your chosen window. Create a separate label file such as `["wake", "unknown", "silence"]`, separate recordings and separate processed/model directories. Reuse the same preparation/training/export pipeline with `--labels`, `--out` and `--data` overrides. Export to a separate directory, not over `firmware/main/`, until you integrate both models and rename symbols. The current firmware contains one model only; dual-model integration is a later change.

Collect hard negatives: similar phrases, command words alone, ordinary speech and TV playback. A wake word is not speaker authentication. Test a replay if you intend to gate anything beyond a benign light-control experiment.

For continuous operation, replace the bench loop with these tasks:

1. A high-priority capture task continuously reads 256 stereo frames, extracts left PCM16 and writes a timestamped ring buffer. Increment an overflow counter on missed data.
2. Every 1600 new samples, an inference task takes a consistent one-second snapshot. Use a lock or buffer ownership handoff so capture cannot change the snapshot during processing. After overflow, invalidate the window and warm up again rather than classifying discontinuous audio.
3. While idle, run only the wake model. After a valid wake detection, flush or advance past the wake audio and start a bounded command-listening state.
4. While listening, run the command model. Reject unknown/silence, low score or insufficient top-two margin. Require repeated compatible detections if validation supports that choice.
5. Queue an accepted action, enter cooldown, then return to idle. Expire the listening window when no command qualifies.

`integration/policy.py` implements the state transitions as a tested host reference. Its defaults require two accepted command windows, a four-second listening timeout and two-second cooldown. Wake detection itself must already have passed a separate score/margin policy before `wake=True` is supplied. Port the tested state transitions into your RTOS application. Adjacent rolling windows are highly correlated; two detections are not two independent votes.

Keep capture active during feature/model computation and avoid HTTP in that task. If MFCC plus inference takes longer than the chosen 100 ms stride, profile and optimize or increase the stride. Precompute tables, use optimized kernels or compare against ESP-DSP only after parity is preserved. Two models may require two arenas, or controlled reinitialization; measure the cost and memory instead of assuming both fit.

Run several hours of negative audio and count accepted wake events, not every high-scoring frame. False accepts per hour = false wake events / negative hours. Miss rate = missed intended wake events / intended attempts. With zero events in H hours, an approximate 95% Poisson upper bound is 3/H events per hour; zero events in a short demo is weak evidence. Gate: measured rates, command-window behavior and recovery from overflow, playback and timeout.

## 7. Integrate the existing smart home backend

Follow `INTEGRATION.md` and section 11 of the progress document. Validate one known light using fixed JSON before sending classifier output. Use recognized intents over HTTP, backend-owned MQTT mapping, then LogicMachine and the existing bus configuration. Keep the optional Orange Pi ASR path separate from this standalone TinyML experiment.

When the end-to-end path works, test disconnects, ambiguous timeouts, duplicate IDs, restart, stale commands, manual override and state feedback. Move the same contract to Orange Pi only after Windows development tests pass. Record every deployment address and dependency version. Keep the existing automation operating when the AI node or gateway is stopped.

