#
# -*-encoding:gb2312-*-

from twisted.internet import reactor

from tools import SpeedMonitor

class BTUpload (object) :
    # producer interface implementation

    def __init__(self, protocol):
        self.protocol = protocol

        self.peer_interested = None
        self.am_choke = None

        self.uploadSpeedMonitor = SpeedMonitor()

        self.upload_todo = []
        self.upload_doing = []
        self.upload_done = []

        self.status = None

    def start(self):
        if self.status == 'started' :
            return

        if not self.protocol:
            return

        self.btm = self.protocol.factory.btm
        self.pieceManager = self.btm.pieceManager

        self.uploadSpeedMonitor.start()
        self.uploadSpeedMonitor.registerObserver(self.protocol.factory.uploadSpeedMonitor)

        self.choke(False)

        self.protocol.transport.registerProducer(self, False)

        self.status = 'started'

    def stop(self):
        if self.status == 'stopped':
            return

        self.uploadSpeedMonitor.stop()

        self.protocol.transport.unregisterProducer()
        
        del self.protocol
        del self.btm
        del self.pieceManager

        self.status = 'stopped'

    def pause(self):
        pass

    def resume(self):
        pass


    def _interested(self, val):
        self.peer_interested = bool(val)

    def _request(self, idx, begin, length):
        if not self.pieceManager.doIHave(idx): # I don't have
            return

        self.upload_todo.append((idx, (begin, length)))

        # data = self.pieceManager.getPieceData(idx, begin, length)
        # if data :
        #     self.protocol.send_piece(idx, begin, data)

        if self.status == 'idle' :
            self.resumeProducing()

    def _cancel(self, idx, begin, length):
        task = idx, (begin, length)
        if task in self.upload_todo :
            self.upload_todo.remove(task)

    def choke(self, val):
        am_choke = bool(val)
        if self.am_choke is am_choke :
            return

        if am_choke :
            self.protocol.send_choke()
        else :
            self.protocol.send_unchoke()

        self.am_choke = am_choke

    def _uploadMonitor(self, _type, data):
        self.uploadSpeedMonitor.addBytes(len(data))

    # called by transport and do write
    def resumeProducing(self):
        for i in range(len(self.upload_todo)) :
            idx, (begin, length) = self.upload_todo[i]
            data = self.pieceManager.getPieceData(idx, begin, length)
            if data :
                self.protocol.send_piece(idx, begin, data)
                self.status = 'uploading'
                del self.upload_todo[i]
                break
        else:
            self.status = 'idle'

    def stopProducing(self):
        pass

