"""Create synthetic fixtures for pipeline testing ONLY, never for voice accuracy claims."""
import argparse, csv, json, wave
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser(); p.add_argument('--out',required=True); a=p.parse_args()
root=Path(a.out); root.mkdir(parents=True,exist_ok=True)
labels=json.loads(Path('ml/labels.json').read_text()); rng=np.random.default_rng(92); rows=[]
for split in ('train','val','test'):
    for i,label in enumerate(labels):
        for n in range(3):
            t=np.arange(16000)/16000
            pcm=np.clip(3000*np.sin(2*np.pi*(200+i*170)*t)+rng.normal(0,100,16000),-32768,32767).astype('<i2')
            name=f'{split}_{label}_{n}.wav'
            with wave.open(str(root/name),'wb') as w:
                w.setparams((1,2,16000,0,'NONE','not compressed')); w.writeframes(pcm.tobytes())
            rows.append([name,label,'synthetic',split,split,split])
with (root/'manifest.csv').open('w',newline='') as f:
    writer=csv.writer(f); writer.writerow(['path','label','speaker','session','group','split']); writer.writerows(rows)
print('Synthetic test fixtures only:',root)
