"""Receive one indexed ASCII PCM clip, validating every sample offset."""
import argparse, array, sys, time, wave
from pathlib import Path
import serial
p=argparse.ArgumentParser()
p.add_argument('--port',required=True); p.add_argument('--out',required=True)
p.add_argument('--baud',type=int,default=115200)
a=p.parse_args()
dest=Path(a.out)
if dest.exists(): raise SystemExit('Refusing to overwrite a recording')
samples=[]; clip=None; deadline=time.monotonic()+90
with serial.Serial(a.port,a.baud,timeout=2) as port:
    while time.monotonic()<deadline:
        line=port.readline().decode('ascii',errors='replace').strip()
        if line.startswith('READY'): print(line,flush=True)
        if line.startswith('PCM_BEGIN '):
            _,clip,count=line.split()
            if count!='32000': raise ValueError('Wrong sample count')
            samples=[]
        elif line.startswith('PCM ') and clip is not None:
            _,offset,data=line.split()
            if int(offset)!=len(samples) or len(data)!=128:
                raise ValueError('Lost or corrupt serial line; discard recording')
            words=[int(data[i:i+4],16) for i in range(0,len(data),4)]
            samples.extend(x if x<32768 else x-65536 for x in words)
        elif line==f'PCM_END {clip}' and clip is not None:
            if len(samples)!=32000: raise ValueError('Incomplete capture')
            dest.parent.mkdir(parents=True,exist_ok=True)
            raw=array.array('h',samples)
            if sys.byteorder!='little': raw.byteswap()
            with wave.open(str(dest),'wb') as w:
                w.setparams((1,2,16000,0,'NONE','not compressed')); w.writeframes(raw.tobytes())
            print('Saved',dest); break
    else: raise TimeoutError('No complete clip in 90 seconds')
