"""urllib.request for a wasmcart cart: the API, without a network.

A cart has no sockets. Every function here therefore raises URLError, which
is the same exception a caller already handles for a machine that is offline,
and the wasmcart WebSocket/DataChannel ABI is not exposed to Python yet.

The point is that `import urllib.request` succeeds. Games put optional online
features (news, high-score upload, version check) behind a try/except around
the *call* and import the module at the top of the file; with no module at
all they die on the import, which no try/except around the call can catch.
"""

from urllib.error import ContentTooShortError, HTTPError, URLError
from urllib.parse import (quote, quote_plus, unquote, unquote_plus, urlencode,
                          urljoin, urlparse, urlsplit, urlunparse)

__all__ = ['Request', 'urlopen', 'urlretrieve', 'urlcleanup', 'build_opener',
           'install_opener', 'pathname2url', 'url2pathname',
           'HTTPError', 'URLError', 'ContentTooShortError']

_NO_NETWORK = 'no network in a wasmcart cart'


class Request:
    """Carries the same fields as CPython's, so building one never fails.

    A request that is never sent is harmless; only urlopen() refuses.
    """

    def __init__(self, url, data=None, headers=None, origin_req_host=None,
                 unverifiable=False, method=None):
        self.full_url = url
        self.data = data
        self.headers = dict(headers or {})
        self.unredirected_hdrs = {}
        self.origin_req_host = origin_req_host
        self.unverifiable = unverifiable
        self.method = method
        parts = urlsplit(url)
        self.type = parts.scheme
        self.host = parts.netloc
        self.selector = parts.path

    def get_full_url(self):
        return self.full_url

    def get_method(self):
        if self.method is not None:
            return self.method
        return 'POST' if self.data is not None else 'GET'

    def add_header(self, key, val):
        self.headers[key.capitalize()] = val

    def add_unredirected_header(self, key, val):
        self.unredirected_hdrs[key.capitalize()] = val

    def has_header(self, header_name):
        name = header_name.capitalize()
        return name in self.headers or name in self.unredirected_hdrs

    def get_header(self, header_name, default=None):
        name = header_name.capitalize()
        return self.headers.get(name, self.unredirected_hdrs.get(name, default))

    def header_items(self):
        return list(self.headers.items()) + list(self.unredirected_hdrs.items())


def urlopen(url, data=None, timeout=None, **kwargs):
    raise URLError(_NO_NETWORK)


def urlretrieve(url, filename=None, reporthook=None, data=None):
    raise URLError(_NO_NETWORK)


def urlcleanup():
    return None


class OpenerDirector:
    def open(self, fullurl, data=None, timeout=None):
        raise URLError(_NO_NETWORK)

    def add_handler(self, handler):
        return None


def build_opener(*handlers):
    return OpenerDirector()


def install_opener(opener):
    return None


def pathname2url(pathname):
    return quote(pathname)


def url2pathname(pathname):
    return unquote(pathname)
