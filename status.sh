#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$PROJECT_DIR/gunicorn.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$PID" ] && ps -p "$PID" > /dev/null 2>&1; then
        echo "🟢 Status: AKTIF / RUNNING (PID: $PID)"
        echo ""
        echo "📊 Info Proses:"
        ps -ef | grep "$PID" | grep -v grep
        echo ""
        echo "📄 10 Baris Log Terakhir ($PROJECT_DIR/gunicorn.log):"
        tail -n 10 "$PROJECT_DIR/gunicorn.log" 2>/dev/null
        exit 0
    fi
fi

echo "🔴 Status: MATI / STOPPED (Tidak sedang berjalan)"
