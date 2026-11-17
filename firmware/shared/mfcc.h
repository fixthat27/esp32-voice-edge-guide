#pragma once
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define AUDIO_N 16000
#define FEATURE_N (98*13)
/* Single caller only. Static scratch avoids large task stacks. */
void mfcc_compute(const int16_t *pcm, float *out);
#ifdef __cplusplus
}
#endif
