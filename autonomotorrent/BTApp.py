"""
"""
import sys

try: 
    if sys.version_info.major !=2 and sys.version_info.minor < 6:
        print 'require python 2.6 or newer'
        exit()
except AttributeError:
    if sys.version_info[0] != 2 and sys.version_info[1] < 6:
        print 'require python 2.6 or newer'
        exit()

try:
    import twisted
except ImportError as err:
    print 'require twisted 10.2.0 or newer'
    exit()

if sys.platform == 'win32':
    try:
        from twisted.internet import iocpreactor
        iocpreactor.install()
    except Exception as err:
        print err
else:
    try:
        from twisted.internet import epollreactor
        epollreactor.install()
    except:
        pass

from twisted.python import log
from twisted.internet import reactor
from autonomotorrent.BTManager import BTManager
from autonomotorrent.factory import BTServerFactories
from autonomotorrent.MetaInfo import BTMetaInfo
from autonomotorrent.DHTProtocol import DHTProtocol
class BTConfig(object):
    listenPort = 6881
    maxDownloadSpeed = 1024
    maxUploadSpeed = 1024

    def __init__(self, torrentPath) :
        self.torrentPath = torrentPath
        self.metainfo = BTMetaInfo(torrentPath)
        self.info_hash = self.metainfo.info_hash
        self.downloadList = None
        self.saveDir = '.'
        self.rootDir = self.metainfo.topDir

    def check(self) :
        if self.downloadList is None:
            self.downloadList = range(len(self.metainfo.files))
        for i in self.downloadList :
            f = self.metainfo.files[i]
            size = f['length']
            name = f['path']
            log.msg("File: {0} Size: {1}".format(name, size)) # TODO: Do we really need this?

        self.rootDir = os.path.join(self.saveDir, self.rootDir)
            
class BTApp:
    def __init__(self, enable_DHT=False):
        self.enable_DHT = enable_DHT
        log.startLogging(sys.stdout) # Start logging to stdout
        self.tasks = {}
        self.listenPort = BTConfig.listenPort
        self.btServer = BTServerFactories(self.listenPort)
        reactor.listenTCP(BTConfig.listenPort, self.btServer)
        if enable_DHT:
            self.dht = DHTProtocol()
            reactor.listenUDP(self.listenPort, self.dht)

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

    def start_reactor(self):
        reactor.run()
