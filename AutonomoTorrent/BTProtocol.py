#
# -*-encoding:gb2312-*-

import hashlib
import struct
import socket
import time

from twisted.internet import reactor, defer
from twisted.internet import protocol
from twisted.python import log

from ClientIdentifier import identify_client
from bitfield import Bitfield
from tools import SpeedMonitor, sleep
from upload import BTUpload
from download import BTDownload

class BTProtocol (protocol.Protocol):

    msg_choke = '\x00'
    msg_unchoke = '\x01'
    msg_interested = '\x02'
    msg_not_interested = '\x03'
    msg_have = '\x04'
    msg_bitfield = '\x05'
    msg_request = '\x06'
    msg_piece = '\x07'
    msg_cancel = '\x08'
    msg_port = '\x09'

    msg_type = {'\x00' : 'choke',
                '\x01' : 'unchoke',
                '\x02' : 'interested',
                '\x03' : 'not_interested',
                '\x04' : 'have',
                '\x05' : 'bitfield',
                '\x06' : 'request',
                '\x07' : 'piece',
                '\x08' : 'cancel',
                '\x09' : 'port'}

    def __init__(self):
        self.peer_id = None

        self.status = None


    def connectionMade(self):
        self.status = 'handshake'

        self.data = ''
        self._handle_data = self.handle_data()
        self._next_data_len = self._handle_data.next()

        self.preHandshake()
        
    def finishHandshake(self):
        self.btm = self.factory.btm

        self.bitfield = Bitfield(self.btm.metainfo.pieces_size)

        self.upload = BTUpload(self)
        self.download = BTDownload(self)
        self.upload.start()
        self.__uploadMonitor = self.upload._uploadMonitor
        self.download.start()
        self.__downloadMonitor = self.download._downloadMonitor

        self.send_bitfield(self.btm.pieceManager.bitfield)
        
        self.send_keep_alive()

        if self.btm.connectionManager.isAlreadyConnected(self.peer_id) :
            reactor.callLater(0, self.transport.loseConnection)
            log.msg('<<-->> already connected, drop the connection')
        else:
            self.factory.addActiveConnection(self.peer_id, self)

        self.status = 'started'

    def connectionLost(self, reason=None):
        if self.status == 'started':
            self.upload.stop()
            self.download.stop()

            del self.__uploadMonitor
            del self.__downloadMonitor
            del self.upload
            del self.download
            del self.btm
            
        self.factory.removeActiveConnection(self)

        self.status = 'stopped'

    def stopConnection(self):
        if self.connected:
            self.transport.loseConnection()

    def send_data(self, data):
        if not self.connected:
            return

        prefix = struct.pack('!I', len(data))
        self.transport.write(prefix + data)

    def send_message(self, _type, data):
        self.send_data(_type + data)

        self.__uploadMonitor(_type, data)

    def __uploadMonitor(self, _type, data):
        pass
        
    def send_handshake(self):
        info_hash = self.factory.btm.metainfo.info_hash
        my_id = self.factory.btm.my_peer_id
        reserved = '\x00'*7 + '\x01'
        data = '\x13' + 'BitTorrent protocol' + reserved + info_hash + my_id
        self.transport.write(data)

        log.msg('<<-- handshake')

    @defer.inlineCallbacks
    def send_keep_alive(self):
        yield sleep(60.0)
        while self.connected:
            self.send_data('')
            log.msg('<<-- keep alive')

            yield sleep(60.0)

    def send_choke(self):
        self.am_choke = True
        self.send_data(self.msg_choke)

        log.msg('<<-- choke')
        
    def send_unchoke(self):
        self.am_choke = False
        self.send_data(self.msg_unchoke)

        log.msg('<<-- unchoke')

    def send_interested(self):
        self.am_interested = True
        self.send_data(self.msg_interested)

        log.msg('<<-- interested')

    def send_not_interested(self):
        self.am_interested = False
        self.send_data(self.msg_not_interested)

        log.msg('<<-- not interested')

    def send_have(self, index):
        data = struct.pack('!I', index)
        self.send_message(self.msg_have, data)

        log.msg('<<-- have index: {0}'.format(index))

    def send_bitfield(self, bitfield):
        if type(bitfield) is str :
            data = bitfield
        elif type(bitfield) is Bitfield :
            data = bitfield.tostring()
        else :
            raise TypeError('bitfield should be str or Bitfield')

        self.send_message(self.msg_bitfield, data)

        log.msg('<<-- bitfield')
        
    def send_request(self, index, begin, length):
        data = struct.pack('!III', index, begin, length)
        self.send_message(self.msg_request, data)

        log.msg('<<-- request index={0}, begin={1}, length={2}'.format(index, begin,
            length))

    def send_piece(self, index, begin, piece):
        data = struct.pack('!II', index, begin) + piece
        self.send_message(self.msg_piece, data)

        log.msg('<<-- piece index={0}, begin={1}'.format(index, begin))

    def send_cancel(self, idx, begin, length):
        data = struct.pack('!III', idx, begin, length)
        self.send_message(self.msg_cancel, data)

        log.msg('<<-- cancel index={0}, begin={1}'.format(idx, begin))

    def send_port(self, port):
        data = struct.pack('!I', port)
        self.send_message(self.msg_port, data)

        log.msg('<<-- port {0}'.format(port))

    def __downloadMonitor(self, data):
        pass
    
    def dataReceived(self, data):
        self.__downloadMonitor(data)

        data = self.data + data
        nd_len = self._next_data_len

        while len(data) >= nd_len:
            data_send, data = data[:nd_len], data[nd_len:]
            nd_len = self._handle_data.send(data_send)

        self.data = data
        self._next_data_len = nd_len
        
    def handle_data(self):
        protocol = yield ord((yield 1))
        reserved = yield 8
        info_hash = yield 20
        peer_id = yield 20

        self.handle_handshake(protocol, reserved, info_hash, peer_id)

        self.postHandshake()

        self.finishHandshake()

        while True:
            size, = struct.unpack('!I', (yield 4))
            if size == 0 :
                self.handle_keep_alive()
            else:
                _type = yield 1
                self.cur_msg_type = _type
                
                data = yield (size - 1)
                
                method_name = 'handle_'+self.msg_type[_type]
                method = getattr(self, method_name, None)
                if method:
                    method(data)
                else:
                    raise NotImplementedError(method_name)

    def handle_handshake(self, protocol, reserved, info_hash, peer_id):
        log.msg('-->> handshake {0}'.format(identify_client(peer_id)))

        self.peer_protocol = protocol
        self.peer_reserved = reserved
        self.peer_info_hash = info_hash
        self.peer_id = peer_id
    
    def handle_keep_alive(self):
        log.msg('-->> keep alive')

    def handle_choke(self, data):
        log.msg('-->> choke')
        self.download._choke(True)

    def handle_unchoke(self, data):
        log.msg('-->> unchoke')
        self.download._choke(False)

    def handle_interested(self, data):
        log.msg('-->> interested')
        self.upload._interested(True)
        
    def handle_not_interested(self, data):
        log.msg('-->> not interested')
        self.upload._interested(False)

    def handle_have(self, data):
        assert len(data) == 4
        index, = struct.unpack('!I', data)
        self.download._have(index)
        # print '-->> have index=%d' % index

    def handle_bitfield(self, data):
        log.msg('-->> bitfield')

        self.download._bitfield(data)

    def handle_request(self, data):
        index, begin, length = struct.unpack('!III', data)

        log.msg('-->> request index={0}, begin={1}, length={2}'.format(index, begin,
            length))

        self.upload._request(index, begin, length)
    
    def handle_piece(self, data):
        index, begin = struct.unpack('!II', data[:8])
        piece = data[8:]

        log.msg('-->> piece index={0}, begin={1}, length={2}'.format(index,
            begin, len(piece)))

        self.download._piece(index, begin, piece)

    def handle_cancel(self, data):
        index, begin, length = struct.unpack('!III', data)

        log.msg('-->> cancel index={0}, begin={1}, length={2}'.format(index, begin,
            length))

        self.upload._cancel(index, begin, length)

    dht_fp = open('dht.txt', 'wb')

    def handle_port(self, data):
        port, = struct.unpack('!H', data)
        self.dht_port = port

        addr = self.transport.getPeer().host
        
        log.msg('-->> port ', '{}:{}'.format(addr, port))

        self.dht_fp.write('{}\t{}\n'.format(addr, port))
        self.dht_fp.flush()

        self.btm.connectionManager.handle_port(addr, port)

############################################################
class BTClientProtocol (BTProtocol):
    def preHandshake(self):
        self.send_handshake()

    def postHandshake(self):
        if self.peer_info_hash == self.factory.btm.metainfo.info_hash :
            pass
        else:
            reactor.callLater(0, self.transport.loseConnection)

class BTServerProtocol (BTProtocol):
    def preHandshake(self):
        pass

    def postHandshake(self):
        factory = self.factory.resetFactory(self, self.peer_info_hash)
        if factory :
            self.send_handshake()
        else:
            reactor.callLater(0, self.transport.loseConnection)

############################################################
