"""Module entry point: ``python -m lumen``.

Cửa trước phải NHẸ. Mọi thứ ở đây chạy trước khi Qt được nạp, để một lệnh như
`lumen --quit` hay một cú bấm phím tắt không phải trả giá hai giây khởi động.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """Handle the no-GUI commands first, then hand over to the real application."""
    argv_list = list(sys.argv if argv is None else argv)

    from lumen.core.cli import handle_fast_path

    handled = handle_fast_path(argv_list[1:])
    if handled is not None:
        return handled

    from lumen.app import main as run_app  # nạp Qt ở đây, không sớm hơn

    return run_app(argv_list)


if __name__ == "__main__":
    sys.exit(main())
