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
    def __init__(self, torrent_path=None, meta_info=None, trackerless=False):
        self.trackerless = trackerless
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
                       remote_debugging=False, 
                       global_peers=None):
        """
        @param remote_degugging enables telnet login via port 9999 with a
            username and password of 'admin'
        @param global_peers list of tuples e.g. [('173.248.194.166', 12005),
            ('192.166.145.8', 13915)]
        """
        log.startLogging(sys.stdout) # Start logging to stdout
        self.save_dir = save_dir
        self.listen_port = listen_port
        self.enable_DHT = enable_DHT
        self.tasks = {}
        self.btServer = BTServerFactories(self.listen_port)
        reactor.listenTCP(self.listen_port, self.btServer)
        if global_peers:
            self.global_peer_pool = set(global_peers)
        else:
            self.global_peer_pool = set() 

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

    def add_global_peers(self, peer_list):
        """
        @param peer_list list of tuples e.g. [('173.248.194.166', 12005),
            ('192.166.145.8', 13915)]
        """
        self.global_peer_pool.union(peers)
        for torrent_manager in self.tasks.itervalues():
            # TODO: Change to set_global_peers?  Why??
            torrent_manager.add_peers(list(self.global_peer_pool))

    def add_torrent(self, config):
        config.check()
        info_hash = config.info_hash
        if info_hash in self.tasks:
            log.msg('Torrent {0} already in download list'.format(config.metainfo.pretty_info_hash))
        else:
            btm = BTManager(self, config)
            if len(self.global_peer_pool) > 0:
                btm.add_peers(list(self.global_peer_pool))
            self.tasks[info_hash] = btm
            btm.startDownload()
            return info_hash 

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
            pretty_hash = bt_manager.metainfo.pretty_info_hash
            speed = bt_manager.get_speed()
            num_connections = bt_manager.get_num_connections()

            status[pretty_hash] = {
                "state": bt_manager.status,
                "speed_up": speed["up"],
                "speed_down": speed["down"],
                "num_seeds": num_connections["server"],
                "num_peers": num_connections["client"],
                }
            try:
                status["all"]["speed_up"] += status[pretty_hash]["speed_up"] 
                status["all"]["speed_down"] += status[pretty_hash]["speed_down"] 
            except KeyError:
                status["all"] = {
                    "speed_up": status[pretty_hash]["speed_up"], 
                    "speed_down": status[pretty_hash]["speed_down"]
                    }


        return status

    def start_reactor(self):
        reactor.run()
