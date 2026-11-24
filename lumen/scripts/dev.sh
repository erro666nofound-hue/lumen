#!/bin/bash

# Xác định đường dẫn repo
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Bật logging cho QML
export QT_LOGGING_RULES="qt.qml.binding.removal.info=true"

# Chạy app từ source với log ra terminal
exec /usr/bin/python3 "$REPO/run.py" --verbose "$@"
