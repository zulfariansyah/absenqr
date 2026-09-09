#!/bin/bash
# ==============================================================================
# Script Instalasi Offline Aplikasi Absensi Seminar
# Menginstall seluruh library Python dari folder offline_wheels tanpa akses internet
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=========================================================="
echo "🚀 Memulai Instalasi Offline Aplikasi Absensi Seminar"
echo "=========================================================="

# 1. Deteksi Python 3
if command -v python3 > /dev/null 2>&1; then
    PY_CMD="python3"
elif command -v python > /dev/null 2>&1; then
    PY_CMD="python"
else
    echo "❌ Error: Python 3 tidak ditemukan di sistem!"
    exit 1
fi

PY_VER=$($PY_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "ℹ️  Menggunakan Python: $PY_CMD (Versi $PY_VER)"

# 2. Buat Virtual Environment jika belum ada
VENV_DIR="$PROJECT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Membuat virtual environment di $VENV_DIR..."
    $PY_CMD -m venv "$VENV_DIR" || {
        echo "⚠️  Gagal membuat venv dengan $PY_CMD -m venv."
        echo "   Mencoba menggunakan virtualenv jika ada..."
        virtualenv "$VENV_DIR" || true
    }
fi

if [ -f "$VENV_DIR/bin/python" ]; then
    PYTHON_EXEC="$VENV_DIR/bin/python"
    PIP_EXEC="$VENV_DIR/bin/pip"
else
    echo "⚠️  Menggunakan Python sistem langsung..."
    PYTHON_EXEC="$PY_CMD"
    PIP_EXEC="$PY_CMD -m pip"
fi

# 3. Install packages dari offline_wheels
WHEELS_DIR="$PROJECT_DIR/offline_wheels"
if [ ! -d "$WHEELS_DIR" ]; then
    echo "❌ Error: Direktori $WHEELS_DIR tidak ditemukan!"
    exit 1
fi

echo "📦 Memasang dependensi Python secara offline dari $WHEELS_DIR..."
$PIP_EXEC install --no-index --find-links="$WHEELS_DIR" -r requirements.txt

# 4. Inisialisasi Database SQLite
echo "🗄️  Menginisialisasi database seminar..."
$PYTHON_EXEC -c "import database; database.init_db(); print('✅ Database SQLite siap.')"

# 5. Set permission script
chmod +x start.sh stop.sh status.sh 2>/dev/null || true

echo ""
echo "=========================================================="
echo "🎉 INSTALASI SELESAI!"
echo "=========================================================="
echo "Untuk menjalankan aplikasi:"
echo "  1. Menggunakan Script:"
echo "     ./start.sh"
echo "  2. Atau menggunakan PM2:"
echo "     pm2 start ecosystem.config.js"
echo "  3. Atau langsung dengan Python/Gunicorn:"
echo "     $VENV_DIR/bin/gunicorn -w 3 -b 0.0.0.0:5000 wsgi:app"
echo "=========================================================="
