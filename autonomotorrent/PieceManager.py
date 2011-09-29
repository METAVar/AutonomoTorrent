# 
# -*-encoding:gb2312-*-

import hashlib

from twisted.python import log
from bitfield import Bitfield
from FileManager import BTFileManager, BTFileError, BTHashTestError

class BTPieceManager:

    slice_size = 2**14

    def __init__(self, btm):
        self.btm = btm
        self.metainfo = btm.metainfo
        self.connectionManager = btm.connectionManager

        self.btfiles = BTFileManager(btm)

        self.bitfield = self.btfiles.bitfieldHave # 标记已经下载的块

        metainfo = self.metainfo
        self.piece_length = metainfo.piece_length
        self.pieces_size = metainfo.pieces_size
        self.pieces_hash = metainfo.pieces_hash

        self.buffer = {}        # 缓冲已完成的piece

        self.bfNeed = self.btfiles.bitfieldNeed   # 标记没有下载的块

        self.pieceDownload = {} # [idx]: [todo], [doing], [done] 
        self.pieceTodo = {}
        self.pieceDoing = {}
        self.pieceDone = {}

    def start(self) :
        self.btfiles.start()

    def stop(self) :
        self.btfiles.stop()

    def do_slice(self, beg, end):
        slice_list = []

        r = range(beg, end, self.slice_size)
        for beg in r[:-1] :
            slice_list.append((beg, self.slice_size))
        slice_list.append((r[-1], end-r[-1]))

        return slice_list

    def __getPieceSlice(self, idx):
        if idx == self.pieces_size-1:
            return self.do_slice(0, self.metainfo.last_piece_length)
        else:
            return self.do_slice(0, self.piece_length)
    
    def amInterested(self, idx):
        if type(idx) is Bitfield:
            try:
                for i in (self.bfNeed & idx):
                    return True
                else:
                    return False
            except TypeError: 
                return False 
        else:
            return idx in self.bfNeed

    def doIHave(self, index):
        return self.bitfield[index]

    def getMorePieceTask(self, peer_bf, num_task=5):
        if num_task == 0:
            return None
        tasks = []
        for idx in (peer_bf & self.bfNeed) :
            while True:
                task = self.getPieceTask(idx)
                if not task :
                    break
                tasks.append(task)
                if len(tasks) == num_task:
                    return tasks

    def getPieceTask(self, idx):
        assert idx in self.bfNeed

        if idx not in self.pieceDownload:
            slice_list = self.__getPieceSlice(idx)
            self.pieceDownload[idx] = [slice_list, [], []]

        task_to_do, task_doing, task_done = self.pieceDownload[idx]

        if not task_to_do:
            return None

        my_task = task_to_do[0]
        del task_to_do[0]

        task_doing.append(my_task)

        return idx, my_task

    def failedPieceTask(self, idx, task):
        #log.err('下载失败 {0}{1}'.format(idx, task))
        task_to_do, task_doing, task_done = self.pieceDownload[idx]
        assert task in task_doing

        task_doing.remove(task)

        task_to_do.append(task)

    def finishPieceTask(self, idx, task, data):
        task_to_do, task_doing, task_done = self.pieceDownload[idx]

        assert task in task_doing

        task_doing.remove(task)

        task_done.append((task, data))

        if not task_to_do and not task_doing :
            task_done.sort(key=lambda x : x[0][0])
            data = ''.join(d for t, d in task_done)

            try:
                self.btfiles.writePiece(idx, data)
                self.bitfield[idx] = 1
                self.bfNeed[idx] = 0

            except BTHashTestError as error:
                # sha1 error ~ corrupt piece
                del self.pieceDownload[idx]
                if idx == self.pieces_size-1:
                    self.do_slice_tail()

            else:
                self.connectionManager.broadcastHave(idx)
                
    def getPieceData(self, index, beg, length) :
        if not self.doIHave(index) :
            return None
        piece = self.btfiles.readPiece(index)
        if piece :
            return piece[beg:(beg+length)]
        else :
            return None

        
