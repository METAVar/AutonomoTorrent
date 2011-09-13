"""
"""
import os
from twisted.python import log
from autonomotorrent.BTApp import BTApp, BTConfig

def main(opt, btfiles):
    app = BTApp(save_dir=opt.save_dir, 
                listen_port=opt.listen_port, 
                enable_DHT=opt.enable_dht)
    for torrent_file in btfiles:
        try:
            log.msg('Adding: {0}'.format(torrent_file))
            config = BTConfig(torrent_file)
            config.downloadList = None
            app.add_torrent(config)

        except:
            log.err()
            log.err("Failed to add {0}".format(torrent_file))

    app.start_reactor()

def console():
    from optparse import OptionParser

    usage = 'usage: %prog [options] torrent1 torrent2 ...'
    parser = OptionParser(usage=usage)
    parser.add_option('-o', '--output_dir', action='store', type='string',
                      dest='save_dir', default='.', 
                      help='save download file to which directory')

    parser.add_option('-l', '--listen-port', action='store', type='int',
                     dest='listen_port', default=6881, 
                     help='the listen port')

    parser.add_option("-d", "--enable_dht", action="store_true",
                    dest="enable_dht", help="enable the DHT extension") 

    options, args = parser.parse_args()
    if(len(args) > 0):
        main(options, args)
    else:
        print "Error: No torrent files given."
        print usage

if __name__ == '__main__':
    console()
