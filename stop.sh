#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$PROJECT_DIR/gunicorn.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$PID" ] && ps -p "$PID" > /dev/null 2>&1; then
        echo "🛑 Menghentikan Aplikasi Absen (PID: $PID)..."
        kill -15 "$PID" 2>/dev/null
        sleep 2
        if ps -p "$PID" > /dev/null 2>&1; then
            kill -9 "$PID" 2>/dev/null
        fi
        rm -f "$PID_FILE"
        echo "✅ Aplikasi berhasil dihentikan."
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

# Fallback menghentikan proses gunicorn wsgi:app milik user ini
pkill -f "gunicorn.*wsgi:app" 2>/dev/null && echo "✅ Proses gunicorn berhasil dihentikan." || echo "ℹ️  Aplikasi tidak sedang berjalan."
