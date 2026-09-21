"""Secure storage for API keys using the OS keyring (Secret Service).

Uses the system ``libsecret`` through ``ctypes`` so no third-party Python
package is required.  On Linux desktops this is backed by GNOME Keyring or
KWallet.  If libsecret or a running Secret Service is unavailable, ``available()``
returns False and callers fall back to their previous behaviour.
"""

import ctypes
import ctypes.util

APP_NAME = "HaiLPER"
SCHEMA_NAME = b"io.github.rokusaburo.hailper"
ATTR = b"provider"

_glib = None
try:
    _glib = ctypes.CDLL(ctypes.util.find_library("glib-2.0") or "libglib-2.0.so.0")
    _glib.g_error_free.argtypes = [ctypes.c_void_p]
except Exception:
    _glib = None


class _Attr(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char_p), ("type", ctypes.c_int)]


class _Schema(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char_p), ("flags", ctypes.c_int),
                ("attributes", _Attr * 32)]


def _free_error(err):
    try:
        if err.value and _glib is not None:
            _glib.g_error_free(err)
    except Exception:
        pass


class _Libsecret(object):
    def __init__(self):
        self.lib = None
        try:
            path = ctypes.util.find_library("secret-1") or "libsecret-1.so.0"
            lib = ctypes.CDLL(path)
            lib.secret_password_store_sync.restype = ctypes.c_int
            lib.secret_password_lookup_sync.restype = ctypes.c_void_p
            lib.secret_password_clear_sync.restype = ctypes.c_int
            lib.secret_password_free.argtypes = [ctypes.c_void_p]
            self.lib = lib
        except Exception:
            self.lib = None

    def _schema(self):
        schema = _Schema()
        schema.name = SCHEMA_NAME
        schema.flags = 0
        schema.attributes[0].name = ATTR
        schema.attributes[0].type = 0  # SECRET_SCHEMA_ATTRIBUTE_STRING
        for index in range(1, 32):
            schema.attributes[index].name = None
        return schema

    def get(self, account):
        schema = self._schema()
        err = ctypes.c_void_p()
        result = self.lib.secret_password_lookup_sync(
            ctypes.byref(schema), None, ctypes.byref(err),
            ATTR, account.encode("utf-8"), None)
        _free_error(err)
        if not result:
            return ""
        try:
            return ctypes.string_at(result).decode("utf-8", "replace")
        finally:
            self.lib.secret_password_free(ctypes.c_void_p(result))

    def set(self, account, secret):
        schema = self._schema()
        err = ctypes.c_void_p()
        ok = self.lib.secret_password_store_sync(
            ctypes.byref(schema), None, APP_NAME.encode("utf-8"),
            secret.encode("utf-8"), None, ctypes.byref(err),
            ATTR, account.encode("utf-8"), None)
        _free_error(err)
        return bool(ok)

    def delete(self, account):
        schema = self._schema()
        err = ctypes.c_void_p()
        ok = self.lib.secret_password_clear_sync(
            ctypes.byref(schema), None, ctypes.byref(err),
            ATTR, account.encode("utf-8"), None)
        _free_error(err)
        return bool(ok)


_backend = None


def _get_backend():
    global _backend
    if _backend is None:
        _backend = _Libsecret()
    return _backend


def available():
    try:
        return _get_backend().lib is not None
    except Exception:
        return False


def get(account):
    """Return the stored secret, "" if none, or None if no backend."""
    try:
        if not available():
            return None
        return _get_backend().get(account)
    except Exception:
        return None


def set(account, secret):
    try:
        if not available():
            return False
        return _get_backend().set(account, secret)
    except Exception:
        return False


def delete(account):
    try:
        if not available():
            return False
        return _get_backend().delete(account)
    except Exception:
        return False
