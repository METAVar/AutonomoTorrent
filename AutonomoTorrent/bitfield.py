from array import array

counts = [chr(sum([(i >> j) & 1 for j in xrange(8)])) for i in xrange(256)]
counts = ''.join(counts)

class BitOp (object):
    def __contians__(self, idx):
        return self[idx]

    def __and__(self, bf):
        return BitfieldOperatorProxy(self, bf, lambda x,y: x&y)

    # def __or__(self, bf):
    #     return BitfieldOperatorProxy(self, bf, lambda x,y: x|y)

    # def __xor__(self, bf):
    #     return BitfieldOperatorProxy(self, bf, lambda x,y: x^y)


class Bitfield (BitOp):

    def __init__(self, length, bitstring=None):
        self.length = length

        rlen, extra = divmod(length, 8)
        if bitstring is None:
            self.numzeros = length
            if extra:
                self.bits = array('B', chr(0) * (rlen + 1))
            else:
                self.bits = array('B', chr(0) * rlen)
        else:
            if extra:
                if len(bitstring) != rlen + 1:
                    raise ValueError
                if (ord(bitstring[-1]) << extra) & 0xFF != 0:
                    raise ValueError
            else:
                if len(bitstring) != rlen:
                    raise ValueError
            c = counts
            self.numzeros = length - sum(array('B',
                                               bitstring.translate(counts)))

            self.bits = array('B', bitstring)

        self.__updateIndex(0)

    def any(self):
        return self.numzeros != self.length

    def allOne(self):
        return self.numzeros == 0

    def allZero(self):
        return self.numzeros == self.length

    def __updateIndex(self, start=0):
        if self.allOne():
            self.idxFirst1 = 0
        elif self.allZero() :
            self.idxFirst1 = None
        else:
            pos = start / 8
            for i in xrange(pos, len(self.bits)):
                c = self.bits[i]
                if c:
                    for _i in xrange(8):
                        if (128 >> _i) & c:
                            break
                    self.idxFirst1 = i * 8 + _i
                    break
            else:
                self.idxFirst1 = None
                
    def set1(self, index):
        pos = index >> 3
        mask = 128 >> (index & 7)
        if self.bits[pos] & mask:
            return
        self.bits[pos] |= mask
        self.numzeros -= 1
        assert self.numzeros >=0
        
        if self.idxFirst1 is None:
            self.idxFirst1 = index
        elif self.idxFirst1 > index:
            self.idxFirst1 = index

    def set0(self, index):
        pos = index >> 3
        mask = 128 >> (index & 7)
        if not self.bits[pos] & mask:
            return

        self.bits[pos] &= ~mask

        self.numzeros += 1
        assert self.numzeros <= self.length

        if index == self.idxFirst1:
            self.__updateIndex(self.idxFirst1)

    def __setitem__(self, index, val):
        if val == 0:
            self.set0(index)
        elif val == 1:
            self.set1(index)
        else:
            raise ValueError('val is 0 or 1')

    def __getitem__(self, index):
        bits = self.bits
        return bits[index >> 3] & 128 >> (index & 7)

    def __len__(self):
        return self.length

    def __repr__(self):
        return self.bits.__repr__()
    
    def __iter__(self):
        if self.any():
            pos = self.idxFirst1 / 8
            for i in xrange(pos, len(self.bits)):
                c = self.bits[i]
                if c:
                    for _i in xrange(8):
                        if (128 >> _i) & c:
                            yield i*8 + _i

    def tostring(self):
        if self.bits is None:
            rlen, extra = divmod(self.length, 8)
            r = chr(0xFF) * rlen
            if extra:
                r += chr((0xFF << (8 - extra)) & 0xFF)
            return r
        else:
            return self.bits.tostring()


class BitfieldOperatorProxy (object):
    def __init__(self, bf1, bf2, op):
        assert len(bf1) == len(bf2)
        self.bf1 = bf1
        self.bf2 = bf2
        self.op = op

    def __iter__(self):
        bf1 = self.bf1
        bf2 = self.bf2
        if self.any:
            pos = max(bf1.idxFirst1, bf2.idxFirst1) / 8
            bits1, bits2 = bf1.bits, bf2.bits
            for i in xrange(pos, len(bits1)):
                c = self.op(bits1[i], bits2[i])
                if c:
                    for _i in xrange(8):
                        if (128 >> _i) & c:
                            yield i*8 + _i

    def __len__(self):
        return len(self.bf1)
                            
    def __getitem__(self, idx):
        return self.op(self.bf1[idx], self.bf2[idx])

    def any(self):
        return self.op(self.bf1.any(), self.bf2.any())

    def allOne(self):
        return self.op(self.bf1.allOne(), self.bf2.allOne())

    def allZero(self):
        return self.op(self.bf1.allZero(), self.bf2.allZero())

if __name__ == '__main__':
    bt1 = Bitfield(64, '\xFF'*4 + '\xFF'*4)
    bt2 = Bitfield(64, '\x01\x01\x01\x01' + '\xFF'*4)

    # for idx in bt1&bt2:
    #     print idx
    
    print 0 in bt1, 0 in bt2, 0 in bt2|bt1, 7 in bt1&bt2

    for i in bt2&bt1:
        print i


