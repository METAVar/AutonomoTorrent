#
# -*-encoding:gb2312-*-
import hashlib
import time, os

from twisted.internet import reactor, defer
from twisted.python import log

def sleep(timeout):
    df = defer.Deferred()

    start_time = time.time()
    
    def callback():
        dt = time.time() - start_time
        df.callback(dt)
        
    reactor.callLater(timeout, callback)
    
    return df

@defer.inlineCallbacks
def dns_resolve(addr):
    ip, port = addr
    if re.match(r'^(\d+\.){3}\d+$', ip):
        defer.returnValue(addr)
    else:
        ip = yield reactor.resolve(ip)
        addr = ip, port
        defer.returnValue(addr)

class SpeedMonitor (object):
    """A generic network speed monitor.
    
    @param period the time window for each individual measurement; if this is
    not set, the SpeedMonitor will not take measurements! 
    """
    def __init__(self, period=None):
        self.bytes = 0
        self.start_time = None

        self.period = period

        self.bytes_record = 0
        self.time_record = None
        self.speed = 0

        self.observer = None

    def registerObserver(self, observer):
        self.observer = observer

    @defer.inlineCallbacks
    def start(self):
        self.bytes = 0
        self.start_time = time.time()
        self.status = 'started'

        while self.status == 'started':
            if not self.period:
                break
            self.bytes_record = self.bytes
            self.time_record = time.time()
            yield sleep(self.period)
            self.speedCalc()

    def stop(self):
        if self.observer:
            self.observer = None

        self.status = 'stopped'

    def addBytes(self, bytes):
        self.bytes += bytes
        if self.observer:
            self.observer.addBytes(bytes)
    
    def speedCalc(self):
        curTime = time.time()
        dq = self.bytes - self.bytes_record
        dt = curTime - self.time_record
        self.speed = float(dq) / dt
        self.time_record = curTime
        self.bytes_record = self.bytes

    def get_speed(self):
        """Returns the speed in kibibit per second (Kibit/s) no matter what the
        period was. Returns None is period is None. 

        """
        if self.speed and self.period:
            return self.speed  / 1024
        else:
            return 0

def generate_peer_id():
    myid = 'M' + '7-2-0' + '--' # 8
    myid += hashlib.sha1(str(time.time())+ ' ' + str(os.getpid())).hexdigest()[-12:] # 12
    assert len(myid) == 20
    return myid

