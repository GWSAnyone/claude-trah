#!/usr/bin/env python3
"""Сессия-заглушка для проверок: слушает, что хук шлёт в её канал. Только тесты.

На POSIX — unix-сокет по заданному пути, как всегда. Под Windows unix-сокетов
у питона нет, а у настоящей сессии канал — именованный `\\\\.\\pipe\\…`, поэтому
заглушка поднимает такой канал сама (WinAPI через ctypes) и отдаёт его имя в
`адрес`. Строку авторизации `{"type":"auth",…}`, которую `sockmsg` шлёт в канал
первой, заглушка не записывает: проверки считают кадры, а не рукопожатие.

Использование: `ухо = Ухо(путь)`, в окружение хука — `ухо.адрес`, строки —
`ухо.строки`, в конце `ухо.закрыть()`.
"""
import hashlib
import json
import os
import socket
import threading

WINDOWS = os.name == "nt"


def _полезные(данные: bytes) -> list[str]:
    строки = []
    for с in данные.decode("utf-8", "replace").splitlines():
        if not с.strip():
            continue
        try:
            if json.loads(с).get("type") == "auth":
                continue
        except (ValueError, AttributeError):
            pass
        строки.append(с)
    return строки


class Ухо:
    def __init__(self, путь: str):
        self.путь = путь
        self.строки: list[str] = []
        self.lines = self.строки  # то же ухо под английским именем
        self._закрыто = False
        if WINDOWS:
            self.адрес = r"\\.\pipe\trah-test-" + hashlib.sha1(
                f"{путь}:{os.getpid()}".encode()).hexdigest()[:16]
            self._канал_готов = threading.Event()
            threading.Thread(target=self._слушать_канал, daemon=True).start()
            self._канал_готов.wait(5)
        else:
            self.адрес = путь
            self.сокет = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.сокет.bind(путь)
            self.сокет.listen(4)
            threading.Thread(target=self._слушать_сокет, daemon=True).start()

    # --- POSIX -----------------------------------------------------------------
    def _слушать_сокет(self) -> None:
        while True:
            try:
                связь, _ = self.сокет.accept()
            except OSError:
                return
            with связь:
                связь.settimeout(2)
                данные = b""
                try:
                    while кусок := связь.recv(65536):
                        данные += кусок
                except OSError:
                    pass
                self.строки += _полезные(данные)

    # --- Windows ---------------------------------------------------------------
    def _слушать_канал(self) -> None:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateNamedPipeW.restype = wintypes.HANDLE
        k32.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                         wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                         wintypes.DWORD, wintypes.LPVOID]
        k32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
        k32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                                 ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        k32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        PIPE_ACCESS_INBOUND, ERROR_PIPE_CONNECTED, НЕВЕРНЫЙ = 1, 535, wintypes.HANDLE(-1).value
        канал = k32.CreateNamedPipeW(self.адрес, PIPE_ACCESS_INBOUND, 0, 255,
                                     65536, 65536, 0, None)
        self._канал_готов.set()
        if канал == НЕВЕРНЫЙ:
            return
        буфер = ctypes.create_string_buffer(65536)
        прочитано = wintypes.DWORD(0)
        try:
            while not self._закрыто:
                if not k32.ConnectNamedPipe(канал, None) and \
                        ctypes.get_last_error() != ERROR_PIPE_CONNECTED:
                    return
                данные = b""
                while k32.ReadFile(канал, буфер, len(буфер), ctypes.byref(прочитано), None) \
                        and прочитано.value:
                    данные += буфер.raw[:прочитано.value]
                k32.DisconnectNamedPipe(канал)
                if not self._закрыто:
                    self.строки += _полезные(данные)
        finally:
            k32.CloseHandle(канал)

    def закрыть(self) -> None:
        self._закрыто = True
        if WINDOWS:
            # Разбудить поток, стоящий в ConnectNamedPipe, пустым подключением.
            try:
                with open(self.адрес, "wb", buffering=0):
                    pass
            except OSError:
                pass
        else:
            self.сокет.close()

    close = закрыть
