# -*- coding: UTF-8 -*-
"""Common utility functions.

"""
from itertools import cycle, permutations, product
from string import printable, punctuation

from .compat import b
from .constants import PYTHON3


__all__ = __features__ = ["bruteforce", "bruteforce_mask", "strings",
                          "strings_from_file", "xor", "xor_file"]


MASKS = {
    'a': printable,
    'b': "".join(chr(i) for i in range(256)),
    'd': "0123456789",
    'h': "0123456789abcdef",
    'H': "0123456789ABCDEF",
    'l': "abcdefghijklmnopqrstuvwxyz",
    's': " " + punctuation,
    'u': "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
}


def bruteforce(maxlen, alphabet=tuple(map(chr, range(256))), minlen=1,
               repeat=True):
    """
    Generator for bruteforcing according to minimum and maximum lengths and an
     alphabet.
    
    :param maxlen:   maximum bruteforce entry length
    :param alphabet: bruteforce alphabet to be used
    :param minlen:   minimum bruteforce entry length (optional)
    :param repeat:   whether alphabet characters can be repeated or not
    :yield:          bruteforce entry
    """
    for i in range(minlen, maxlen + 1):
        if repeat:
            for c in product(alphabet, repeat=i):
                yield c if isinstance(c[0], int) else ''.join(c)
        else:
            for c in permutations(alphabet, i):
                yield c if isinstance(c[0], int) else ''.join(c)


def bruteforce_mask(mask, charsets=None):
    """
    Generator for bruteforcing according to a given mask (similar to this used
     in hashcat).
     
    :param mask:     bruteforce mask
    :param charsets: custom alphabets for use with the mask
    """
    iterables, charset = [], False
    masks = {k: v for k, v in MASKS.items()}
    masks.update(charsets or {})
    for c in mask:
        if c == "?":
            charset = True
            continue
        if charset:
            iterables.append(masks[c])
            charset = False
            continue
        iterables.append(c)
    for c in product(*iterables):
        yield c if isinstance(c[0], int) else ''.join(c)


def strings(data, minlen=4, alphabet=printable):
    """
    Generator yielding strings according to a charset and a minimal length from
     a given string buffer.

    :param data:     input data
    :param minlen:   minimal length of strings to be considered
    :param alphabet: valid charset for the strings
    """
    result = ""
    for c in b(data):
        if c in b(alphabet):
            result += chr(c) if PYTHON3 else c
            continue
        if len(result) >= minlen:
            yield result
        result = ""
    if len(result) >= minlen:
        yield result


def strings_from_file(filename, minlen=4, alphabet=printable, offset=0):
    """
    Generator yielding strings according to a charset and a minimal length from
     a given file.
    
    :param filename: input file
    :param minlen:   minimal length of strings to be considered
    :param alphabet: valid charset for the strings
    :param offset:   start offset in the input file
    """
    with open(filename, 'rb') as f:
        f.seek(offset)
        result = ""
        while True:
            data = f.read(max(1024, 2 * minlen))
            if not data:
                break
            for c in data:
                if c in b(alphabet):
                    result += chr(c) if PYTHON3 else c
                    continue
                if len(result) >= minlen:
                    yield result
                result = ""
        if len(result) >= minlen:
            yield result


def xor(str1, str2, offset=0):
    """
    Function for XORing two strings of different length. Either the first of the
     second string can be longer than the other.

    :param str1:   first string, with length L1
    :param str2:   second string, with length L2
    :param offset: ASCII offset to be applied on each resulting character
    """
    convert = isinstance(str1[0], int) or isinstance(str2[0], int)
    r = b("") if convert else ""
    for c1, c2 in zip(cycle(str1) if len(str1) < len(str2) else str1,
                      cycle(str2) if len(str2) < len(str1) else str2):
        c1 = c1 if isinstance(c1, int) else ord(c1)
        c2 = c2 if isinstance(c2, int) else ord(c2)
        c = chr(((c1 ^ c2) + offset) % 256)
        r += b(c) if convert else c
    return r


def xor_file(filename, key, offset=0):
    """
    Function for XORing a file with a given key.

    :param filename: input file
    :param key:      XOR key
    :param offset:   start offset in the input file
    """
    with open(filename, 'rb+') as f:
        cursor, l = offset, len(key)
        f.seek(cursor)
        while True:
            data = f.read(l)
            if not data:
                break
            f.seek(cursor)
            f.write(xor(data, b(key[:len(data)])))
            cursor += l
