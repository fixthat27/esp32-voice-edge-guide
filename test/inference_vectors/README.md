# Synthetic DSP vector

This is a generated chirp with noise, not a human recording or a trained voice model.
Use its PCM samples to exercise embedded MFCC and compare the resulting 98 x 13
float tensor with synthetic_chirp_mfcc.npy, before involving the live microphone.
The expected tensor is unnormalized; model-specific mean/std are applied later.
Regenerate with python tools/make_dsp_vector.py from the bundle root.
