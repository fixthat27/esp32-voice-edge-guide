#pragma once
#include <stdint.h>

/*
 * Audio/DSP configuration. Mirrors ml/config/audio_config.json.
 * When changing the input window size, update the JSON and this header
 * together so Python and C stay consistent.
 *
 * Derived values:
 *   FRAMES  = (SAMPLES - WINDOW) / HOP + 1
 *   FREQ_BINS = FFT / 2 + 1
 *   FEATURE_N = FRAMES * MFCC
 */
#define AUDIO_SAMPLE_RATE 16000
#define AUDIO_SAMPLES     32000
#define AUDIO_WINDOW      400
#define AUDIO_HOP         160
#define AUDIO_FFT         512
#define AUDIO_MEL_BINS    40
#define AUDIO_MFCC        13
#define AUDIO_FMIN        20
#define AUDIO_FMAX        7600

#define AUDIO_FRAMES      ((AUDIO_SAMPLES - AUDIO_WINDOW) / AUDIO_HOP + 1)
#define AUDIO_FREQ_BINS   (AUDIO_FFT / 2 + 1)
#define AUDIO_FEATURE_N   (AUDIO_FRAMES * AUDIO_MFCC)
