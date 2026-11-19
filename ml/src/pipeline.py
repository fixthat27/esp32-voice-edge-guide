"""Run from bundle root. See --help and docs/WORKFLOW.md."""
import argparse, csv, hashlib, json, wave
from pathlib import Path
import numpy as np
from config import config
from features import mfcc, quantize


def read_wav(path):
    with wave.open(str(path),'rb') as w:
        if (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())!=(1,2,config.sample_rate,config.samples):
            raise ValueError(f'{path}: need {config.samples}-sample, mono PCM16, {config.sample_rate} Hz')
        return np.frombuffer(w.readframes(config.samples),dtype='<i2').astype(np.int16)


def prepare(args):
    manifest=Path(args.manifest)
    rows=list(csv.DictReader(manifest.open(encoding='utf-8-sig')))
    labels=json.loads(Path(args.labels).read_text())
    if len(set(labels))!=len(labels) or not {'unknown','silence'}<=set(labels):
        raise ValueError('Unique labels including unknown and silence required')
    groups={}; hashes=set(); data={s:[] for s in ('train','val','test')}
    for row in rows:
        split=row['split']; group=row['group']
        if not group or split not in data: raise ValueError('Bad split/group')
        if group in groups and groups[group]!=split: raise ValueError('Group leakage: '+group)
        groups[group]=split
        path=manifest.parent/row['path']; pcm=read_wav(path)
        digest=hashlib.sha256(pcm.tobytes()).hexdigest()
        if digest in hashes: raise ValueError('Duplicate PCM: '+str(path))
        hashes.add(digest)
        feat=mfcc(pcm)
        data[split].append((feat,labels.index(row['label'])))
    for split,items in data.items():
        if not items or set(y for _,y in items)!=set(range(len(labels))):
            raise ValueError(f'Every label needs examples in {split}')
    train=np.stack([x for x,_ in data['train']])
    mean=train.mean(axis=(0,1)); std=np.maximum(train.std(axis=(0,1)),1e-5)
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    for split,items in data.items():
        x=np.stack([x for x,_ in items]); y=np.array([y for _,y in items])
        np.savez_compressed(out/f'{split}.npz',x=((x-mean)/std)[...,None],y=y)
    config_meta={'sample_rate':config.sample_rate,'samples':config.samples,'window':config.window,'hop':config.hop,'fft':config.fft,
            'frames':config.frames,'mel_bins':config.mel_bins,'mfcc':config.mfcc,'fmin':config.fmin,'fmax':config.fmax,
            'window_type':config.window_type,'mel':config.mel,'power':config.power,'log':config.log,
            'dct':config.dct,'padding':config.padding,'preemphasis':config.preemphasis,
            'labels':labels,'mean':mean.tolist(),'std':std.tolist(),
            'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
            'audio_sha256':sorted(hashes)}
    (out/'metadata.json').write_text(json.dumps(config_meta,indent=2))
    print({s:len(v) for s,v in data.items()})


def augment(x, rng):
    """Add noise, random gain, and time shift."""
    x = x + rng.normal(0, 0.01, x.shape)
    x = x * rng.uniform(0.8, 1.2)
    shift = rng.integers(-5, 6)
    if shift != 0:
        x = np.roll(x, shift, axis=0)
    return x


def train(args):
    import tensorflow as tf
    tf.keras.utils.set_random_seed(2026)
    root=Path(args.data); a=np.load(root/'train.npz'); v=np.load(root/'val.npz')
    meta=json.loads((root/'metadata.json').read_text())
    rng=np.random.default_rng(2026)
    # Augment training data
    x_train = np.stack([augment(x, rng) for x in a['x']])
    model=tf.keras.Sequential([
        tf.keras.layers.Input((config.frames,config.mfcc,1)),
        tf.keras.layers.Conv2D(16,3,padding='same',activation='relu'),
        tf.keras.layers.MaxPooling2D(2),
        tf.keras.layers.Conv2D(32,3,padding='same',activation='relu'),
        tf.keras.layers.Conv2D(64,3,padding='same',activation='relu'),
        tf.keras.layers.GlobalAveragePooling2D(),
        tf.keras.layers.Dense(len(meta['labels']),activation='softmax')])
    model.compile(optimizer='adam',loss='sparse_categorical_crossentropy',metrics=['accuracy'])
    # Compute class weights
    class_weight = {i: 1.0 / np.sum(a['y'] == i) for i in range(len(meta['labels']))}
    model.summary()
    model.fit(x_train,a['y'],validation_data=(v['x'],v['y']),epochs=args.epochs,batch_size=32,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=20,restore_best_weights=True),
                         tf.keras.callbacks.ReduceLROnPlateau(factor=0.5,patience=5)],
              class_weight=class_weight)
    model.save(root/'command.keras')


