"""Đọc tham số dòng lệnh, và trả lời ngay những lệnh không cần mở giao diện.

Đây là cửa trước của app, và nó cố ý KHÔNG chạm tới Qt. Nạp PySide6 mất khoảng
hai giây; một lệnh gửi qua socket rồi thoát thì chỉ cần vài chục mili giây. Nếu
để việc này sau `import lumen.app` thì phím tắt bấm xong phải chờ hai giây mới
thấy gì — đo được, không phải phỏng đoán.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from lumen.core import ipc

PROG = "lumen"

#: Chờ bản vừa được bảo thoát nhả socket ra trước khi hỏi bản tiếp theo.
_HANDOVER_S = 0.35


def build_parser() -> argparse.ArgumentParser:
    """Return the one and only argument parser of the application."""
    parser = argparse.ArgumentParser(prog=PROG)
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    parser.add_argument(
        "--quit", action="store_true", help="ask a running Lumen to exit, then stop"
    )
    parser.add_argument(
        "--mini", action="store_true", help="toggle the floating Mini Lumen window"
    )
    parser.add_argument("--toggle", action="store_true", help="play / pause the running Lumen")
    parser.add_argument("--next", action="store_true", help="skip to the next song")
    parser.add_argument("--prev", action="store_true", help="go back to the previous song")
    parser.add_argument("--slot", type=int, choices=(1, 2, 3), help="play the track in shortcut slot 1-3")
    parser.add_argument("--play", action="store_true", help="play (nothing loaded: the first track)")
    parser.add_argument("--pause", action="store_true", help="pause")
    parser.add_argument("--seek", metavar="SEC", help="+10 / -10 jumps by seconds, 30 goes to second 30")
    parser.add_argument("--mute", action="store_true", help="mute, or bring the volume back")
    parser.add_argument("--volume", metavar="N", type=int, help="set the volume, 0-100")
    parser.add_argument("--status", action="store_true", help="print what is playing as one line of JSON")
    return parser


def parse(argv_tail: list[str]) -> argparse.Namespace:
    """Parse everything after the program name."""
    return build_parser().parse_args(argv_tail)


#: Số lần thử tối đa khi tắt. Bình thường chỉ có một bản, nhưng nếu vì lý do gì
#: đó còn sót vài bản thì mỗi lần một bản nhả socket ra, bản kế tiếp giành lấy —
#: nên phải gọi lại cho tới khi không còn ai trả lời.
_QUIT_ROUNDS = 5


def _quit_everything() -> bool:
    """Ask every running Lumen to exit; return True if at least one answered."""
    stopped = False
    for _ in range(_QUIT_ROUNDS):
        if not ipc.send(ipc.CMD_QUIT):
            break
        stopped = True
        time.sleep(_HANDOVER_S)
    return stopped


def handle_fast_path(argv_tail: list[str]) -> int | None:
    """Answer without a GUI when possible; None means "go ahead and start the app".

    Also the single-instance guard: two Lumen processes mean two mpv playing
    over each other and two writers on one database.
    """
    args = parse(argv_tail)
    if args.quit:
        return 0 if _quit_everything() else 1
    if args.mini:
        # Chưa có bản nào chạy thì đừng báo lỗi: mở app rồi hiện thẳng Mini.
        return 0 if ipc.send(ipc.CMD_MINI) else None
    # Phím tắt phát nhạc: chỉ có nghĩa khi Lumen đang chạy — không có ai trả lời
    # thì báo lỗi chứ đừng mở cả app ra chỉ để bấm Play (vòng 2 R-1).
    for flag, command in ((args.toggle, ipc.CMD_TOGGLE), (args.next, ipc.CMD_NEXT), (args.prev, ipc.CMD_PREV)):
        if flag:
            return 0 if ipc.send(command) else 1
    if args.slot:
        return 0 if ipc.send(ipc.CMD_SLOTS[args.slot - 1]) else 1
    remote = _remote_command(args)
    if remote is not None:
        return remote
    if ipc.send(ipc.CMD_SHOW):
        return 0
    return None


def _remote_command(args: argparse.Namespace) -> int | None:
    """The commands for an assistant or a script; None when none of them was given.

    They never start Lumen: with nothing running they fail (exit 1) instead.
    """
    if args.status:
        answer = ipc.request(ipc.CMD_STATUS)
        sys.stdout.write((answer or json.dumps({"running": False})) + "\n")
        return 0 if answer else 1
    commands = [command for flag, command in ((args.play, ipc.CMD_PLAY), (args.pause, ipc.CMD_PAUSE),
                                              (args.mute, ipc.CMD_MUTE)) if flag]
    if args.seek is not None:
        commands.append(f"{ipc.CMD_SEEK} {args.seek}")
    if args.volume is not None:
        commands.append(f"{ipc.CMD_VOLUME} {args.volume}")
    if not commands:
        return None
    for command in commands:
        if not ipc.is_valid(command):
            sys.stderr.write(f"lumen: tham số không hợp lệ: {command!r}\n")
            return 2
        if not ipc.send(command):
            return 1
    return 0
