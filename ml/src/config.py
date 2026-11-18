"""Load audio/DSP configuration from ml/config/audio_config.json.

Derived values (frames, freq_bins, feature_n) are computed from the base
parameters so the whole pipeline stays consistent when the input window
is resized. Edit the JSON to change the window length; every dependent
value updates automatically.

================================================================================
TECHNICAL GUIDE: Changing the Input Window Length
================================================================================

PURPOSE
-------
The input window length determines how many PCM16 audio samples are captured
and fed into the MFCC feature extractor and the CNN model for each inference
window. The default is one second (16000 samples at 16 kHz). If spoken
commands do not fit naturally within one second, increase this value so
syllables are not chopped off. This section documents exactly what to change,
the expected data type, and the performance implications.

--------------------------------------------------------------------------------
1. VARIABLE TO MODIFY
--------------------------------------------------------------------------------

File:  ml/config/audio_config.json
Key:   "samples"
Type:  integer (int)
Default: 16000

This is the total number of PCM16 samples captured per inference window.
It must be consistent with:
  - "sample_rate"   (16000 Hz by default) -> samples / sample_rate = duration in seconds
  - "window"        (400 samples, the FFT frame size)
  - "hop"           (160 samples, the frame stride)

The derived value "frames" is computed automatically as:

    frames = (samples - window) // hop + 1

For the default configuration:
    frames = (16000 - 400) // 160 + 1 = 98

This drives the CNN input shape [batch, frames, mfcc, 1] and the C firmware
buffer sizes AUDIO_SAMPLES and AUDIO_FEATURE_N (frames * mfcc).

--------------------------------------------------------------------------------
2. DATA TYPE REQUIREMENTS
--------------------------------------------------------------------------------

- JSON value must be a JSON integer (no quotes, no decimal point).
  Valid:  16000, 24000, 32000
  Invalid: "16000", 16000.0, 16k

- In Python, config.samples becomes an int.
- In C, AUDIO_SAMPLES becomes a preprocessor integer constant used in array
  declarations (e.g. `static int16_t pcm[AUDIO_SAMPLES]`). It must be a
  compile-time constant; VLA (variable-length arrays) are not used.

Constraint: (samples - window) must be evenly divisible by hop for a clean
frame count. If not, integer division truncates, potentially dropping a
partial final frame. Choose samples such that
    (samples - window) % hop == 0
or accept the truncation.

--------------------------------------------------------------------------------
3. PERFORMANCE AND MEMORY IMPACT
--------------------------------------------------------------------------------

Increasing "samples" linearly increases memory and compute across every layer:

Python side (training / export / evaluation):
  - MFCC output: frames * mfcc floats (4 bytes each).
    Default: 98 * 13 = 1274 floats ~ 5.1 KB per clip.
    At 24000 samples: 148 * 13 = 1924 floats ~ 7.7 KB per clip.
  - CNN input tensor: [batch, frames, mfcc, 1]. Larger frames increase
    activation memory in Conv2D and MaxPool2D layers proportionally.
  - Training time per epoch grows roughly linearly with frames.
  - Export calibration and golden-vector generation use more RAM.

C / firmware side (ESP32-S3 embedded inference):
  - PCM capture buffer: samples * 2 bytes (int16).
    Default: 16000 * 2 = 32,000 bytes (~31.25 KB).
    At 32000 samples: 64,000 bytes (~62.5 KB).
  - Feature output buffer: frames * mfcc * 4 bytes (float).
    Default: 98 * 13 * 4 = 5,096 bytes (~5 KB).
    At 32000 samples: 198 * 13 * 4 = 10,296 bytes (~10 KB).
  - MFCC static scratch in mfcc.c: re/im/power_bins arrays sized by FFT
    (unchanged by samples), plus win[AUDIO_WINDOW] (unchanged).
  - TFLM arena: must remain large enough for the larger input tensor and
    intermediate activations. Default arena is 256 KiB; monitor
    `arena_used_bytes` after resizing.
  - Inference latency: MFCC computation is O(frames * fft * log fft);
    CNN cost scales with frames. Expect roughly linear latency growth.

RAM budget guidance (ESP32-S3):
  - Internal SRAM is limited (~320 KB usable after RTOS, Wi-Fi, etc.).
  - The PCM buffer + feature buffer + TFLM arena must fit in available RAM.
  - If internal RAM is exhausted, relocate suitable buffers to PSRAM or
    reduce the arena size, but measure free heap first.

--------------------------------------------------------------------------------
4. EXAMPLE MODIFICATION
--------------------------------------------------------------------------------

Example: Change the input window from 1 second (16000 samples) to 2 seconds
(32000 samples) at 16 kHz.

Step 1 - Edit ml/config/audio_config.json:

    {
      "sample_rate": 16000,
      "samples": 32000,       <-- changed from 16000
      "window": 400,
      "hop": 160,
      "fft": 512,
      "mel_bins": 40,
      "mfcc": 13,
      ...
    }

Step 2 - Edit firmware/shared/config.h to match:

    #define AUDIO_SAMPLE_RATE 16000
    #define AUDIO_SAMPLES     32000   <-- changed from 16000
    #define AUDIO_WINDOW      400
    #define AUDIO_HOP         160
    #define AUDIO_FFT         512
    ...

    #define AUDIO_FRAMES      ((AUDIO_SAMPLES - AUDIO_WINDOW) / AUDIO_HOP + 1)
    #define AUDIO_FEATURE_N   (AUDIO_FRAMES * AUDIO_MFCC)

    Result: frames = (32000 - 400) / 160 + 1 = 198
            feature_n = 198 * 13 = 2574

Step 3 - Re-run the pipeline:

    python ml/src/pipeline.py prepare --manifest ml/data/manifest.csv
    python ml/src/pipeline.py train --epochs 60
    python ml/src/pipeline.py export
    python ml/src/pipeline.py evaluate --split val

Step 4 - Rebuild and flash firmware:

    cd firmware
    idf.py build
    idf.py -p <PORT> flash monitor

Step 5 - Verify tests:

    python -m unittest test.test_reference.Features

The model input shape becomes [batch, 198, 13, 1]. All dependent constants
(AUDIO_FRAMES, AUDIO_FEATURE_N, CNN input dims, test assertions) derive
automatically from samples, so no further hardcoded edits are needed.

--------------------------------------------------------------------------------
5. VALIDATION CHECKLIST AFTER CHANGING "samples"
--------------------------------------------------------------------------------

 [ ] ml/config/audio_config.json has integer "samples" with no quotes
 [ ] firmware/shared/config.h AUDIO_SAMPLES matches the JSON value
 [ ] (samples - window) % hop == 0 (or truncation is acceptable)
 [ ] pipeline.py prepare runs without shape errors
 [ ] CNN Input shape is (frames, mfcc, 1) where frames matches config
 [ ] Export shape check passes: [1, frames, mfcc, 1]
 [ ] C firmware compiles with new AUDIO_SAMPLES / AUDIO_FEATURE_N
 [ ] Arena usage printed at boot is below available RAM
 [ ] test_reference.py Features tests pass
 [ ] Golden vector regenerated and matches device output

--------------------------------------------------------------------------------
6. REVERSE OPERATION (SHORTENING THE WINDOW)
--------------------------------------------------------------------------------

Reducing "samples" follows the same steps in reverse. Beware: shortening
below the natural command duration clips syllables and degrades recognition.
Only reduce if you have confirmed commands fit entirely within the shorter
window and validation metrics remain acceptable.

================================================================================
END OF TECHNICAL GUIDE
================================================================================
"""
import json
from pathlib import Path
from types import SimpleNamespace

_CONFIG_PATH = Path(__file__).resolve().parent.parent / 'config' / 'audio_config.json'


def _load_config():
    with open(_CONFIG_PATH) as f:
        raw = json.load(f)
    raw['frames'] = (raw['samples'] - raw['window']) // raw['hop'] + 1
    raw['freq_bins'] = raw['fft'] // 2 + 1
    raw['feature_n'] = raw['frames'] * raw['mfcc']
    return SimpleNamespace(**raw)


config = _load_config()
