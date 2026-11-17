# Theory behind the workflow

These explanations describe this bundle's design. They are not measured hardware results. Official source links and version notes are in [REFERENCES.md](REFERENCES.md).

## 1. What the ESP32 model does

A small-vocabulary classifier assigns a fixed audio window to one of a few learned labels. It does not transcribe arbitrary speech, understand unrestricted language or authenticate a person. Training adjusts weights using examples on the PC. Inference applies those fixed weights on the ESP32. A deterministic policy decides whether an inference result may cause an action.

The proposal separates perception, policy and automation. Here the microphone/model supplies evidence, the confidence/state logic rejects weak evidence, and the backend maps a permitted command to the existing automation system. Keeping those responsibilities separate lets you change a model without teaching it MQTT topics or KNX group addresses.

## 2. Sampling, PCM and I2S

Sampling measures amplitude at discrete times. At 16000 samples per second, the Nyquist frequency is 8000 Hz. The chosen mel filters stop at 7600 Hz. PCM16 stores each signed amplitude in two bytes. A second of mono PCM16 therefore occupies 16000 × 2 = 32000 bytes. Normalize it by 32768 to obtain approximately [-1,1).

I2S is a synchronous sample transport, not a WAV file format. BCLK clocks bits; WS identifies the left/right slot; SD carries samples. The INMP441 sends 24-bit signed data in 32-bit slots and expects a stereo frame of 64 clocks. Grounding L/R selects the left slot. The driver reads two 32-bit words per frame, but only the left word belongs to this microphone. The right slot may be undriven; do not average it into the signal.

The DMA read size of 256 audio frames is an I/O block size, not the MFCC window size. It represents 16 ms at 16 kHz. MFCC analysis uses overlapping 400-sample windows. Keep I/O buffering and signal-analysis framing as separate concepts.

RMS is sqrt(mean(x²)). It measures signal energy, including DC. dBFS is 20 log10(RMS) when full scale is 1. A quiet room is not numerical zero. Clipping means the signal hits the representable extremes and loses information. Mean amplitude estimates DC offset. Listening and waveform inspection remain necessary because none of these numbers identifies the spoken word or proves the whole phrase was captured.

## 3. Exact feature contract

MFCCs compress short-time spectral shape. The name alone does not specify a compatible implementation. Different defaults in librosa, TensorFlow and embedded libraries can produce different tensors from identical audio. This bundle uses the following explicit contract:

| Setting | Value |
|---|---|
| Input | Exactly 16000 mono signed PCM16 samples |
| Amplitude conversion | Divide by 32768; no automatic gain |
| Pre-emphasis/DC removal | None |
| Frame size | 400 samples, 25 ms |
| Hop | 160 samples, 10 ms |
| Padding/centering | No frame padding; no centering |
| Window | Periodic Hann, w[n] = 0.5 - 0.5 cos(2 pi n / 400) |
| FFT | 512-point, zero pad each 400-sample frame at its end |
| Spectrum | Magnitude squared divided by 512; one-sided bins, no doubling |
| Mel bands | 40 triangular filters between 20 and 7600 Hz |
| Mel convention | HTK: m = 2595 log10(1 + f/700); no area normalization |
| Filter construction | Evaluate continuous triangular weights at FFT bin frequencies |
| Compression | Natural logarithm, floor energy at 1e-10 |
| Cepstrum | Orthonormal DCT-II, retain c0 through c12 |
| Lifter/deltas | None |
| Dataset normalization | Per coefficient, training-only mean/std; std floor 1e-5 |
| Tensor ordering | Frame, coefficient, channel: 98 × 13 × 1 |

The number of complete frames is 1 + floor((16000 - 400) / 160) = 98. The last frame starts at sample 15520 and ends at 15919; the remaining 80 samples do not form another complete frame. FFT zero padding does not create new acoustic information; it samples the window's spectrum more densely.

For frame t, compute windowed samples, then power P[t,k]. Each mel energy is a weighted sum of P over FFT bins. Take its log and apply the DCT:

```text
E[t,m] = sum_k weights[m,k] * P[t,k]
L[t,m] = ln(max(E[t,m], 1e-10))
C[t,c] = a[c] * sum_m L[t,m] * cos(pi*c*(m+0.5)/40)
a[0] = sqrt(1/40); a[c>0] = sqrt(2/40)
Z[t,c] = (C[t,c] - train_mean[c]) / train_std[c]
```

