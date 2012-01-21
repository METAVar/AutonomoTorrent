"""
"""
from twisted.internet import reactor, defer

from tools import SpeedMonitor, sleep
from bitfield import Bitfield

class BTDownload(object) :

    task_max_size = 5
    
    def __init__(self, protocol):
        self.protocol = protocol

        self.piece_doing = []
        self.piece_done = []

        self.peer_choke = None
        self.am_interested = None

        self.downloadSpeedMonitor = SpeedMonitor()

        self.task_max_size = 5

    def start(self):
        if not self.protocol:
            return

        self.status = 'running'
        self.btm = self.protocol.factory.btm
        self.pieceManager = self.btm.pieceManager
        pm = self.pieceManager
        self.peer_bitfield = Bitfield(pm.pieces_size)
        self.downloadSpeedMonitor.start()
        self.downloadSpeedMonitor.registerObserver(self.protocol.factory.downloadSpeedMonitor)

    def stop(self):
        for task in self.piece_doing:
            self.pieceManager.failedPieceTask(*task)

        del self.piece_doing[:]
            
        self.downloadSpeedMonitor.stop()

        del self.protocol
        del self.btm
        del self.pieceManager

        self.status = 'stopped'

    def _choke(self, val):
        self.peer_choke = bool(val)
        
        if val:
            pass
        else:
            self.__pieceRequest()

    def interested(self, val):
        am_interested = bool(val)
        if self.am_interested is am_interested :
            return

        if am_interested :
            self.protocol.send_interested()
        else :
            self.protocol.send_not_interested()

        self.am_interested = am_interested

    def cancel(self, task):
        idx, (beg, length) = task
        self.protocol.send_cancel(idx, beg, length)

    def _downloadMonitor(self, data):
        self.downloadSpeedMonitor.addBytes(len(data))        

    def __pieceRequest(self):
        if self.am_interested==True and self.peer_choke==False:
            if self.piece_doing :
                return
            new_task = self.__getTask()
            if new_task :
                self.__sendTaskRequest(new_task)
            
    def __getTask(self, size=None):
        if size is None :
            size = self.task_max_size
        pm = self.pieceManager
        new_task = pm.getMorePieceTask(self.peer_bitfield, size)
        return new_task

    @defer.inlineCallbacks
    def __sendTaskRequest(self, new_task, timeout=None):
        if not new_task:
            return

        if timeout is None:
            timeout = len(new_task) * 60

        for task in new_task :
            i, (beg, size) = task
            self.protocol.send_request(i, beg, size)
            self.piece_doing.append(task)

        yield sleep(timeout)
        self.__checkTimeout(new_task)

    def __checkTimeout(self, task_plan):
        if self.status == 'stopped' :
            return
        
        set_plan = set(task_plan)
        set_ing = set(self.piece_doing)
        set_undo = set_plan & set_ing
        set_new = set_ing - set_plan

        task_size = self.task_max_size - len(set_undo)
        if set_new:
            task_size += 1

        if task_size < 1:
            task_size = 1
        elif task_size > BTDownload.task_max_size :
            task_size = BTDownload.task_max_size

        self.task_max_size = task_size

        if not set_undo:
            return

        new_task = self.__getTask(self.task_max_size)

        for task in set_undo:
            self.cancel(task)
            self.piece_doing.remove(task)
            self.pieceManager.failedPieceTask(*task)

        if new_task:
            self.__sendTaskRequest(new_task)

    def _piece(self, index, beg, piece):
        task = index, (beg, len(piece))
        if task not in self.piece_doing: 
            return

        self.pieceManager.finishPieceTask(index, (beg, len(piece)), piece)
        self.piece_doing.remove(task)
        if len(self.piece_doing) == 0:
            self.__pieceRequest()

    def _bitfield(self, data):
        pm = self.pieceManager
        bf = Bitfield(pm.pieces_size, data)
        self.peer_bitfield = bf
        
        if self.pieceManager.amInterested(bf):
            self.interested(True)
            self.__pieceRequest()
        else:
            self.interested(False)

    def _have(self, index):
        self.peer_bitfield[index] = 1
        if self.pieceManager.amInterested(index) :
            self.interested(True)
            self.__pieceRequest()
