#
# -*-encoding:gb2312-*-

from twisted.internet import defer
from PieceManager import BTPieceManager
from tools import SpeedMonitor, generate_peer_id, sleep
from factory import ConnectionManager
from TrackerClient import BTTrackerClient

class BTManager (object):
    def __init__(self, app, config):
        self.app = app
        self.config = config
        self.metainfo = config.metainfo
        self.info_hash = self.metainfo.info_hash
        self.downloadSpeedMonitor = SpeedMonitor(5)
        self.uploadSpeedMonitor = SpeedMonitor(5)
        self.my_peer_id = generate_peer_id()
        self.connectionManager = ConnectionManager(self)
        self.pieceManager = BTPieceManager(self)
        self.bttrackerclient = BTTrackerClient(self) # 管理对tracker服务器的连接
        self.status = None

    def startDownload(self):
        self.pieceManager.start()

        self.connectionManager.start()
        
        self.downloadSpeedMonitor.start()
        self.uploadSpeedMonitor.start()

        self.bttrackerclient.start() # 从tracker服务器更新peers list

        self.status = 'running'

    def stopDownload(self):
        self.pieceManager.stop()

        self.connectionManager.stop()
        
        self.downloadSpeedMonitor.stop()
        self.uploadSpeedMonitor.stop()

        self.bttrackerclient.stop()

        self.status = 'stopped'

    def get_speed(self):
        """Returns the speed in kibibit per second (Kibit/s).
        """
        return {
            "down": self.downloadSpeedMonitor.get_speed(),
            "up":   self.uploadSpeedMonitor.get_speed()  }

    def get_num_connections(self):
        return {
            "client": len(self.connectionManager.clientFactory.active_connection),
            "server": len(self.connectionManager.serverFactory.active_connection)}

    def exit(self):
        if self.status == 'running' :
            self.stopDownload()

        for i in self.__dict__ :
            del self.__dict__[i]

