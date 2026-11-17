"""Standalone dry-run reference. Port validation into existing command_service, not beside it."""
import hashlib, json, math, sqlite3, threading
class Rejected(ValueError): pass
class Conflict(ValueError): pass
class CommandService:
    def __init__(self,db='commands.sqlite3',adapter=None):
        self.lock=threading.Lock(); self.db=sqlite3.connect(db,check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, digest TEXT, result TEXT)')
        self.db.commit(); self.adapter=adapter
    def execute(self,body):
        if body['device_id']!='technical-office-light' or body['action'] not in ('turn_on','turn_off'):
            raise Rejected('Unsupported device/action')
        if body['value'] is not (body['action']=='turn_on') or not math.isfinite(body['confidence']) or not .85<=body['confidence']<=1:
            raise Rejected('Value mismatch or low confidence')
        digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        with self.lock:
            row=self.db.execute('SELECT digest,result FROM requests WHERE id=?',(body['request_id'],)).fetchone()
            if row:
                if row[0]!=digest: raise Conflict('Request ID reused with different content')
                return json.loads(row[1])
            pending={'request_id':body['request_id'],'status':'indeterminate','confirmed':False}
            # Commit before side effect. On crash, do not blindly replay an uncertain command.
            self.db.execute('INSERT INTO requests VALUES (?,?,?)',(body['request_id'],digest,json.dumps(pending))); self.db.commit()
            if self.adapter is None:
                result={**pending,'status':'shadow','message':'Validated only; no MQTT publication'}
            else:
                try:
                    self.adapter(body) # Must wait for broker acknowledgment or raise.
                    result={**pending,'status':'published'}
                except Exception:
                    result={**pending,'status':'indeterminate','message':'Delivery uncertain; reconcile state'}
            self.db.execute('UPDATE requests SET result=? WHERE id=?',(json.dumps(result),body['request_id'])); self.db.commit()
            return result
