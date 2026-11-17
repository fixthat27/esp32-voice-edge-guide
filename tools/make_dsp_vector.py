"""Create an explicitly synthetic DSP fixture, independent of trained models."""
import sys, wave
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'ml/src'))
from features import mfcc
dest=root/'test/inference_vectors'; dest.mkdir(parents=True,exist_ok=True)
t=np.arange(16000)/16000
rng=np.random.default_rng(30)
x=np.clip(7000*np.sin(2*np.pi*(180*t+1000*t*t))+rng.normal(0,80,16000),-32768,32767).astype('<i2')
with wave.open(str(dest/'synthetic_chirp.wav'),'wb') as w:
    w.setparams((1,2,16000,0,'NONE','not compressed')); w.writeframes(x.tobytes())
np.save(dest/'synthetic_chirp_mfcc.npy',mfcc(x))
(dest/'README.md').write_text('''# Synthetic DSP vector

This is a generated chirp with noise, not a human recording or a trained voice model.
Use its PCM samples to exercise embedded MFCC and compare the resulting 98 x 13
float tensor with synthetic_chirp_mfcc.npy, before involving the live microphone.
The expected tensor is unnormalized; model-specific mean/std are applied later.
Regenerate with python tools/make_dsp_vector.py from the bundle root.
''')
