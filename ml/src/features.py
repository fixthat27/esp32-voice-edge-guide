"""Exact documented feature contract; independent NumPy reference for C parity."""
import numpy as np
from config import config


def mfcc(pcm):
    pcm = np.asarray(pcm)
    if pcm.shape != (config.samples,) or pcm.dtype != np.int16:
        raise ValueError(f'Expected exactly {config.samples} PCM16 samples')
    x = pcm.astype(np.float64) / 32768.0
    frames = np.stack([x[i:i+config.window] for i in range(0, config.samples - config.window + 1, config.hop)])
    window = .5 - .5*np.cos(2*np.pi*np.arange(config.window)/config.window)
    power = np.abs(np.fft.rfft(frames*window, n=config.fft))**2 / config.fft
    hz = 700*(10**(np.linspace(2595*np.log10(1+config.fmin/700),
                                2595*np.log10(1+config.fmax/700), config.mel_bins+2)/2595)-1)
    bins = np.arange(config.freq_bins)*config.sample_rate/config.fft
    weights = np.maximum(0, np.minimum(
        (bins[None,:]-hz[:-2,None])/(hz[1:-1]-hz[:-2])[:,None],
        (hz[2:,None]-bins[None,:])/(hz[2:]-hz[1:-1])[:,None]))
    logmel = np.log(np.maximum(power @ weights.T, config.log_floor))
    dct = np.cos(np.pi*np.arange(config.mfcc)[:,None]*(np.arange(config.mel_bins)+.5)/config.mel_bins)
    dct *= np.sqrt(2/config.mel_bins)
    dct[0] /= np.sqrt(2)
    return (logmel @ dct.T).astype(np.float32)


def quantize(x, scale, zero):
    if scale <= 0:
        raise ValueError('Invalid quantization scale')
    # Round ties away from zero, matching C roundf.
    z = np.asarray(x)/scale
    return np.clip(np.sign(z)*np.floor(np.abs(z)+.5)+zero,-128,127).astype(np.int8)
