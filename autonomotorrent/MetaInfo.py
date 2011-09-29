# 
# -*-encoding:gb2312-*-

import sys
import zlib

from os.path import getsize, split, join, abspath, isdir, normpath
from copy import copy
from string import strip
from time import time
try:
    from sys import getfilesystemencoding
    ENCODING = getfilesystemencoding()
except:
    from sys import getdefaultencoding
    ENCODING = getdefaultencoding()

### original imports
import hashlib
import os

from bencode import bencode, bdecode

from twisted.python import log

class BTMetaInfo:
    """ 
    """ 
    encoding = 'utf-8'
    def __init__(self, path=None, meta_info=None):
        if path:
            ct = open(path, 'rb').read()
            metainfo = bdecode(ct)
        elif meta_info:
            metainfo = meta_info
        else:
            raise Exception("Must pass either a BT meta file path or the " +\
                "meta  info itself!")
        self.metainfo = metainfo

        if 'announce' in metainfo:
            self.announce_list = [metainfo['announce']]
            if 'announce-list' in metainfo:
                self.announce_list += reduce(lambda x,y: x+y, metainfo['announce-list'])
        else: # Trackerless torrent?
            self.announce_list = []

        if 'encoding' in metainfo:
            self.encoding = metainfo['encoding']
            
        info = metainfo['info']
        temp = hashlib.sha1(bencode(info))
        self.info_hash =  temp.digest()
        self.pretty_info_hash =  temp.hexdigest()

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
                
            self.total_length = cur_size                
            self.topDir = name
                
        else:
            _d = {}
            _d['path'] = name
            _d['length'] = info['length']
            _d['pos_range'] = 0, info['length'] # TODO: Is this right?
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

def _calcsize(file_to_torrent):
    if not isdir(file_to_torrent):
        return getsize(file_to_torrent)
    total = 0
    for s in _subfiles(abspath(file_to_torrent)):
        total += getsize(s[1])
    return total

def calculate_piece_length(file_to_torrent, piece_len_exp=None):
    """Calculates the piece length according to the piece length exponent.  If
    one is not provided, it calculates it for you.
    """
    if not piece_len_exp:  # then calculate it automatically
        size = _calcsize(file_to_torrent)
        if size <= 1*1024*1024:         # <= 1M 
            # If this small, we have to make sure it at least has enough pieces
            # to properly work with most clients (~1000) 
            # NOTE: Using BT with pieces this small is inefficient.
            return int(size/1000)
        elif size > 2*1024*1024*1024:   # > 2 gig =
            piece_len_exp = 20          #   1 meg pieces
        elif size > 512*1024*1024:      # > 512M =
            piece_len_exp = 19          #   512K pieces
        elif size > 64*1024*1024:       # > 64M =
            piece_len_exp = 18          #   256K pieces
        elif size > 16*1024*1024:       # > 16M =
            piece_len_exp = 17          #   128K pieces
        elif size > 4*1024*1024:        # > 4M =
            piece_len_exp = 16          #   64K pieces
        else:                           # < 4M =
            piece_len_exp = 15          #   32K pieces
    piece_length = 2 ** piece_len_exp
    return piece_length

def _get_fs_encoding():
    """Attempts to figure out and return the local filesystem encoding.
    """
    fs_encoding = ENCODING
    if not fs_encoding:
        fs_encoding = 'ascii'
    return fs_encoding

def save_meta_info(path, meta_info):
    """Bencodes and saves the meta_info dictioary to the path provided.

    Warning: This does not verify the meta_info for correctness.
    """
    # TODO: Check/verify meta_info?
    target_file = open(path, 'wb')
    target_file.write(bencode(meta_info))
    target_file.close()

def create_meta_info(file_to_torrent, url, target=None, save_to_disk=True, 
    comment=None, created_by=None, announce_list=None, httpseeds=None, 
    piece_len_exp=None, get_hash=None):        
    """Creates and returns the meta info dictionary for the file_to_torrent
    passed.

    @param comment string 
    @param created_by string
    @param announce_list list of lists with each list within the list being a
        tier and each string in that list being an announce url (e.g.
        [["sometracker.org:80/announce","trckr.net:80"],["t.com:80/announce"]]
    @param httpseeds list of urls (strings)
    """
    info = make_info(file_to_torrent, piece_len_exp=piece_len_exp, get_hash=get_hash)
    #check_info(info) # FIXME: from BitTornado.BT1.btformats import check_info
    data = {'info': info, 'announce': strip(url), 'creation date': long(time())}

    if comment: 
        data['comment'] = comment
    if created_by:
        data['created by'] = created_by
    if announce_list: 
        data['announce-list'] = announce_list
    if httpseeds:
        data['httpseeds'] = httpseeds

    if save_to_disk:
        if target:
            target_path = join(target, split(normpath(file_to_torrent))[1] + '.torrent')
        else:
            a, b = split(file_to_torrent)
            if b == '':
                target_path = a + '.torrent'
            else:
                target_path = join(a, b + '.torrent')
        save_meta_info(target_path, data)

    return data

