"""urllib.error for a wasmcart cart.

The real exception hierarchy, minus the http.client dependency that
CPython's version carries for HTTPError's response behaviour. Callers
catch these by name, so the names and the inheritance are what matter.
"""

__all__ = ['URLError', 'HTTPError', 'ContentTooShortError']


class URLError(OSError):
    def __init__(self, reason, filename=None):
        self.args = (reason,)
        self.reason = reason
        if filename is not None:
            self.filename = filename

    def __str__(self):
        return '<urlopen error %s>' % self.reason


class HTTPError(URLError):
    def __init__(self, url, code, msg, hdrs, fp):
        self.code = code
        self.msg = msg
        self.hdrs = hdrs
        self.fp = fp
        self.filename = url
        self.reason = msg

    def __str__(self):
        return 'HTTP Error %s: %s' % (self.code, self.msg)

    @property
    def headers(self):
        return self.hdrs

    @property
    def status(self):
        return self.code


class ContentTooShortError(URLError):
    def __init__(self, message, content):
        URLError.__init__(self, message)
        self.content = content
