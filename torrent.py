#
# -*-encoding:gb2312-*-

import sys
import os

from MetaInfo import BTMetaInfo
from FileManager import BTFiles

def hashTest(btfilepath) :
    btf = BTMetaInfo(btfilepath)
    bfs = BTFiles(btf, '.', [0])

    print bfs
    
    goodPiece = 0
    for i in range(len(bfs)):
        res = bfs[i]
        if res :
            if len(res) == 1:
                beg, dat = res[0]
                if bfs.doHashTest(i, dat):
                    goodPiece += 1
                else:
                    #print 'hash test error:', i
                    pass
            else:
                #print 'fragment', i
                pass
        else:
            #print 'not download', i
            pass

    print 'donwload piece number :', goodPiece

    bfHave, bfNeed = bfs.getBitfield()

    print bfHave


if __name__ == '__main__' :
    btfiles = sys.argv[1:]

    for path in btfiles :
        btf = BTMetaInfo(path)
        print '-'*20
        print path
        for i, f in enumerate(btf.files) :
            size = f['length']
            print u'[{}] [{:,}bytes] {}'.format(i, size, f['path'])

        print '-'*60
        print 'totoal pieces:', btf.pieces_size

        hashTest(path)

