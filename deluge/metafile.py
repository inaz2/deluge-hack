# The contents of this file are subject to the BitTorrent Open Source License
# Version 1.1 (the License).  You may not copy or use this file, in either
# source code or executable form, except in compliance with the License.  You
# may obtain a copy of the License at http://www.bittorrent.com/license/.
#
# Software distributed under the License is distributed on an AS IS basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied.  See the License
# for the specific language governing rights and limitations under the
# License.

# Written by Bram Cohen

import os
import os.path
import sys
import time
from sha import sha

from deluge.bencode import bencode
from deluge.log import LOG as log

ignore = ['core', 'CVS', 'Thumbs.db', 'desktop.ini']

noncharacter_translate = {}
for i in xrange(0xD800, 0xE000):
    noncharacter_translate[i] = ord('-')
for i in xrange(0xFDD0, 0xFDF0):
    noncharacter_translate[i] = ord('-')
for i in (0xFFFE, 0xFFFF):
    noncharacter_translate[i] = ord('-')

def gmtime():
    return time.mktime(time.gmtime())

def get_filesystem_encoding():
    default_encoding = 'utf8'

    if os.path.supports_unicode_filenames:
        encoding = None
    else:
        try:
            encoding = sys.getfilesystemencoding()
        except AttributeError:
            log.debug("This version of Python cannot detect filesystem encoding.")


        if encoding is None:
            encoding = default_encoding
            log.debug("Python failed to detect filesystem encoding. "
                      "Assuming '%s' instead.", default_encoding)
        else:
            try:
                'a1'.decode(encoding)
            except:
                log.debug("Filesystem encoding '%s' is not supported. Using '%s' instead.",
                          encoding, default_encoding)
                encoding = default_encoding

    return encoding

def decode_from_filesystem(path):
    encoding = get_filesystem_encoding()
    if encoding == None:
        assert isinstance(path, unicode), "Path should be unicode not %s" % type(path)
        decoded_path = path
    else:
        assert isinstance(path, str), "Path should be str not %s" % type(path)
        decoded_path = path.decode(encoding)

    return decoded_path

def dummy(v):
    pass
    
def make_meta_file(path, url, piece_len_exp, progress=dummy,
                   title=None, comment=None, safe=None, content_type=None,
                   target=None, url_list=None, name=None):
    data = {'announce': url.strip(), 'creation date': int(gmtime())}
    piece_length = 2 ** piece_len_exp
    a, b = os.path.split(path)
    if not target:
        if b == '':
            f = a + '.torrent'
        else:
            f = os.path.join(a, b + '.torrent')
    else:
        f = target
    info = makeinfo(path, piece_length, progress, name, content_type)

    #check_info(info)
    h = file(f, 'wb')

    data['info'] = info
    if title:
        data['title'] = title
    if comment:
        data['comment'] = comment
    if safe:
        data['safe'] = safe
    if url_list:
        data['url-list'] = url_list
    h.write(bencode(data))
    h.close()

def calcsize(path):
    total = 0
    for s in subfiles(os.path.abspath(path)):
        total += os.path.getsize(s[1])
    return total

def makeinfo(path, piece_length, progress, name = None,
             content_type = None):  # HEREDAVE. If path is directory,
                                    # how do we assign content type?
    def to_utf8(name):
        if isinstance(name, unicode):
            u = name
        else:
            try:
                u = decode_from_filesystem(name)
            except Exception, e:
                s = str_exc(e)
                raise Exception('Could not convert file/directory name %r to '
                                  'Unicode (%s). Either the assumed filesystem '
                                  'encoding "%s" is wrong or the filename contains '
                                  'illegal bytes.') % (name, s, get_filesystem_encoding())

        if u.translate(noncharacter_translate) != u:
            raise Exception('File/directory name "%s" contains reserved '
                              'unicode values that do not correspond to '
                              'characters.' % name)
        return u.encode('utf-8')
    path = os.path.abspath(path)
    if os.path.isdir(path):
        subs = subfiles(path)
        subs.sort()
        pieces = []
        sh = sha()
        done = 0
        fs = []
        totalsize = 0.0
        totalhashed = 0
        for p, f in subs:
            totalsize += os.path.getsize(f)

        for p, f in subs:
            pos = 0
            size = os.path.getsize(f)
            p2 = [to_utf8(n) for n in p]
            if content_type:
                fs.append({'length': size, 'path': p2,
                           'content_type' : content_type}) # HEREDAVE. bad for batch!
            else:
                fs.append({'length': size, 'path': p2})
            h = file(f, 'rb')
            while pos < size:
                a = min(size - pos, piece_length - done)
                sh.update(h.read(a))
                done += a
                pos += a
                totalhashed += a

                if done == piece_length:
                    pieces.append(sh.digest())
                    done = 0
                    sh = sha()
                progress(a)
            h.close()
        if done > 0:
            pieces.append(sh.digest())

        if name is not None:
            assert isinstance(name, unicode)
            name = to_utf8(name)
        else:
            name = to_utf8(os.path.split(path)[1])

        return {'pieces': ''.join(pieces),
            'piece length': piece_length, 'files': fs,
            'name': name}
    else:
        size = os.path.getsize(path)
        pieces = []
        p = 0
        h = file(path, 'rb')
        while p < size:
            x = h.read(min(piece_length, size - p))
            if flag.isSet():
                return
            pieces.append(sha(x).digest())
            p += piece_length
            if p > size:
                p = size
            progress(min(piece_length, size - p))
        h.close()
        if content_type is not None:
            return {'pieces': ''.join(pieces),
                'piece length': piece_length, 'length': size,
                'name': to_utf8(os.path.split(path)[1]),
                'content_type' : content_type }
        return {'pieces': ''.join(pieces),
            'piece length': piece_length, 'length': size,
            'name': to_utf8(os.path.split(path)[1])}

def subfiles(d):
    r = []
    stack = [([], d)]
    while stack:
        p, n = stack.pop()
        if os.path.isdir(n):
            for s in os.listdir(n):
                if s not in ignore and not s.startswith('.'):
                    stack.append((p + [s], os.path.join(n, s)))
        else:
            r.append((p, n))
    return r