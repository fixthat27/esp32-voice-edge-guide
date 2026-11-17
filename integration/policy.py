"""Reference state machine. Feed scores from a rolling inference loop, monotonic seconds."""
import math
class VoicePolicy:
    def __init__(self,threshold=.85,margin=.15,window=4.,cooldown=2.):
        self.threshold=threshold; self.margin=margin; self.window=window; self.cooldown=cooldown
        self.state='IDLE'; self.until=0.; self.last=None; self.count=0; self.timestamp=-math.inf
    def tick(self,now,wake=False,label='unknown',score=0.,runner_up=0.):
        if not math.isfinite(now) or now<self.timestamp: raise ValueError('Use monotonic time')
        self.timestamp=now
        if self.state=='COOLDOWN':
            if now<self.until: return None
            self.state='IDLE'
        if self.state=='IDLE':
            if wake:
                self.state='COMMAND'; self.until=now+self.window; self.last=None; self.count=0
            return None # Do not classify the wake phrase as a command in the same window.
        if now>=self.until:
            self.state='IDLE'; self.last=None; self.count=0; return None
        allowed={'light_on','light_off','music_on','music_off'}
        if label not in allowed or not math.isfinite(score) or not math.isfinite(runner_up) or score<self.threshold or score-runner_up<self.margin:
            self.last=None; self.count=0; return None
        self.count=self.count+1 if self.last==label else 1; self.last=label
        if self.count<2: return None
        self.state='COOLDOWN'; self.until=now+self.cooldown; return label
