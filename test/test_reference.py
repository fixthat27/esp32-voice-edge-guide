import ctypes, importlib.util, json, os, sys, tempfile, unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'ml/src')]
from features import mfcc, quantize
from integration.policy import VoicePolicy
from integration.service import CommandService, Conflict, Rejected

class Features(unittest.TestCase):
    def test_shape_and_silence(self):
        a=mfcc(np.zeros(16000,np.int16))
        self.assertEqual(a.shape,(98,13)); self.assertTrue(np.isfinite(a).all())
        np.testing.assert_allclose(a[:,1:],0,atol=1e-10)
    def test_quantization(self):
        np.testing.assert_array_equal(quantize(np.array([-999,-.5,.5,999]),1,0),[-128,-1,1,127])
    @unittest.skipUnless(os.getenv('MFCC_LIB'),'Set MFCC_LIB to compiled shared library')
    def test_c_parity(self):
        lib=ctypes.CDLL(os.environ['MFCC_LIB']); fn=lib.mfcc_compute
        fn.argtypes=[ctypes.POINTER(ctypes.c_int16),ctypes.POINTER(ctypes.c_float)]
        rng=np.random.default_rng(17)
        t=np.arange(16000)/16000
        signals=[np.zeros(16000,np.int16),rng.integers(-30000,30000,16000,dtype=np.int16),
                 (12000*np.sin(2*np.pi*440*t)).astype(np.int16),
                 (100*np.sin(2*np.pi*997*t)+rng.normal(0,4,16000)).astype(np.int16)]
        for i,x in enumerate(signals):
            out=np.empty((98,13),np.float32)
            fn(x.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)))
            error=float(np.max(np.abs(out-mfcc(x))))
            print(f'parity signal={i} max_abs_error={error:.8f}')
            np.testing.assert_allclose(out,mfcc(x),atol=.003,rtol=.0002)

class Policy(unittest.TestCase):
    def test_wake_command_cooldown(self):
        p=VoicePolicy(); self.assertIsNone(p.tick(0,label='light_on',score=.99))
        p.tick(1,wake=True)
        self.assertIsNone(p.tick(1.1,label='light_on',score=.95))
        self.assertEqual(p.tick(1.2,label='light_on',score=.95),'light_on')
        self.assertIsNone(p.tick(1.3,label='light_on',score=.95))
    def test_reject_resets_and_timeout(self):
        p=VoicePolicy(); p.tick(0,wake=True); p.tick(.1,label='light_on',score=.99)
        p.tick(.2,label='unknown',score=.99)
        self.assertIsNone(p.tick(.3,label='light_on',score=.99))
        self.assertIsNone(p.tick(5,label='light_on',score=.99)); self.assertEqual(p.state,'IDLE')
    def test_nan_and_ambiguity(self):
        p=VoicePolicy(); p.tick(0,wake=True)
        self.assertIsNone(p.tick(.1,label='light_on',score=float('nan')))
        self.assertIsNone(p.tick(.2,label='light_on',score=.9,runner_up=.85))

class Service(unittest.TestCase):
    def setUp(self): self.body=json.loads((ROOT/'integration/request.example.json').read_text())
    def test_duplicate_and_conflict(self):
        calls=[]; svc=CommandService(':memory:',calls.append)
        self.assertEqual(svc.execute(self.body)['status'],'published')
        svc.execute(self.body); self.assertEqual(len(calls),1)
        with self.assertRaises(Conflict): svc.execute({**self.body,'model_version':'other'})
    def test_no_replay_after_uncertain_delivery(self):
        calls=[]
        def adapter(b): calls.append(b); raise TimeoutError()
        svc=CommandService(':memory:',adapter)
        self.assertEqual(svc.execute(self.body)['status'],'indeterminate')
        svc.execute(self.body); self.assertEqual(len(calls),1)
    def test_rejections(self):
        calls=[]; svc=CommandService(':memory:',calls.append)
        for change in ({'device_id':'door'},{'confidence':.1},{'value':False}):
            with self.assertRaises(Rejected): svc.execute({**self.body,**change})
        self.assertEqual(calls,[])
    def test_persistent_dedup(self):
        with tempfile.TemporaryDirectory() as temp:
            db=str(Path(temp)/'requests.db'); svc=CommandService(db)
            svc.execute(self.body); svc.db.close()
            calls=[]; svc=CommandService(db,calls.append)
            self.assertEqual(svc.execute(self.body)['status'],'shadow')
            self.assertEqual(calls,[]); svc.db.close()
    def test_api_schema_auth(self):
        from fastapi.testclient import TestClient
        os.environ['VOICE_DB']=':memory:'; os.environ['VOICE_API_KEY']='test-token'
        from integration.api import app
        c=TestClient(app)
        self.assertEqual(c.post('/api/v1/commands',json=self.body).status_code,401)
        headers={'X-API-Key':'test-token'}
        self.assertEqual(c.post('/api/v1/commands',json={**self.body,'value':'true'},headers=headers).status_code,422)
        r=c.post('/api/v1/commands',json=self.body,headers=headers)
        self.assertEqual(r.status_code,200); self.assertEqual(r.json()['status'],'shadow')
if __name__=='__main__': unittest.main()