def export(args):
    import tensorflow as tf
    root=Path(args.data); meta=json.loads((root/'metadata.json').read_text())
    model=tf.keras.models.load_model(root/'command.keras'); train=np.load(root/'train.npz')
    # Balanced training-only calibration, up to 100 examples per label.
    rng=np.random.default_rng(2026); indices=[]
    for label in range(len(meta['labels'])):
        ids=np.where(train['y']==label)[0]; rng.shuffle(ids); indices.extend(ids[:100])
    def representative():
        for i in indices: yield [train['x'][i:i+1].astype(np.float32)]
    # Export an inference SavedModel explicitly before conversion.
    saved=root/'saved_model'
    model.export(str(saved))
    converter=tf.lite.TFLiteConverter.from_saved_model(str(saved))
    converter.optimizations=[tf.lite.Optimize.DEFAULT]
    converter.representative_dataset=representative
    converter.target_spec.supported_ops=[tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type=tf.int8; converter.inference_output_type=tf.int8
    blob=converter.convert(); (root/'command.tflite').write_bytes(blob)
    engine=tf.lite.Interpreter(model_content=blob); engine.allocate_tensors()
    inp=engine.get_input_details()[0]; out=engine.get_output_details()[0]
    if inp['dtype']!=np.int8 or out['dtype']!=np.int8 or list(inp['shape'])!=[1,config.frames,config.mfcc,1]:
        raise ValueError('Unexpected model I/O')
    meta['input_quantization']=list(inp['quantization'])
    meta['output_quantization']=list(out['quantization'])
    meta['model_sha256']=hashlib.sha256(blob).hexdigest()
    # Analyzer is the supported human inspection path; save its console output too.
    tf.lite.experimental.Analyzer.analyze(model_content=blob)
    dest=Path(args.firmware); dest.mkdir(parents=True,exist_ok=True)
    (dest/'model_data.cc').write_text('alignas(16) extern const unsigned char command_model[] = {\n'+
        ','.join(str(b) for b in blob)+'\n};\n')
    def array(name,values):
        return 'static const float '+name+'[] = {'+','.join(f'{float(v):.9e}f' for v in values)+'};\n'
    header='#pragma once\n#define LABEL_COUNT '+str(len(meta['labels']))+'\n'
    header+='static const char * const LABELS[] = {'+','.join(json.dumps(x) for x in meta['labels'])+'};\n'
    header+=array('FEATURE_MEAN',meta['mean'])+array('FEATURE_STD',meta['std'])
    (dest/'model_metadata.h').write_text(header)
    (root/'export_metadata.json').write_text(json.dumps(meta,indent=2))
    v=np.load(root/'test.npz')['x'][0:1].astype(np.float32)
    q=quantize(v,*inp['quantization']); engine.set_tensor(inp['index'],q); engine.invoke()
    np.savez(root/'golden_vector.npz',features=v,input_int8=q,
             output_int8=engine.get_tensor(out['index']))
    (dest/'golden_input.h').write_text('#pragma once\nstatic const signed char GOLDEN_INPUT[] = {'+
        ','.join(str(int(x)) for x in q.ravel())+'};\n'+
        'static const signed char GOLDEN_OUTPUT[] = {'+
        ','.join(str(int(x)) for x in engine.get_tensor(out['index']).ravel())+'};\n')


def evaluate(args):
    import tensorflow as tf
    root=Path(args.data); data=np.load(root/(args.split+'.npz'))
    labels=json.loads((root/'metadata.json').read_text())['labels']
    model=tf.keras.models.load_model(root/'command.keras')
    fp=model.predict(data['x'],verbose=0)
    engine=tf.lite.Interpreter(model_path=str(root/'command.tflite')); engine.allocate_tensors()
    inp=engine.get_input_details()[0]; out=engine.get_output_details()[0]; scores=[]
    for x in data['x']:
        engine.set_tensor(inp['index'],quantize(x[None],*inp['quantization'])); engine.invoke()
        s,z=out['quantization']; scores.append((engine.get_tensor(out['index'])[0].astype(float)-z)*s)
    scores=np.array(scores); pred=scores.argmax(1); truth=data['y']; matrix=np.zeros((len(labels),len(labels)),int)
    for a,b in zip(truth,pred): matrix[a,b]+=1
    per={}
    for i,label in enumerate(labels):
        tp=int(matrix[i,i]); precision=tp/max(1,int(matrix[:,i].sum())); recall=tp/max(1,int(matrix[i].sum()))
        per[label]={'precision':precision,'recall':recall,'f1':2*precision*recall/max(1e-12,precision+recall)}
    negatives=np.isin(truth,[labels.index('unknown'),labels.index('silence')])
    valid=~np.isin(pred,[labels.index('unknown'),labels.index('silence')])
    ordered=np.sort(scores,axis=1); accepted=valid & (ordered[:,-1]>=args.threshold) & ((ordered[:,-1]-ordered[:,-2])>=args.margin)
    report={'split':args.split,'labels':labels,'confusion_rows_true_cols_pred':matrix.tolist(),
            'float_accuracy':float((fp.argmax(1)==truth).mean()),'int8_accuracy':float((pred==truth).mean()),
            'float_int8_disagreement':float((fp.argmax(1)!=pred).mean()),'per_class':per,
            'threshold':args.threshold,'margin':args.margin,
            'negative_clips':int(negatives.sum()),'false_accepted_negative_clips':int((accepted&negatives).sum()),
            'positive_clips':int((~negatives).sum()),
            'missed_or_wrong_positive_clips':int(((~accepted|(pred!=truth))&~negatives).sum())}
    (root/f'report_{args.split}.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))


p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
a=sub.add_parser('prepare'); a.add_argument('--manifest',required=True); a.add_argument('--labels',default='ml/labels.json'); a.add_argument('--out',default='ml/data/processed'); a.set_defaults(run=prepare)
for cmd,fn in [('train',train),('export',export),('evaluate',evaluate)]:
    a=sub.add_parser(cmd); a.add_argument('--data',default='ml/data/processed'); a.set_defaults(run=fn)
    if cmd=='train': a.add_argument('--epochs',type=int,default=60)
    if cmd=='export': a.add_argument('--firmware',default='firmware/main')
    if cmd=='evaluate':
        a.add_argument('--split',choices=['val','test'],default='val'); a.add_argument('--threshold',type=float,default=.85); a.add_argument('--margin',type=float,default=.15)
if __name__=='__main__':
    args=p.parse_args(); args.run(args)
