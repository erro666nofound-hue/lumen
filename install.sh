#!/bin/bash
# Lối vào dễ thấy ở gốc repo. Script thật: lumen/scripts/install.sh
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lumen/scripts/install.sh" "$@"
