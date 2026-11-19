"""
Drag & drop onto the desktop BOT: files (-> phone) and now also text / links (-> phone clipboard).

Windows only sends plain WM_DROPFILES for files, so BOT registers an OLE drop target
(IDropTarget) to also accept text dragged from a browser, Word, Notepad...
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
from ctypes import POINTER, Structure, c_long, c_longlong, c_ulong, c_ushort, c_void_p

import comtypes
from comtypes import COMMETHOD, GUID, HRESULT, IUnknown, COMObject

log = logging.getLogger("bot")
ole32 = ctypes.WinDLL("ole32")
kernel32 = ctypes.WinDLL("kernel32")
shell32 = ctypes.WinDLL("shell32")
kernel32.GlobalLock.restype = c_void_p
kernel32.GlobalLock.argtypes = [c_void_p]
kernel32.GlobalUnlock.argtypes = [c_void_p]
shell32.DragQueryFileW.argtypes = [c_void_p, ctypes.c_uint, wt.LPWSTR, ctypes.c_uint]
shell32.DragQueryFileW.restype = ctypes.c_uint
CF_UNICODETEXT, CF_HDROP = 13, 15
DROPEFFECT_NONE, DROPEFFECT_COPY = 0, 1


class FORMATETC(Structure):
    _fields_ = [("cfFormat", c_ushort), ("ptd", c_void_p), ("dwAspect", c_ulong), ("lindex", c_long),
                ("tymed", c_ulong)]


class STGMEDIUM(Structure):
    _fields_ = [("tymed", c_ulong), ("hGlobal", c_void_p), ("pUnkForRelease", c_void_p)]


ole32.ReleaseStgMedium.argtypes = [POINTER(STGMEDIUM)]


class IDataObject(IUnknown):
    _iid_ = GUID("{0000010e-0000-0000-C000-000000000046}")
    _methods_ = [
        COMMETHOD([], HRESULT, "GetData", (["in"], POINTER(FORMATETC), "pformatetcIn"),
                  (["in"], POINTER(STGMEDIUM), "pmedium")),
        COMMETHOD([], HRESULT, "GetDataHere", (["in"], POINTER(FORMATETC), "pformatetc"),
                  (["in"], POINTER(STGMEDIUM), "pmedium")),
        COMMETHOD([], HRESULT, "QueryGetData", (["in"], POINTER(FORMATETC), "pformatetc")),
    ]


class IDropTarget(IUnknown):
    _iid_ = GUID("{00000122-0000-0000-C000-000000000046}")
    _methods_ = [
        # POINTL is passed by value (8 bytes): declared as one 64-bit number
        COMMETHOD([], HRESULT, "DragEnter", (["in"], POINTER(IDataObject), "pDataObj"), (["in"], c_ulong, "grfKeyState"),
                  (["in"], c_longlong, "pt"), (["in"], POINTER(c_ulong), "pdwEffect")),
        COMMETHOD([], HRESULT, "DragOver", (["in"], c_ulong, "grfKeyState"), (["in"], c_longlong, "pt"),
                  (["in"], POINTER(c_ulong), "pdwEffect")),
        COMMETHOD([], HRESULT, "DragLeave"),
        COMMETHOD([], HRESULT, "Drop", (["in"], POINTER(IDataObject), "pDataObj"), (["in"], c_ulong, "grfKeyState"),
                  (["in"], c_longlong, "pt"), (["in"], POINTER(c_ulong), "pdwEffect")),
    ]


def _get(data, cf: int) -> STGMEDIUM | None:
    fmt = FORMATETC(cf, None, 1, -1, 1)  # DVASPECT_CONTENT, TYMED_HGLOBAL
    med = STGMEDIUM()
    try:
        data.GetData(ctypes.byref(fmt), ctypes.byref(med))
    except (comtypes.COMError, OSError):
        return None
    return med if med.hGlobal else None


def read(data) -> tuple[list[str], str]:
    """(file paths, text) from a dragged IDataObject."""
    files, text = [], ""
    med = _get(data, CF_HDROP)
    if med is not None:
        try:
            n = shell32.DragQueryFileW(med.hGlobal, 0xFFFFFFFF, None, 0)
            for i in range(n):
                buf = ctypes.create_unicode_buffer(1024)
                shell32.DragQueryFileW(med.hGlobal, i, buf, 1024)
                files.append(buf.value)
        finally:
            ole32.ReleaseStgMedium(ctypes.byref(med))
    if not files:
        med = _get(data, CF_UNICODETEXT)
        if med is not None:
            try:
                p = kernel32.GlobalLock(med.hGlobal)
                if p:
                    text = ctypes.wstring_at(p)
                    kernel32.GlobalUnlock(med.hGlobal)
            finally:
                ole32.ReleaseStgMedium(ctypes.byref(med))
    return files, text


class DropTarget(COMObject):
    _com_interfaces_ = [IDropTarget]

    def __init__(self, on_drop):
        super().__init__()
        self.on_drop = on_drop  # on_drop(files, text)
        self._ok = False

    def _can(self, data) -> bool:
        for cf in (CF_HDROP, CF_UNICODETEXT):
            fmt = FORMATETC(cf, None, 1, -1, 1)
            try:
                if data.QueryGetData(ctypes.byref(fmt)) == 0:
                    return True
            except (comtypes.COMError, OSError):
                pass
        return False

    def IDropTarget_DragEnter(self, this, pDataObj, grfKeyState, pt, pdwEffect):
        try:
            self._ok = self._can(pDataObj)
        except Exception:
            self._ok = False
        pdwEffect[0] = DROPEFFECT_COPY if self._ok else DROPEFFECT_NONE
        return 0

    def IDropTarget_DragOver(self, this, grfKeyState, pt, pdwEffect):
        pdwEffect[0] = DROPEFFECT_COPY if self._ok else DROPEFFECT_NONE
        return 0

    def IDropTarget_DragLeave(self, this):
        return 0

    def IDropTarget_Drop(self, this, pDataObj, grfKeyState, pt, pdwEffect):
        try:
            files, text = read(pDataObj)
            if files or text:
                self.on_drop(files, text)
                pdwEffect[0] = DROPEFFECT_COPY
            else:
                pdwEffect[0] = DROPEFFECT_NONE
        except Exception:
            log.exception("drop failed")
            pdwEffect[0] = DROPEFFECT_NONE
        return 0


def register(hwnd, on_drop):
    """Accept files and text on this window. Returns the target (keep a reference) or None."""
    try:
        ole32.OleInitialize(None)
        target = DropTarget(on_drop)
        ptr = target.QueryInterface(IDropTarget)
        hr = ole32.RegisterDragDrop(wt.HWND(hwnd), ptr)
        if hr != 0:
            log.info("Text drop unavailable (0x%08X); files still work", hr & 0xFFFFFFFF)
            return None
        return target, ptr
    except Exception as exc:
        log.info("Text drop unavailable: %s", exc)
        return None
