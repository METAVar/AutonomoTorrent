"""Provides basic DHT functionality using Twisted
"""
import hashlib
import struct
import socket
import time
import os
import re
import pickle
import bz2

from twisted.internet import reactor
from twisted.internet import protocol, defer
from twisted.python import log

from bencode import bencode, bdecode, BTError

def sleep(timeout):
    df = defer.Deferred()
    reactor.callLater(timeout, df.callback, None)
    return df

@defer.inlineCallbacks
def dns_resolve(addr):
    ip, port = addr
    if re.match(r'^(\d+\.){3}\d+$', ip):
        defer.returnValue(addr)
    else:
        try:
            ip = yield reactor.resolve(ip)
            addr = ip, port
            defer.returnValue(addr)
        except Exception as err :
            raise DHTError(err)

def decodeIPAddr(addr) :
    if type(addr) is not str:
        raise TypeError('addr should be a string')

    if len(addr) != 6:
        raise ValueError('len(addr) == 6')
        
    ip = socket.inet_ntoa(addr[0:4])
    port, = struct.unpack('!H', addr[4:6])
    return ip, port

def encodeIPAddr(addr):
    '''
    @addr : (ip, port)
    '''
    ip, port = addr
    s_ip = socket.inet_aton(ip)
    s_port = struct.pack('!H', port)
    return s_ip + s_port

def decodeCompactNodes(compNodes):
    if type(compNodes) is not str:
        raise TypeError('compNodes should be a string')

    if len(compNodes) % 26 != 0 :
        raise ValueError('len(compNodes) % 26 != 0')
    
    nodes = []
    for i in xrange(0, len(compNodes), 26) :
        dat = compNodes[i:(i+26)]
        _id = dat[0:20]
        ip, port = decodeIPAddr(dat[20:26])
        nodes.append((_id, (ip, port)))
    return nodes

def encodeCompactNodes(nodes):
    '''
    @nodes: [(id, (ip, port)), (id, (ip, port)), ...]
    '''
    return ''.join(_id + encodeIPAddr(addr) for _id, addr in nodes)

def decodeCompactPeers(compPeers):
    return [decodeIPAddr(addr) for addr in compPeers]

def encodeCompactPeers(peers) :
    '''
    @peers: [(ip, port), (ip, port), ...]
    '''
    return [encodeIPAddr(addr) for addr in peers]

