"""urllib for a wasmcart cart.

pack_game.sh drops urllib from the packed stdlib, because a cart has no
sockets and CPython's urllib.request drags in http.client, email and socket --
several megabytes that can never run. Dropping it entirely turned out to be
worse than useless, though: a game that merely *imports* urllib at module
scope for an optional online feature dies at boot with ModuleNotFoundError,
long before the feature is reached. SolarWolf's news page is exactly that
shape -- its download is already wrapped in try/except, so the network being
absent is fine; the import failing is not.

So this package exists and imports cleanly:

  urllib.parse   the real CPython module. Pure string manipulation, no
                 sockets, and useful on its own.
  urllib.error   the real exception hierarchy, so `except URLError` works.
  urllib.request the API surface, raising URLError on any attempt to fetch.

A fetch failing is the honest answer -- the cart has no network -- and it
fails the way a caller already handles, rather than at import time in a
place no caller can handle.
"""

__all__ = ['error', 'parse', 'request', 'response']
