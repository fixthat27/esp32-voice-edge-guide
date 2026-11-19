#pragma once
#include <stdint.h>
#include "config.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Single caller only. Static scratch avoids large task stacks. */
void mfcc_compute(const int16_t *pcm, float *out);
#ifdef __cplusplus
}
#endif
