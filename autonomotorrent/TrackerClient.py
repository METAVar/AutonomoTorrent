#
# -*-encoding:gb2312-*-

from twisted.internet import reactor

from bencode import bencode, bdecode, BTError

from twisted.python import log
from twisted.internet import defer
from twisted.web.client import getPage

from tools import sleep

from urllib import urlencode
import hashlib
import socket
import struct


class BTTrackerClient (object):
    def __init__(self, btm):
        self.btm = btm
        self.reciever = btm.connectionManager.clientFactory
        self.timmer = {}
        self.interval = 15 * 60

    @defer.inlineCallbacks
    def start(self):
        self.status = 'started'

        info_hash = self.btm.metainfo.info_hash
        peer_id = self.btm.my_peer_id
        port = self.btm.app.btServer.listen_port
        request = {
            'info_hash' : info_hash,
            'peer_id' : peer_id,
            'port' : port,
            'compact' : 1,
            #'key' : 'abcd', # This is optional anyways
            'uploaded' : 0,
            'downloaded' : 0,
            'left' : 100,
            'event' : 'started'
            }
        request_encode = urlencode(request)

        for url in self.btm.metainfo.announce_list :
            self.getPeerList(url, request_encode)
            yield sleep(1)

    def stop(self):
        self.status = 'stopped'

    @defer.inlineCallbacks
    def getPeerList(self, url, data):
        """TODO: This is in serious need of refactoring...
        """
        if self.status == 'stopped':
            return
        
        try:
            page = yield getPage(url + '?' + data)

        except Exception as error:
            log.err('Failed to connect to tracker: {0}'.format(url))

            yield sleep(self.interval)
            self.getPeerList(url, data)

        else:
            try:
                res = bdecode(page)
            except BTError:
                log.err("Received an invalid peer list from the tracker: " +\
                    "{0}".format(url))
            else:
                if len(res) == 1:
                    log.msg('Tracker: {0}'.format(res)) # TODO: What is this?
                    return

                peers = res['peers']
                peers_list = []
                try: # Try parsing in binary format first
                    while peers:
                        addr = socket.inet_ntoa(peers[:4])
                        port = struct.unpack('!H', peers[4:6])[0]
                        peers_list.append((addr, port))
                        peers = peers[6:]
                except: # Now try parsing in dictionary format
                    try:
                        for p in peers:
                            peers_list.append((p["ip"], p["port"]))
                    except:
                        log.err("Received an invalid peer list from the " +\
                            "tracker: {0}".format(url))

                log.msg('Received {0} peers from tracker: {1}'.format(
                    len(peers_list), url))
                self.btm.add_peers(peers_list)
                interval = res.get('interval', self.interval)
                yield sleep(interval)
                self.getPeerList(url, data)

            
