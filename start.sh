#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PID_FILE="$PROJECT_DIR/gunicorn.pid"
LOG_FILE="$PROJECT_DIR/gunicorn.log"
PORT=${PORT:-5000}

# Periksa apakah proses sudah berjalan
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$PID" ] && ps -p "$PID" > /dev/null 2>&1; then
        echo "⚠️  Aplikasi Absen sudah berjalan dengan PID $PID pada port $PORT."
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

# Cari path gunicorn di virtual environment
if [ -f "$PROJECT_DIR/venv/bin/gunicorn" ]; then
    GUNICORN_BIN="$PROJECT_DIR/venv/bin/gunicorn"
elif [ -f "$PROJECT_DIR/.venv/bin/gunicorn" ]; then
    GUNICORN_BIN="$PROJECT_DIR/.venv/bin/gunicorn"
else
    GUNICORN_BIN="gunicorn"
fi

echo "🚀 Menjalankan Aplikasi Absen Seminar di background (Port $PORT)..."
nohup "$GUNICORN_BIN" --workers 3 --bind 127.0.0.1:$PORT --pid "$PID_FILE" wsgi:app >> "$LOG_FILE" 2>&1 &

sleep 2

if [ -f "$PID_FILE" ]; then
    NEW_PID=$(cat "$PID_FILE")
    echo "✅ Berhasil dijalankan! (PID: $NEW_PID)"
    echo "📄 File log: $LOG_FILE"
else
    echo "❌ Gagal menjalankan. Silakan cek $LOG_FILE"
fi
