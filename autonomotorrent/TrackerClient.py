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


# TODO: Figure out why we have these and why they are hardcoded...
peers = [('60.50.9.1', 14004), ('98.235.129.196', 42389), ('125.230.14.154', 11353),
         ('122.100.136.51', 56042), ('111.83.132.31', 25629), ('124.172.231.44', 10902),
         ('112.104.34.10', 16702), ('222.93.137.21', 13280), ('81.11.242.216', 6881),
         ('222.92.50.187', 45234), ('218.203.212.78', 1080), ('207.6.253.181', 16881),
         ('118.165.11.65', 15694), ('60.54.43.191', 42802), ('110.84.247.106', 9976),
         ('219.70.196.48', 12205), ('60.241.34.141', 64407), ('60.54.43.191', 42803),
         ('61.59.213.55', 18923), ('221.127.107.4', 24488), ('116.19.99.43', 8193),
         ('58.115.112.252', 16881), ('118.141.249.23', 7127), ('118.72.85.24', 11316),
         ('175.168.174.171', 10701), ('123.195.80.225', 12803), ('113.89.104.164', 10809),
         ('173.68.85.202', 49644), ('123.110.88.16', 32680), ('123.117.65.169', 80),
         ('58.253.17.13', 13005), ('114.36.24.127', 18162), ('125.73.29.234', 12555),
         ('219.85.209.33', 10438), ('122.100.205.2', 44916), ('210.66.166.76', 24924),
         ('61.148.123.130', 12902)]

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
                log.err("Received an invalid peer list from the tracker: {0}".format(url))
            else:
                if len(res) == 1:
                    log.msg('Tracker: {0}'.format(res)) # TODO: What is this?
                    return

                peers = res['peers']
                peers_list = []
                while peers:
                    addr = socket.inet_ntoa(peers[:4])
                    port = struct.unpack('!H', peers[4:6])[0]
                    peers_list.append((addr, port))
                    peers = peers[6:]
                log.msg('Received {0} peers from tracker: {1}'.format(len(peers_list), url))

                self.btm.add_peers(peers_list)
            
                interval = res.get('interval', self.interval)

                yield sleep(interval)
                self.getPeerList(url, data)

            
