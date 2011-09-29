#
# -*-encoding:gb2312-*-

import abc

from twisted.python import log
from twisted.internet import reactor
from twisted.internet import protocol, defer

from tools import SpeedMonitor, sleep
from BTProtocol import BTClientProtocol, BTServerProtocol

class IConnectionManager (object) :
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def start(self):
        pass

    @abc.abstractmethod
    def stop(self):
        pass

    @abc.abstractmethod
    def broadcastHave(self, idx):
        pass

    @abc.abstractmethod
    def redownloadPiece(self, idx):
        pass

    @abc.abstractmethod
    def broadcastCancelPiece(self, idx, begin, length):
        pass

    @abc.abstractmethod
    def isAlreadyConnected(self, peer_id):
        pass

    @abc.abstractmethod
    def getConnection(self, peer_id) :
        pass

class ConnectionManager (IConnectionManager):
    def __init__(self, btm):
        self.btm = btm
        self.btServer = self.btm.app.btServer

        self.clientFactory = BTClientFactory(btm) # 管理主动连接
        self.serverFactory = BTServerFactory(btm) # 管理被动连接

    def start(self):
        self.clientFactory.start()
        self.serverFactory.start()

        self.btServer.addFactory(self.serverFactory)

    def stop(self):
        self.clientFactory.stop()
        self.serverFactory.stop()

        self.btServer.removeFactory(self.serverFactory)    

    def broadcastHave(self, idx):
        self.clientFactory.broadcastHave(idx)
        self.serverFactory.broadcastHave(idx)

    def redownloadPiece(self, idx):
        self.clientFactory.redownloadPiece(idx)
        self.serverFactory.redownloadPiece(idx)

    def broadcastCancelPiece(self, idx, begin, length):
        self.clientFactory.broadcastPiece(idx, begin, length)
        self.serverFactory.broadcastPiece(idx, begin, length)

    def isAlreadyConnected(self, peer_id):
        return self.clientFactory.isAlreadyConnected(peer_id) \
            or self.serverFactory.isAlreadyConnected(peer_id)

    def getConnection(self, peer_id) :
        return self.clientFactory.getConnection(peer_id) \
            or self.serverFactory.getConnection(peer_id)

    @defer.inlineCallbacks
    def handle_port(self, addr, port):
        if self.btm.app.enable_DHT:
            dht = self.btm.app.dht
            info_hash = self.btm.info_hash
            myport = self.btm.app.listen_port
            
            yield dht.addNode((addr, port))

            def callback(peers):
                log.msg('Received {0} peers from DHT'.format(len(peers)))
                self.clientFactory.updateTrackerPeers(peers)

            yield dht.register_torrent(info_hash, myport, callback)

class ConnectionManagerBase (IConnectionManager):
    def __init__(self, btm):
        self.btm = btm
        self.info_hash = btm.metainfo.info_hash

        self.active_connection = {}

        self.downloadSpeedMonitor = SpeedMonitor()
        self.downloadSpeedMonitor.registerObserver(btm.downloadSpeedMonitor)

        self.uploadSpeedMonitor = SpeedMonitor()
        self.uploadSpeedMonitor.registerObserver(btm.uploadSpeedMonitor)


    def addActiveConnection(self, peerid, connection):
        peerid = connection.peer_id
        self.active_connection[peerid] = connection

    def removeActiveConnection(self, peerid):
        if peerid in self.active_connection:
            del self.active_connection[peerid]

    def isAlreadyConnected(self, peer_id) :
        return peer_id in self.active_connection
    
    def getConnection(self, peer_id) :
        return self.active_connection.get(peer_id, None)

    def broadcastHave(self, idx):
        for peerid, con in self.active_connection.iteritems():
            con.send_have(idx)

    def redownloadPiece(self, idx):
        for peerid, con in self.active_connection.iteritems():
            con.redownloadPiece(idx)

    def broadcastCancelPiece(self, idx, begin, length):
        for peerid, con in self.active_connection.iteritems():
            con.send_cancel(idx, begin, length)

    def start(self):
        pass

    def stop(self):
        pass

class BTClientFactory(protocol.ClientFactory, ConnectionManagerBase):
    protocol = BTClientProtocol

    def __init__(self, btm):
        ConnectionManagerBase.__init__(self, btm)

        self.peers_connecting = set()
        self.peers_failed = set()
        self.peers_blacklist = set()

        self.peers_retry = {}

    def updateTrackerPeers(self, newPeers):
        newPeers = set(newPeers)
        newPeers -= self.peers_connecting | self.peers_blacklist | self.peers_failed

        self.conncectPeers(newPeers)

    @defer.inlineCallbacks
    def conncectPeers(self, peers):
        for addr, port in peers:
            reactor.connectTCP(addr, port, self)
            yield sleep(0)
    
    def startFactory(self):
        pass

    def stopFactory(self):
        pass

    def startedConnecting(self, connector):
        #print '开始连接', connector.getDestination()
        addr = self.getPeerAddr(connector)
        self.peers_connecting.add(addr)

    def clientConnectionFailed(self, connector, reason):
        #print '连接不上', connector.getDestination(), reason
        self.connectRetry(connector)

    def clientConnectionLost(self, connector, reason):
        #print '连接丢失', connector.getDestination(), reason
        #self.connectRetry(connector)
        self.connectRetry(connector)

    @defer.inlineCallbacks
    def connectRetry(self, connector):
        addr = self.getPeerAddr(connector)

        if addr in self.peers_retry:
            retry = self.peers_retry[addr]
        else:
            retry = 0

        if retry > 50:
            self.peers_failed.add(addr)
            self.peers_connecting.remove(addr)
            del self.peers_retry[addr]
        else:
            yield sleep(5)
            connector.connect()
            retry += 1
            self.peers_retry[addr] = retry

    def getPeerAddr(self, connector):
        ipaddr = connector.getDestination()
        addr = ipaddr.host, ipaddr.port
        return addr

class BTServerFactory (protocol.ServerFactory, ConnectionManagerBase):
    '''
    监听端口 仅服务于 一个bt任务
    '''

    protocol = BTServerProtocol

    def __init__(self, btm):
        ConnectionManagerBase.__init__(self, btm)

    def resetFactory(self, protocol, info_hash):
        assert peer.factory is self
        return self

    def __getattr__(self, name):
        return getattr(self.btm.app.btServer, name)
        
class BTServerFactories (protocol.ServerFactory):
    """ 
    """ 

    protocol = BTServerProtocol
    
    def __init__(self, listen_port=6881):
        self.maps = {}
        self.listen_port = listen_port
    
    def startFactory(self):
        pass

    def stopFactory(self):
        pass

    def addFactory(self, factory):
        info_hash = factory.info_hash
        if info_hash not in self.maps:
            factory.factories = self
            self.maps[factory.info_hash] = factory

    def removeFactory(self, factory):
        info_hash = factory.info_hash
        if info_hash in self.maps:
            try:
                del factory.maps
            except:
                pass
            try:
                del self.maps[info_hash]
            except:
                pass
    
    def resetFactory(self, protocol, info_hash):
        if info_hash in self.maps :
            protocol.factory = self.maps[info_hash]
            return protocol.factory
        else:
            return None
