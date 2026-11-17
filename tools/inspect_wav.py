import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ml/src'))
import numpy as np
from pipeline import read_wav
p=argparse.ArgumentParser(); p.add_argument('wav'); a=p.parse_args()
x=read_wav(a.wav).astype(float)/32768
rms=float(np.sqrt(np.mean(x*x)))
print(json.dumps({'samples':len(x),'rms':rms,'dbfs':20*np.log10(max(rms,1e-12)),
                  'dc':float(x.mean()),'peak':float(np.max(np.abs(x))),
                  'clipping_fraction':float((np.abs(x)>=32767/32768).mean())},indent=2))