class RoutingTable :
    timeout = 15 * 60  # 15 min
    
    def __init__(self):
        self.my_node_id = hashlib.sha1(os.urandom(160)).digest()
        self.nodes_dict = {}
        self.bucket = []
        self.k_value = 8

    def doStart(self, dht_protocol):
        self.dht = dht_protocol
        dht = self.dht
        nodes_dict = self.nodes_dict
        self.nodes_dict = {}
        del self.bucket[:]

        [self.addNode(addr) for addr in nodes_dict.itervalues()]

        self.autoFillRoutingTable()

    def doStop(self):
        self.dht = None

    @defer.inlineCallbacks
    def autoFillRoutingTable(self):
        if len(self.nodes_dict) > 160 * 6:
            return

        query_history = set()
        while len(self.nodes_dict) < 160*6:
            for _id, addr in self.nodes_dict.iteritems():
                if _id not in query_history:
                    query_history.add(_id)
                    break
            else:
                break

            try:
                _id, nodes = yield self.dht.find_node(addr, _id)
            except DHTError:
                pass
            else:
                [(yield fd) for fd in
                 [self.addNode(addr) for _id, addr in nodes]]
        
    @defer.inlineCallbacks
    def addNode(self, addr):
        try:
            _id = yield self.dht.ping(addr)
        except DHTError as err:
            defer.returnValue(False)
        else:
            self.addGoodNode(_id, addr)
            defer.returnValue(True)

        if _id in self.nodes_dict :
            self.updateNode(_id)
            defer.returnValue(True)

    @defer.inlineCallbacks        
    def addGoodNode(self, node_id, node_addr):
        if node_id in self.nodes_dict :
            self.updateNode(node_id)
            return

        if len(self.nodes_dict) > 160 * 6: # too many nodes in the table
            return
        
        self.nodes_dict[node_id] = node_addr
        self.__addToBucket(node_id)

        yield sleep(15*60)
        while (node_id in self.nodes_dict and self.dht) :
            try:
                _id = yield self.dht.ping(self.nodes_dict[node_id])
                assert node_id == _id
            except DHTError as err:
                self.removeNode(node_id)
                break
            else:
                self.updateNode(node_id)
                yield sleep(15*60)

    def updateNode(self, node_id):
        if node_id not in self.nodes_dict:
            return

        self.__addToBucket(node_id)

    def __addToBucket(self, node_id):
        '''
            0     1     2        3
        [[159],[158],[157], [156~0]]
        '''
        if len(self.bucket) == 0:
            self.bucket.append([node_id])

        idx = 159 - self.__distance(node_id)

        if idx == 160:
            return

        b_size = len(self.bucket)

        if (b_size-1) <= idx < 159:
            buk = self.bucket[-1]
            try:
                buk.remove(node_id)
            except ValueError:
                pass
            buk.append(node_id)

            if len(buk) > self.k_value: 
                _buk, buk_ = [], []
                for node in buk:
                    _idx = 159 - self.__distance(node)
                    if _idx == (b_size-1):
                        _buk.append(node)
                    else:
                        buk_.append(node)
                self.bucket[-1:] = [_buk, buk_]
        else:
            buk = self.bucket[idx]
            try:
                buk.remove(node_id)
            except ValueError:
                pass
            buk.append(node_id)

            if len(buk) > self.k_value:
                del self.nodes_dict[buk[0]]
                del buk[0]              

    def __distance(self, node_id):
        for i in range(20):
            val = ord(self.my_node_id[i]) ^ ord(node_id[i])
            if val:
                for j in range(8):
                    if val & (0x80>>j):
                        return 159 - (i*8 + j)
        else:
            return -1

    def __removeFromBucket(self, node_id):
        if len(self.bucket) ==0 :
            return

        idx = 159 - self.__distance(node_id)

        if idx >= len(self.bucket):
            idx = -1

        try:
            self.bucket[idx].remove(node_id)
        except ValueError:
            pass

    def __findFromBucket(self, node_id):
        if len(self.bucket) == 0:
            return []

        b_size = len(self.bucket)
        
        idx = 159 - self.__distance(node_id)
        if idx >= b_size:
            idx = b_size - 1

        result = self.bucket[idx][:]

        if len(result) >= self.k_value:
            return result
        
        for i in range(1, 160):
            idx_ = idx + 1
            if idx_ < b_size:
                size_need = self.k_value - len(result)
                result += self.bucket[idx_][:size_need]
                if len(result) >= self.k_value:
                    break

            _idx = idx - 1
            if _idx >= 0 :
                size_need = self.k_value - len(result)
                result += self.bucket[_idx][:size_need]
                if len(result) >= self.k_value:
                    break

        return result

    def removeNode(self, node_id):
        '''
        node is bad node and node_id is already in the table
        '''
        if node_id in self.nodes_dict:
            del self.nodes_dict[node_id]
            self.__removeFromBucket(node_id)

    def queryNode(self, node_id):
        '''
        find node of node_id
        if node_id in the table, return it
        otherwise, return the closest nodes
        return: [(id,(ip, port)), ...]
        '''
        return [(_id, self.nodes_dict[_id]) for _id in self.__findFromBucket(node_id)]

    def __contains__(self, node_id):
        return node_id in self.nodes_dict

    def __getitem__(self, node_id):
        return self.nodes_dict[node_id]

class DHTError (Exception):
    pass