def _uniconvertl(l, e):
    r = []
    try:
        for s in l:
            r.append(_uniconvert(s, e))
    except UnicodeError:
        raise UnicodeError('bad filename: '+join(l))
    return r
def _uniconvert(s, e):
    try:
        s = unicode(s,e)
    except UnicodeError:
        raise UnicodeError('bad filename: '+s)
    return s.encode('utf-8')
def make_info(file_to_torrent, piece_len_exp=None, get_hash=None):
    """Creates and returns the meta info dictionary.

    @param piece_len_exp integer 2^piece_len_exp used to calculate the piece
    length.  If piece_len_exp is not given, it (and thus the piece length) will
    be calculated for you.
    """
    piece_length = calculate_piece_length(file_to_torrent, piece_len_exp) 
    if get_hash is None:
        get_hash = {}
    
    if not 'md5' in get_hash:
        get_hash['md5'] = False
    if not 'crc32' in get_hash:
        get_hash['crc32'] = False
    if not 'sha1' in get_hash:
        get_hash['sha1'] = False

    fs_encoding = _get_fs_encoding()
    file_to_torrent = abspath(file_to_torrent)
    pieces = []
    if isdir(file_to_torrent): #Multiple files
        subs = _subfiles(file_to_torrent)
        subs.sort()
        sh = hashlib.sha1()
        done = 0
        fs = []
        totalsize = 0.0
        totalhashed = 0
        for p, f in subs:
            totalsize += getsize(f)

        for p, f in subs:
            pos = 0
            size = getsize(f)
            h = open(f, 'rb')

            if get_hash['md5']:
                hash_md5 = hashlib.md5()
            if get_hash['sha1']:
                hash_sha1 = hashlib.sha1()
            if get_hash['crc32']:
                hash_crc32 = zlib.crc32('')
            
            while pos < size:
                a = min(size-pos, piece_length-done)
                readpiece = h.read(a)
                sh.update(readpiece)
                if get_hash['md5']:                
                    hash_md5.update(readpiece)
                if get_hash['crc32']:                
                    hash_crc32 = zlib.crc32(readpiece, hash_crc32)
                if get_hash['sha1']:                
                    hash_sha1.update(readpiece)
                
                done += a
                pos += a
                totalhashed += a
                
                if done == piece_length:
                    pieces.append(sh.digest())
                    done = 0
                    sh = hashlib.sha1()
                    
            newdict = {'length': size,
                       'path': _uniconvertl(p, fs_encoding) }
            if get_hash['md5']:
                newdict['md5sum'] = hash_md5.hexdigest()
            if get_hash['crc32']:
                newdict['crc32'] = "%08X" % hash_crc32
            if get_hash['sha1']:
                newdict['sha1'] = hash_sha1.digest()
            fs.append(newdict)
            h.close()
        if done > 0:
            pieces.append(sh.digest())
        return {'pieces': ''.join(pieces), 
                'piece length': piece_length,
                'files': fs, 
                'name': _uniconvert(split(file_to_torrent)[1], fs_encoding) 
               }
    else: # Single file
        size = getsize(file_to_torrent)
        p = 0
        h = open(file_to_torrent, 'rb')
        
        if get_hash['md5']:
            hash_md5 = hashlib.md5()
        if get_hash['crc32']:
            hash_crc32 = zlib.crc32('')
        if get_hash['sha1']:
            hash_sha1 = hashlib.sha1()
        
        while p < size:
            x = h.read(min(piece_length, size - p))
            if get_hash['md5']:
                # Update MD5
                hash_md5.update(x)
            if get_hash['crc32']:
                # Update CRC32
                hash_crc32 = zlib.crc32(x, hash_crc32)
            if get_hash['sha1']:
                # Update SHA-1
                hash_sha1.update(x)
                
            pieces.append(hashlib.sha1(x).digest())
            p += piece_length
            if p > size:
                p = size
        h.close()
        newdict = {'pieces': ''.join(pieces), 
                   'piece length': piece_length,
                   'length': size, 
                   'name': _uniconvert(split(file_to_torrent)[1], fs_encoding),
                  }
        if get_hash['md5']:
            newdict['md5sum'] = hash_md5.hexdigest()
        if get_hash['crc32']:
            newdict['crc32'] = "%08X" % hash_crc32
        if get_hash['sha1']:
            newdict['sha1'] = hash_sha1.digest()
                   
        return newdict
def _subfiles(d):
    r = []
    stack = [([], d)]
    while stack:
        p, n = stack.pop()
        if isdir(n):
            for s in os.listdir(n):
                if s[:1] != '.':
                    stack.append((copy.copy(p) + [s], join(n, s)))
        else:
            r.append((p, n))
    return r
