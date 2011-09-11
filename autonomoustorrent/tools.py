#
# -*-encoding:gb2312-*-
import hashlib
import time, os

from twisted.internet import reactor, defer

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

        # print '当前速率 %d B/s' % int(self.speed)

def generate_peer_id():
    myid = 'M' + '7-2-0' + '--' # 8
    myid += hashlib.sha1(str(time.time())+ ' ' + str(os.getpid())).hexdigest()[-12:] # 12
    assert len(myid) == 20
    return myid