class DHTProtocolBase (protocol.DatagramProtocol) :
    timeout = 15  # seconds

    def __init__(self):
        self.my_node_id = os.urandom(20)

        self.transaction = {}
        self.recieved_tokens = {}
        self.sent_tokens = {}

    def startProtocol(self):
        pass
        
    def stopProtocol(self):
        pass

    @defer.inlineCallbacks
    def ping(self, node_addr, timeout=None):
        args = {'id' : self.my_node_id}
        data = yield self.__KRPC_do_query(node_addr, 'ping', args, timeout)
        node_id = data['id']
        defer.returnValue(node_id)

    @defer.inlineCallbacks
    def find_node(self, node_addr, target_id, timeout=None):
        args = {'id' : self.my_node_id,
                'target' : target_id}
        data = yield self.__KRPC_do_query(node_addr, 'find_node', args, timeout)
        node_id = data['id']
        nodes = decodeCompactNodes(data['nodes'])
        defer.returnValue((node_id, nodes))

    @defer.inlineCallbacks
    def get_peers(self, node_addr, info_hash, timeout=None):
        args = {'id' : self.my_node_id,
                'info_hash' : info_hash}
        data = yield self.__KRPC_do_query(node_addr, 'get_peers', args, timeout)
        node_id = data['id']

        if 'token' in data:
            self.recieved_tokens[node_addr] = data['token']
        
        def token_timeout():
            if node_addr in self.recieved_tokens:
                del self.recieved_tokens[node_addr]
        reactor.callLater(600, token_timeout) # 10 min life time

        if 'values' in data :
            try:
                peers = decodeCompactPeers(data['values'])
            except (TypeError, ValueError) as error:
                raise DHTError(error)
            else:
                defer.returnValue((node_id, 'values', peers))

        elif 'nodes' in data :
            try:
                nodes = decodeCompactNodes(data['nodes'])
            except (TypeError, ValueError) as error:
                raise DHTError(error)
            else:
                defer.returnValue((node_id, 'nodes', nodes))
        else:
            assert False

    @defer.inlineCallbacks
    def announce_peer(self, node_addr, info_hash, port, timeout=None):
        if node_addr not in self.recieved_tokens:
            node_id, _type, peers = yield self.get_peers(node_addr, info_hash)

        token = self.recieved_tokens.get(node_addr, '')

        args = {'id' : self.my_node_id,
                'info_hash' : info_hash,
                'port' : port,
                'token' : token}
        
        data = yield self.__KRPC_do_query(node_addr, 'announce_peer', args, timeout)
        node_id = data['id']

        defer.returnValue(node_id)

    @defer.inlineCallbacks
    def __KRPC_do_query(self, node_addr, qtype, args, timeout=None) :
        t_id = os.urandom(20)
        self._KRPC_send_query(node_addr, t_id, qtype, args)
        
        df = defer.Deferred()
        self.transaction[t_id] = df

        @defer.inlineCallbacks
        def timeout_check(timeout):
            if timeout is None: timeout = self.timeout
            yield sleep(timeout)        
            if t_id in self.transaction:
                df.errback(DHTError((0, 'timeout: "{}" to {}'.format(qtype, node_addr))))

        timeout_check(timeout)

        try:
            data = yield df
        finally:
            del self.transaction[t_id]

        defer.returnValue(data)

    def __KRPC_fire_response(self, t_id, data, node_addr):
        if t_id in self.transaction:
            df = self.transaction[t_id]
            df.callback(data)
        else:   # timeout
            pass

    def __KRPC_fire_error(self, t_id, error, node_addr):
        if t_id in self.transaction:
            df = self.transaction[t_id]
            df.errback(DHTError(*error))
        else:   # timeout
            pass

    def _KRPC_send_query(self, node_addr, t_id, qtype, args):
        data = {'t' : t_id,
                'y' : 'q',
                'q' : qtype,
                'a' : args }
        self.writeDatagram(bencode(data), node_addr)

    def _KRPC_send_response(self, node_addr, t_id, args):
        response = {'t' : t_id,
                    'y' : 'r',
                    'r' : args}
        self.writeDatagram(bencode(response), node_addr)

    def _KRPC_send_error(self, node_addr, t_id, error):
        data = {'t' : t_id,
                'y' : 'e',
                'e' : error}
        self.writeDatagram(bencode(data), node_addr)
        
    def _KRPC_recieve_response(self, data, node_addr):
        assert data['y'] == 'r'
        t_id = data['t']
        args = data['r']
        node_id = args['id']

        self.__KRPC_fire_response(t_id, data['r'], node_addr)

    def _KRPC_recieve_error(self, data, node_addr):
        assert data['y'] == 'e'
        t_id = data['t']
        self.__KRPC_fire_error(t_id, data['e'], node_addr)

    def _KRPC_recieve_Query(self, data, node_addr):
        assert data['y'] == 'q'
        t_id = data['t']
        args = data['a']
        node_id = args['id']

        name = 'handle_' + data['q']
        if hasattr(self, name):
            getattr(self, name)(t_id, data['a'], node_addr)

        self._handle_query(node_id, node_addr)

    @defer.inlineCallbacks
    def writeDatagram(self, data, node_addr):
        node_addr = yield dns_resolve(node_addr)
        for i in range(10):
            try:
                self.transport.write(data, node_addr)
            except:
                log.err()
        
    def datagramReceived(self, datagram, node_addr):
        try:
            data = bdecode(datagram)
        except BTError:
            return
        if data['y'] == 'q':
            self._KRPC_recieve_Query(data, node_addr)
        elif data['y'] == 'r':
            self._KRPC_recieve_response(data, node_addr)
        elif data['y'] == 'e':
            self._KRPC_recieve_error(data, node_addr)
        else:
            assert False

            
    def handle_ping(self, t_id, data, node_addr):
        node_id = data['id']
        args = {'id' : self.my_node_id}
        self._KRPC_send_response(node_addr, t_id, args)

    def handle_find_node(self, t_id, data, node_addr):
        node_id = data['id']
        target_id = data['target']
        nodes = self._handle_find_node(target_id)
        args = {'id' : self.my_node_id,
                'nodes' : encodeCompactNodes(nodes)}
        self._KRPC_send_response(node_addr, t_id, args)
        
    def handle_get_peers(self, t_id, data, node_addr):
        node_id = data['id']
        info_hash = data['info_hash']

        token = hashlib.sha1(node_addr[0]+os.urandom(20)).digest()
        self.sent_tokens[token] = node_addr[0]
        def token_invalid():
            del self.sent_tokens[token]
        reactor.callLater(600, token_invalid)

        _type, peers_or_nodes = self._handle_get_peers(info_hash)
        if _type == 'values':
            values = encodeCompactPeers(peers_or_nodes)
            args = {'id' : self.my_node_id,
                    'values' : values,
                    'token' : token}

        elif _type == 'nodes' :
            values = encodeCompactNodes(peers_or_nodes)
            args = {'id' : self.my_node_id,
                    'nodes' : values,
                    'token' : token}

        self._KRPC_send_response(node_addr, t_id, args)

    def handle_announce_peer(self, t_id, data, node_addr):
        node_id = data['id']
        info_hash = data['info_hash']
        port = data['port']
        token = data['token']
        ip = node_addr[0]

        if token not in self.sent_tokens:
            error = [203, 'protocol error: invalid token']
            self._KRPC_send_error(node_addr, t_id, error)
            return

        self._handle_announce_peer(info_hash, (ip, port))

        args = {'id' : self.my_node_id}
        self._KRPC_send_response(node_addr, t_id, args)
    
    def _handle_get_peers(self, info_hash):
        raise NotImplemented()

    def _handle_find_node(self, target_id):
        raise NotImplemented()

    def _handle_announce_peer(self, info_hash, peer_addr):
        raise NotImplemented()

    def _handle_query(self, node_id, node_addr):
        raise NotImplemented()

