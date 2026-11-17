"""Print split/label/group counts before preparation; paths relative to manifest."""
import argparse, collections, csv
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('manifest'); a=p.parse_args()
rows=list(csv.DictReader(Path(a.manifest).open(encoding='utf-8-sig')))
for (split,label),n in sorted(collections.Counter((r['split'],r['label']) for r in rows).items()):
    print(f'{split:5} {label:20} {n}')
for split in ('train','val','test'):
    print(split,'groups:',sorted({r['group'] for r in rows if r['split']==split}))
