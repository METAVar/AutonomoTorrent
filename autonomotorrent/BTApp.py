"""
"""
import sys
import os

import os
from twisted.python import log
from twisted.internet import reactor
from twisted.internet import task 

from autonomotorrent.BTManager import BTManager
from autonomotorrent.factory import BTServerFactories
from autonomotorrent.MetaInfo import BTMetaInfo
from autonomotorrent.DHTProtocol import DHTProtocol

class BTConfig(object):
    def __init__(self, torrent_path=None, meta_info=None):
        if torrent_path:
            #self.torrentPath = torrent_path #TODO: Do we need this?
            self.metainfo = BTMetaInfo(path=torrent_path)
        elif meta_info:
            self.metainfo = BTMetaInfo(meta_info=meta_info)
        else:
            raise Exception("Must provide either a torrent path or meta_info.")

        self.info_hash = self.metainfo.info_hash
        self.downloadList = None

    def check(self) :
        if self.downloadList is None:
            self.downloadList = range(len(self.metainfo.files))
        for i in self.downloadList :
            f = self.metainfo.files[i]
            size = f['length']
            name = f['path']
            log.msg("File: {0} Size: {1}".format(name, size)) # TODO: Do we really need this?
            
class BTApp:
    def __init__(self, save_dir=".", 
                       listen_port=6881, 
                       enable_DHT=False,
                       remote_debugging=False):
        log.startLogging(sys.stdout) # Start logging to stdout
        self.save_dir = save_dir
        self.listen_port = listen_port
        self.enable_DHT = enable_DHT
        self.tasks = {}
        self.btServer = BTServerFactories(self.listen_port)
        reactor.listenTCP(self.listen_port, self.btServer)

        if enable_DHT:
            log.msg("Turning DHT on.")
            self.dht = DHTProtocol()
            reactor.listenUDP(self.listen_port, self.dht)

        if remote_debugging:
            log.msg("Turning remote debugging on. You may login via telnet " +\
                "on port 9999 username & password are 'admin'")
            import twisted.manhole.telnet
            dbg = twisted.manhole.telnet.ShellFactory()
            dbg.username = "admin"
            dbg.password = "admin"
            dbg.namespace['app'] = self 
            reactor.listenTCP(9999, dbg)

        task.LoopingCall(self.get_status).start(5, now=False)

    def add_torrent(self, config):
        config.check()
        hs = config.info_hash
        if hs in self.tasks:
            log.msg('{0} is already in download list'.format(hs))
        else:
            btm = BTManager(self, config)
            self.tasks[hs] = btm
            btm.startDownload()
            return hs

    def stop_torrent(self, key):
        info_hash = key
        if info_hash in self.tasks:
            btm = self.tasks[info_hash]
            btm.stopDownload()
        
    def remove_torrent(self, key):
        info_hash = key
        if info_hash in self.tasks:
            btm = self.tasks[info_hash]
            btm.exit()

    def stop_all_torrents(self):
        for task in self.tasks.itervalues() :
            task.stopDownload()

    def get_status(self):
        """Returns a dictionary of stats on every torrent and total speed.
        """
        status = {}
        for torrent_hash, bt_manager in self.tasks.iteritems():
            status[torrent_hash] = {
                "state": bt_manager.status,
                "speed": bt_manager.get_speed(),
                "num_connections": bt_manager.get_num_connections(),
                }
            try:
                status["all"]["speed"]["up"] += status[torrent_hash]["speed"]["up"] 
                status["all"]["speed"]["down"] += status[torrent_hash]["speed"]["down"] 
            except KeyError:
                status["all"] = {"speed": 
                        {"up": status[torrent_hash]["speed"]["up"], 
                        "down": status[torrent_hash]["speed"]["down"]}, 
                    }


        log.msg("Status: {0}".format(status,))
        return status

    def start_reactor(self):
        reactor.run()