class DHTProtocol (DHTProtocolBase) :

    def __init__(self):
        DHTProtocolBase.__init__(self)

        self.torrent = {}

    def startProtocol(self):
        self.routingTable = RoutingTable()
        self.my_node_id = self.routingTable.my_node_id
        self.routingTable.doStart(self)
        
    def stopProtocol(self):
        self.routingTable.doStop()
        self.torrent = {}

    @defer.inlineCallbacks
    def addNode(self, addr):
        ip, port = addr
        yield self.routingTable.addNode(addr)
        self.routingTable.autoFillRoutingTable()

    @defer.inlineCallbacks
    def searchPeers(self, node_addr, info_hash):
        try:
            node_id, _type, values =  (yield self.get_peers(node_addr, info_hash))
        except DHTError as err:
            log.err() 
            return
        else:
            node_id, nodes = yield self.find_node(node_addr, node_id)
        
    @defer.inlineCallbacks
    def register_torrent(self, info_hash, my_peer_port, callback):
        assert callable(callback)
        
        if info_hash in self.torrent:
            yield self.__updatePeers(info_hash)
            return

        args = {'callback':callback,
                'port' : my_peer_port,
                'result' : set(),
                'status' : 'idle'}

        self.torrent[info_hash] = args

        while info_hash in self.torrent:
            yield self.__updatePeers(info_hash)
            size = len(args['result'])
            if 100 < size:
                yield sleep(15*60)
            elif 50 < size <= 100:
                yield sleep(10*60)
            else:
                yield sleep(5*60)

    @defer.inlineCallbacks
    def __updatePeers(self, info_hash):
        args = self.torrent[info_hash]

        if args['status'] == 'running':
            return

        args['status'] = 'running'
        nodes = self.routingTable.queryNode(info_hash)
        query_history = set()

        dfs = []
        for node in nodes:
            df = self._getPeers(node, info_hash, query_history)
            dfs.append(df)
            yield sleep(0)

        [(yield df) for df in dfs]

        args['status'] = 'idle'

    def unregsiter_torrent(self, info_hash):
        if info_hash in self.torrent:
            del self.torrent[info_hash]

    @defer.inlineCallbacks
    def _getPeers(self, node, info_hash, query_history=set()):
        if info_hash not in self.torrent:
            return

        node_id, node_addr = node
        ip, port = node_addr

        if node_addr in query_history:
            return
        else:
            query_history.add(node_addr)

        args = self.torrent[info_hash]
        peers_callback = args['callback']
        my_peer_port = args['port']
        peers_result = args['result']

        try:
            node_id, _type, values =  (yield self.get_peers(node_addr, info_hash))
        except DHTError as err:
            self.routingTable.removeNode(node_id)
            return

        self.routingTable.addGoodNode(node_id, node_addr)

        if _type == 'values':
            peers_result |= set(values)
            peers_callback(values)
            if my_peer_port :
                try:
                    _id = yield self.announce_peer(node_addr, info_hash, my_peer_port)
                except DHTError as err:
                    pass

        elif _type == 'nodes':
            dfs = []
            for node in values:
                df = self._getPeers(node, info_hash, query_history)
                dfs.append(df)
                yield sleep(0)

            [(yield df) for df in dfs]    # wait for all children finishing

        else:
            assert False

    @defer.inlineCallbacks
    def _handle_query(self, node_id, node_addr):
        if node_id in self.routingTable:
            self.routingTable.updateNode(node_id)
        else:
            try:
                _id = yield self.ping(node_addr)
                assert _id == node_id
            except DHTError as err:
                pass
            else:
                self.routingTable.addGoodNode(_id, node_addr)
        
    def _handle_find_node(self, target_id):
        return self.routingTable.queryNode(target_id)
        
    def _handle_get_peers(self, info_hash):
        if info_hash in self.torrent:
            peers = list(self.torrent[info_hash])[:10]
            return 'values', peers
        else:
            nodes = self.routingTable.queryNode(info_hash)
            return 'nodes', nodes

    def _handle_announce_peer(self, info_hash, peer_addr):
        pass

