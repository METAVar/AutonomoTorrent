"""Tests cases for BTApp which is the main control point for using
AutonomoTorrent
"""
import unittest

from twisted.internet import reactor

from autonomotorrent.BTApp import BTApp, BTConfig

class testBTApp(unittest.TestCase):
    """Tests the BTApp which is the main control point for using AutonomoTorrent
    """
    def setUp(self):
        self.bt_app = BTApp() 

    def test_using_file(self):
        """Tests the BT App using a known good torrent meta file from disk.
        """
        config = BTConfig(torrent_path="tests/unit/damn_small_linux.torrent")
        self.bt_app.add_torrent(config)
        reactor.callLater(5, reactor.stop)
        self.bt_app.start_reactor()

if __name__ == "__main__":
    unittest.main()
