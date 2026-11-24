"""Phía nhận của kênh điều khiển: nghe lệnh từ những lần gọi `lumen` sau.

Ở đây mới được dùng Qt, vì nghe socket cần vòng lặp sự kiện. Phía gửi cố ý nằm
ở core/ipc.py và không đụng tới Qt — xem lý do trong file đó.

Server KHÔNG tự quyết định làm gì với lệnh: nó kiểm tra lệnh có hợp lệ không
rồi phát tín hiệu. Ai nối dây (app.py) mới biết "show" nghĩa là hiện cửa sổ nào.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from lumen.core import ipc, paths

log = logging.getLogger(__name__)


class ControlServer(QObject):
    """Listen on a Unix socket and emit each valid command that arrives."""

    commandReceived = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_connection)
        self._address: str | None = None
        # Giữ đệm riêng cho từng kết nối: một lệnh có thể tới làm nhiều mẩu.
        self._buffers: dict[QLocalSocket, bytes] = {}
        # `status` phải trả lời bằng DỮ LIỆU, nên server hỏi thẳng hàm này
        # (app.py cấp) thay vì phát tín hiệu rồi trả "ok" như mọi lệnh khác.
        self.status_provider: Callable[[], str] | None = None

    @property
    def address(self) -> str | None:
        """Return the address currently being listened on, if any."""
        return self._address

    def start(self, address: str | None = None) -> bool:
        """Start listening; return False if the socket could not be claimed.

        Hỏi xem có ai đang nghe TRƯỚC khi dọn file socket. Dọn vô điều kiện là
        cách một bản thứ hai CƯỚP socket của bản đang sống: bản cũ vẫn chạy,
        vẫn phát nhạc, nhưng không lệnh nào tới được nó nữa và người dùng không
        còn cách nào tắt ngoài `kill`. Đã xảy ra thật.
        """
        target = address if address is not None else paths.control_address()
        if ipc.send(ipc.CMD_PING, address=target):
            log.info("Another Lumen already owns %s", target)
            return False
        # Tới đây thì chắc chắn không ai nghe: file còn sót lại là rác của một
        # lần thoát đột ngột, dọn đi mới nghe lại được.
        QLocalServer.removeServer(target)
        if not self._server.listen(target):
            log.error("Could not listen on %s: %s", target, self._server.errorString())
            return False
        self._address = target
        log.info("Control socket ready at %s", target)
        return True

    def stop(self) -> None:
        """Stop listening and remove the socket file."""
        if self._address is None:
            return
        self._server.close()
        QLocalServer.removeServer(self._address)
        self._address = None

    def _on_connection(self) -> None:
        connection = self._server.nextPendingConnection()
        if connection is None:
            return
        self._buffers[connection] = b""
        connection.readyRead.connect(lambda: self._on_ready(connection))
        connection.disconnected.connect(lambda: self._forget(connection))

    def _on_ready(self, connection: QLocalSocket) -> None:
        buffered = self._buffers.get(connection, b"") + bytes(connection.readAll())
        if len(buffered) > ipc.MAX_MESSAGE:
            self._reply(connection, ipc.REPLY_ERROR)
            return
        if b"\n" not in buffered:
            self._buffers[connection] = buffered
            return

        command = ipc.decode(buffered)
        if not ipc.is_valid(command):
            log.warning("Ignoring unknown control command: %r", command)
            self._reply(connection, ipc.REPLY_ERROR)
            return
        if ipc.split(command)[0] == ipc.CMD_STATUS:
            if self.status_provider is None:
                self._reply(connection, ipc.REPLY_ERROR)
            else:
                self._reply(connection, ipc.REPLY_OK + " " + self.status_provider())
            return
        self._reply(connection, ipc.REPLY_OK)
        self.commandReceived.emit(command)

    def _reply(self, connection: QLocalSocket, reply: str) -> None:
        connection.write(ipc.encode(reply))
        connection.flush()
        connection.disconnectFromServer()
        self._forget(connection)

    def _forget(self, connection: QLocalSocket) -> None:
        self._buffers.pop(connection, None)
