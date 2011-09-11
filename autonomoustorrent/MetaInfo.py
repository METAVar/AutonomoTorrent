# 
# -*-encoding:gb2312-*-

import hashlib
import os

from bencode import bencode, bdecode

class BTMetaInfo:
    '''
    对应于torrent文件
    '''
    
    encoding = 'utf-8'

    def __init__(self, btfile):
        ct = open(btfile, 'rb').read()
        metainfo = bdecode(ct)
        self.metainfo = metainfo

        self.announce_list = [metainfo['announce']]
        if 'announce-list' in metainfo:
            self.announce_list += reduce(lambda x,y: x+y, metainfo['announce-list'])

        if 'encoding' in metainfo:
            self.encoding = metainfo['encoding']
            
        info = metainfo['info']
        self.info_hash = hashlib.sha1(bencode(info)).digest()

        self.piece_length = info['piece length']

        hashes = info['pieces']
        self.pieces_hash = [hashes[i:i+20] for i in range(0, len(hashes), 20)]
        self.pieces_size = len(self.pieces_hash)
        
        self.files = []

        self.topDir = '.'
        name = info['name'].decode(self.encoding)
        if 'files' in info:
            cur_size = 0
            for fd in info['files']:
                _d = fd.copy()
                _path = [name] + [p.decode(self.encoding) for p in _d['path']]
                _path = os.path.join(*_path)
                _d['path'] = _path

                _start = cur_size
                _stop = cur_size + _d['length']
                cur_size = _stop

                _d['pos_range'] = _start, _stop

                self.files.append(_d)

                # print _d['piece'], _d['offset']
                
            self.total_length = cur_size                
            # print divmod(self.total_length, self.piece_length)
            # print self.pieces_size
            self.topDir = name
                
        else:
            _d = {}
            _d['path'] = name
            _d['length'] = info['length']
            self.files.append(_d)
            self.total_length = info['length']

        last_piece_length = self.total_length % self.piece_length
        if last_piece_length == 0 :
            last_piece_length = self.piece_length
        self.last_piece_length = last_piece_length

    def __getitem__(self, key):
        if type(key) is type(0):
            return self.files[key]
        return self.metainfo[key]

    def __iter__(self):
        for f in self.files:
            yield f


if __name__ == '__main__':
    print BTMetaInfo('test.torrent')
