"""Exact documented feature contract; independent NumPy reference for C parity."""
import numpy as np

def mfcc(pcm):
    pcm = np.asarray(pcm)
    if pcm.shape != (16000,) or pcm.dtype != np.int16:
        raise ValueError('Expected exactly 16000 PCM16 samples')
    x = pcm.astype(np.float64) / 32768.0
    frames = np.stack([x[i:i+400] for i in range(0, 15601, 160)])
    window = .5 - .5*np.cos(2*np.pi*np.arange(400)/400)
    power = np.abs(np.fft.rfft(frames*window, n=512))**2 / 512
    hz = 700*(10**(np.linspace(2595*np.log10(1+20/700),
                                2595*np.log10(1+7600/700),42)/2595)-1)
    bins = np.arange(257)*16000/512
    weights = np.maximum(0, np.minimum(
        (bins[None,:]-hz[:-2,None])/(hz[1:-1]-hz[:-2])[:,None],
        (hz[2:,None]-bins[None,:])/(hz[2:]-hz[1:-1])[:,None]))
    logmel = np.log(np.maximum(power @ weights.T, 1e-10))
    dct = np.cos(np.pi*np.arange(13)[:,None]*(np.arange(40)+.5)/40)
    dct *= np.sqrt(2/40)
    dct[0] /= np.sqrt(2)
    return (logmel @ dct.T).astype(np.float32)

def quantize(x, scale, zero):
    if scale <= 0:
        raise ValueError('Invalid quantization scale')
    # Round ties away from zero, matching C roundf.
    z = np.asarray(x)/scale
    return np.clip(np.sign(z)*np.floor(np.abs(z)+.5)+zero,-128,127).astype(np.int8)
