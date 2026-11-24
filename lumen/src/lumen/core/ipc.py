"""Kênh điều khiển giữa một lệnh `lumen` mới gọi và bản Lumen đang chạy.

Wayland không cho ứng dụng tự giữ phím tắt toàn cục, nên phím tắt phải do
Hyprland giữ rồi chạy `lumen --...`. Lệnh đó TUYỆT ĐỐI không được mở thêm một
app nữa — hai tiến trình là hai mpv, nhạc chồng lên nhạc và hai bên cùng ghi
vào một database. Nó phải nói chuyện với bản đang chạy.

Phía GỬI nằm ở đây và dùng socket của thư viện chuẩn, cố ý không dùng Qt: nạp
PySide6 mất khoảng một giây, mà lệnh bấm phím tắt phải xong trong chớp mắt.
Phía NHẬN cần vòng lặp sự kiện nên nằm ở services/control.py.
"""

from __future__ import annotations

import logging
import re
import socket

from lumen.core import paths

log = logging.getLogger(__name__)

CMD_PING = "ping"
CMD_SHOW = "show"
CMD_QUIT = "quit"
CMD_MINI = "mini"
# Vòng 2 R-1: phím tắt phát nhạc.
CMD_TOGGLE = "toggle"
CMD_NEXT = "next"
CMD_PREV = "prev"
CMD_SLOTS = ("slot1", "slot2", "slot3")

# Lệnh cho trợ lý / script (2026-10-16). `seek` và `volume` mang MỘT tham số.
CMD_PLAY = "play"
CMD_PAUSE = "pause"
CMD_MUTE = "mute"
CMD_STATUS = "status"
CMD_SEEK = "seek"
CMD_VOLUME = "volume"

#: Lệnh nào hợp lệ. Bên nhận từ chối mọi thứ ngoài danh sách này thay vì đoán.
COMMANDS = frozenset({CMD_PING, CMD_SHOW, CMD_QUIT, CMD_MINI, CMD_TOGGLE, CMD_NEXT, CMD_PREV, *CMD_SLOTS,
                      CMD_PLAY, CMD_PAUSE, CMD_MUTE, CMD_STATUS, CMD_SEEK, CMD_VOLUME})

#: Lệnh nào nhận tham số, và tham số phải trông thế nào. `seek`: "+10"/"-10" là
#: nhảy tương đối (giây), "30" là tới giây 30. `volume`: 0-100.
_ARGUMENTS = {
    CMD_SEEK: re.compile(r"[+-]?\d{1,6}"),
    CMD_VOLUME: re.compile(r"\d{1,3}"),
}

REPLY_OK = "ok"
REPLY_ERROR = "err"
#: Trần cho một câu trả lời dài (`status` mang JSON) — đủ rộng cho tên bài dài.
MAX_REPLY = 65536

_ENCODING = "utf-8"
_TERMINATOR = "\n"
#: Lệnh dài nhất chỉ vài ký tự; chặn ở đây để một client hỏng không bơm mãi.
MAX_MESSAGE = 256


def encode(command: str) -> bytes:
    """Turn a command into the bytes that travel over the socket."""
    if _TERMINATOR in command:
        raise ValueError("command must not contain a newline")
    return (command + _TERMINATOR).encode(_ENCODING)


def decode(payload: bytes) -> str:
    """Turn received bytes back into a command, or "" if the payload is unusable."""
    if len(payload) > MAX_MESSAGE:
        return ""
    try:
        text = payload.decode(_ENCODING)
    except UnicodeDecodeError:
        return ""
    return text.strip()


def split(command: str) -> tuple[str, str]:
    """Split "seek +10" into ("seek", "+10"); a bare command gets ""."""
    word, _, argument = command.partition(" ")
    return word, argument.strip()


def is_valid(command: str) -> bool:
    """Report whether a command (and its argument, if it takes one) is one this application knows."""
    word, argument = split(command)
    if word not in COMMANDS:
        return False
    shape = _ARGUMENTS.get(word)
    if shape is None:
        return argument == ""
    if not shape.fullmatch(argument):
        return False
    return word != CMD_VOLUME or 0 <= int(argument) <= 100


def _send_unix(address: str, command: str, timeout: float) -> bool:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        try:
            client.connect(address)
            client.sendall(encode(command))
            reply = decode(client.recv(MAX_MESSAGE))
        except (OSError, socket.timeout) as error:
            log.debug("No running Lumen at %s (%s)", address, error)
            return False
    return reply == REPLY_OK


def _request_unix(address: str, command: str, timeout: float) -> str | None:
    """Like `_send_unix`, but read the whole reply (the server closes when done)."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        try:
            client.connect(address)
            client.sendall(encode(command))
            payload = b""
            while len(payload) <= MAX_REPLY:
                chunk = client.recv(4096)
                if not chunk:
                    break
                payload += chunk
        except (OSError, socket.timeout) as error:
            log.debug("No running Lumen at %s (%s)", address, error)
            return None
    try:
        reply = payload.decode(_ENCODING).strip()
    except UnicodeDecodeError:
        return None
    word, _, body = reply.partition(" ")
    return body if word == REPLY_OK else None


def _send_windows(address: str, command: str) -> bool:
    """Talk to the running instance through a Windows named pipe.

    Windows không có socket kiểu file, nên phía nhận (QLocalServer) dựng một
    named pipe. Mở pipe bằng `open()` như một file bình thường là được — không
    cần thư viện ngoài, đúng tinh thần "phía gửi phải nhẹ" của module này.
    """
    try:
        with open(rf"\\.\pipe\{address}", "r+b", buffering=0) as pipe:
            pipe.write(encode(command))
            reply = decode(pipe.read(MAX_MESSAGE))
    except OSError as error:
        log.debug("No running Lumen at pipe %s (%s)", address, error)
        return False
    return reply == REPLY_OK


def send(command: str, *, address: str | None = None, timeout: float = 0.5) -> bool:
    """Send a command to a running Lumen; return False when nobody is listening.

    False is the normal answer on the very first launch, not an error: it means
    "no instance yet, go start one".
    """
    if not is_valid(command):
        raise ValueError(f"unknown command: {command!r}")

    target = address if address is not None else paths.control_address()
    if paths.on_windows():
        return _send_windows(target, command)
    return _send_unix(target, command, timeout)


def request(command: str, *, address: str | None = None, timeout: float = 1.0) -> str | None:
    """Send a command and return the text the running Lumen answers with ("" for a bare ok).

    None = nobody is listening, or the command was refused. Used by `--status`.
    """
    if not is_valid(command):
        raise ValueError(f"unknown command: {command!r}")
    target = address if address is not None else paths.control_address()
    if paths.on_windows():
        return "" if _send_windows(target, command) else None
    return _request_unix(target, command, timeout)
