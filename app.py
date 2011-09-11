"""
"""
import sys

if sys.version_info.major !=2 and sys.version_info.minor<6:
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

import os
from twisted.python import log
from twisted.internet import reactor
from AutonomoTorrent.BTManager import BTManager
from AutonomoTorrent.factory import BTServerFactories
from AutonomoTorrent.MetaInfo import BTMetaInfo
from AutonomoTorrent.DHTProtocol import DHTProtocol

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
        log.msg('-' * 20)
        for i in self.downloadList :
            f = self.metainfo.files[i]
            size = f['length']
            name = f['path']
            log.msg("{0} {1}".format(size, name))

        self.rootDir = os.path.join(self.saveDir, self.rootDir)
        log.msg('root dir: {0}'.format(self.rootDir))
            
class BTApp:

    def __init__(self):
        log.startLogging(sys.stdout)
        log.msg("Started logging to stdout.")
        self.tasks = {}
        self.listenPort = BTConfig.listenPort
        self.btServer = BTServerFactories(self.listenPort)
        reactor.listenTCP(BTConfig.listenPort, self.btServer)
        self.dht = DHTProtocol()
        reactor.listenUDP(self.listenPort, self.dht)

    def add_torrent(self, config):
        config.check()
        hs = config.info_hash
        if hs in self.tasks:
            log.msg('{0} is already in download task list'.format(hs))
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


def main(opt, btfiles):
    app = BTApp()
    for torrent_file in btfiles:
        log.msg('Adding: {0}'.format(torrent_file))
        config = BTConfig(torrent_file)
        config.downloadList = None
        config.saveDir = opt.saveDir
        config.listenPort = opt.listenPort
        app.add_torrent(config)

    app.start_reactor()


if __name__ == '__main__':
    from optparse import OptionParser

    usage = 'usage: %prog [options] torrent1 torrent2 ...'
    parser = OptionParser(usage=usage)
    parser.add_option('-o', '--output_dir', action='store', type='string',
                      dest='saveDir', default='.', metavar='SaveDir', 
                      help='save download file to which directory')

    parser.add_option('-p', '--port', action='store', type='int',
                     dest='listenPort', default=6881, metavar='LISTEN-PORT',
                     help='the listen port')

    options, args = parser.parse_args()
    if(len(args) > 0):
        main(options, args)
    else:
        print "Error: No torrent files given."
        print usage
