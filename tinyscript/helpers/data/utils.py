# -*- coding: UTF-8 -*-
"""Common utility functions for data.

"""
import re
from ast import literal_eval as litev
from bitstring import BitArray as BaseBitArray
from random import randint

from .types import *


__all__ = __features__ = ["BitArray", "pad", "unpad"]


PAD = ["ansic9.23", "incremental", "iso7816-4", "pkcs5", "pkcs7", "w3c"]


class BitArray(BaseBitArray):
    __doc__ = """
    Small improvement to the original bitstring.BitArray class.
    
    It allows to set the number of bits per group (by default, 8, for
     considering bytes).
    
    """ + BaseBitArray.__doc__
    
    def __new__(cls, auto=None, length=None, offset=None, nbits=8, **kwargs):
        if auto:
            if not auto.startswith("0b"):
                auto = "0b" + auto
            auto = "0b" + pad(auto[2:], "0", nbits)
        c = super(BitArray, cls).__new__(cls, auto, length, offset,
                                                 **kwargs)
        c._nbits = nbits
        c.original = True
        return c
    
    @property
    def nbits(self):
        return self._nbits
    
    @nbits.setter
    def nbits(self, n):
        ob = self.bin
        nb = ""
        for i in range(0, len(ob), self._nbits):
            group = pad(ob[i:i+self._nbits], ">0", n)[-n:]
            if int(ob[i:i+self._nbits], 2) != int(group, 2):
                self.original = False
            nb += group
        self.bin = nb
        self._nbits = n


def pad(string, padding=None, blocksize=8, raw=False):
    """
    Custom string padding function relying on Tinyscript's data type check
     functions and a few implemented padding algorithms.
    
    NB: Default algorithm is the zero padding.
    
    :param padding:   padding characters or padding algorithm
    :param blocksize: block size to be considered for padding
    :param raw:       whether the input string must be considered as a normal
                       strint (it disables the check for hexstring)
    """
    s, bs = string, blocksize
    isb, ish = is_bin(s) and not raw, is_hex(s) and not raw
    if (padding in PAD and isb) or (padding == "bit" and not isb):
        raise ValueError("Incompatible padding algorithm")
    if blocksize <= 0:
        raise ValueError("Block size must be a positive integer")
    to_char = lambda x: [chr(x), "{:0>2}".format(hex(x)[2:])][ish]
    lp = [1, 2][ish]
    bn = bs * lp
    p = int((bn - (len(s) % bn) / lp) % bs)
    zc = ["\x00", "00"][ish]
    nc = to_char(p)
    if padding == "ansic9.23":
        return s + (p - 1) * zc + int(p > 0) * nc
    elif padding == "bit":
        p = bs - (len(s) % bs) % bs
        return s + "1" + (p - 1) * "0"
    elif padding == "incremental":
        return s + "".join(map(to_char, range(1, p + 1)))
    elif padding == "iso7816-4":
        return s + ["\x80", "80"][ish] + (p - 1) * zc
    elif padding in ["pkcs5", "pkcs7"]:
        return s + p * nc
    elif padding == "w3c":
        rand = "".join(to_char(randint(0, 255)) for i in range(p - 1))
        return s + rand + int(p > 0) * nc
    else:
        padding = padding or ("0" if isb else "00" if ish else "\x00")
        if re.match(r"[<>]", padding):
            left = padding[0] == ">"
            padding = padding[1:]
        else:
            left = False
        if len(s) % len(padding) != 0:
            raise ValueError("Bad padding character(s)")
        lp = len(padding)
        bn = bs * lp
        p = int((bn - (len(s) % bn) / lp) % bs)
        return ["", p * padding][left] + s + [p * padding, ""][left]


def unpad(string, padding=None, blocksize=8, raw=False):
    """
    Custom string unpadding function relying on Tinyscript's data type check
     functions and a few implemented padding algorithms.
    
    NB: Default algorithm is the zero padding.
    
    :param padding:   padding characters or padding algorithm
    :param blocksize: block size to be considered for padding
    :param raw:       whether the input string must be considered as a normal
                       strint (it disables the check for hexstring)
    """
    s, bs = string, blocksize
    isb, ish = is_bin(s) and not raw, is_hex(s) and not raw
    if (padding in PAD and isb) or (padding == "bit" and not isb):
        raise ValueError("Incompatible padding algorithm")
    if blocksize <= 0:
        raise ValueError("Block size must be a positive integer")
    to_char = lambda x: [chr(x), "{:0>2}".format(hex(x)[2:])][ish]
    lastb = [litev("0x" + (s[i:i+2 or len(s)] or "0")) for i in \
             range(-bs*2, 0, 2)] if ish else list(map(ord, s[-bs:]))
    n = lastb[-1]
    lp = [1, 2][ish]
    if padding == "ansic9.23":
        if n <= bs and lastb[-n:-1] == [0] * (n - 1):
            return s[:-n*lp]
    elif padding == "bit":
        l = len(s)
        s = s.rstrip("0")
        if len(s) < l:
            return s[:-1]
    elif padding == "incremental":
        if n <= bs and lastb[-n:-1] == list(range(1, n)):
            return s[:-n*lp]
    elif padding == "iso7816-4":
        n = 0
        while lastb[-1] == 0:
            lastb.pop()
            n += 1
        if n < bs and lastb[-1] == 128:
            lastb.pop()
            n += 1
            return s[:-n*lp]
    elif padding in ["pkcs5", "pkcs7"]:
        if n <= bs and lastb[-n:-1] == (n - 1) * [n]:
            return s[:-n*lp]
    elif padding == "w3c":
        n = lastb[-1]
        if n <= bs:
            return s[:-n*lp or len(s)]
    else:
        return s.rstrip("0") if isb else pad(s.rstrip("0"), "0", 2) \
               if ish else s.rstrip("\x00")
    return s