Training and firmware must agree through Z, not merely C. Preserve normalization with the model. This reference computes FFT scratch values in double precision to keep a transparent numerical baseline. ESP32-S3 double arithmetic can be expensive. Optimize to a validated float/DSP implementation only after comparing real microphone clips, and measure whether the chosen inference stride is sustainable.

The host parity test uses an independent NumPy FFT and the same C implementation that firmware compiles. This catches conventions and implementation errors. It does not prove that arbitrary future compiler flags, fast-math changes, replacement DSP kernels or modified preprocessing preserve behavior.

## 4. CNNs and dataset leakage

A convolution learns small patterns in neighboring time/cepstral positions. Pooling reduces spatial size; a global average reduces each learned feature map to one value; the final dense layer generates class logits. Softmax transforms logits into a normalized score vector. A score is not a calibrated probability of a correct physical action, especially on sounds unlike the training data.

The compact model is an engineering baseline. It sacrifices some temporal detail for low parameter count. If it confuses opposite commands, inspect whether recordings contain the distinguishing syllable and whether averaging removes useful ordering. A DS-CNN can reduce computation with depthwise and pointwise convolution, but it changes the operator set and must pass export and TFLM checks again.

Leakage occurs when evaluation examples share information with training examples that would not be available for a genuinely new case. Adjacent windows from one long recording, augmented copies and the same background source can leak. Splitting by recording group avoids the easiest failure; holding out speakers tests a stronger generalization claim. Normalization, augmentation decisions and INT8 calibration must not learn from the test split.

Unknown is not a universal description of every possible noise. It is a class sampled from the negatives you collected. Add difficult real failures as new training examples while reserving fresh evaluation recordings. The final confidence gate can reject an otherwise winning command class.

## 5. INT8 quantization and memory

Quantization represents a real value x with integer q using scale s and zero point z:

```text
q = clip(round(x/s) + z, -128, 127)
x_approx = (q - z) * s
```

This bundle uses ties-away-from-zero rounding in both Python and C. Read scales and zero points from the actual tensors; do not assume a zero point of zero or that output bytes can be divided by 127. Representative data determines activation ranges. Too narrow a range clips real features; too wide a range wastes precision. Calibration must see normalized training examples, not raw PCM or unnormalized MFCCs.

The model file is not the total RAM requirement. The tensor arena stores intermediate activations and runtime allocations; feature tables, ring buffers, task stacks, DMA and network allocations are separate. A small weight file can still require substantial activation memory. Log `arena_used_bytes`, minimum free heap and task stack watermarks. A configured 256 KiB arena is a starting capacity, not a measured requirement.

Correctness has three distinct tests: float versus INT8 on the PC, desktop INT8 versus TFLM for identical input bytes, and host versus embedded preprocessing for identical PCM. Separating these tests tells you whether a failure comes from conversion, runtime integration or audio preprocessing.

## 6. Streaming and decision logic

A fixed-window classifier has no built-in event boundaries. In a rolling system, one utterance appears in several overlapping windows. Acting on every high score can send repeated commands. A state machine adds a listening interval, repeated-detection rule and cooldown. It also defines what happens on timeout, low confidence, unknown audio and network failure.

A ring buffer stores recent audio while capture continues. An inference snapshot must represent a contiguous time interval; reading a buffer that capture is modifying can mix old and new samples. Snapshot copies or ownership handoff solve that problem. If processing falls behind, count the lost data and reject the broken window.

Report capture/window latency, feature latency, model latency, policy delay and network/device latency separately. A model invocation of a few milliseconds would not mean a one-second-window system reacts in a few milliseconds. Continuous false-trigger testing is also separate from a balanced clip test.

## 7. Distributed commands and acknowledgment

HTTP success, MQTT publish acknowledgment and physical state confirmation are different events. A successful API response may mean only that input was validated. QoS 1 acknowledges transport between MQTT peers and permits duplicate delivery. Neither QoS 1 nor QoS 2 certifies that a light changed state.

Use stable request IDs for deduplication and traceability. Reusing an ID with different content is a conflict. Retrying a timed-out request can duplicate a side effect if the original request succeeded but its reply was lost. Even a persistent deduplication table cannot atomically commit a database row and an independent physical device operation. This reference records an indeterminate state before calling an adapter and refuses to replay uncertain work automatically. A production backend needs reconciliation, appropriate durable/outbox processing, and actual state feedback.

Prefer `turn_on`/`turn_off` over `toggle`: repeated set-state requests express the same desired state, while repeated toggle requests can reverse the intended effect. Keep manual override and bus interlocks authoritative. A model confidence score is evidence for policy, not authorization.
