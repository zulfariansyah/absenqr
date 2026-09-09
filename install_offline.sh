#!/bin/bash
# ==============================================================================
# Script Instalasi Offline Aplikasi Absensi Seminar
# Menginstall seluruh library Python dari folder offline_wheels tanpa akses internet & tanpa apt
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

# Direktori target
VENV_DIR="$PROJECT_DIR/.venv"
WHEELS_DIR="$PROJECT_DIR/offline_wheels"

if [ ! -d "$WHEELS_DIR" ]; then
    echo "❌ Error: Direktori $WHEELS_DIR tidak ditemukan!"
    exit 1
fi

# 2. Buat Virtual Environment dengan --without-pip (agar tidak butuh ensurepip/apt)
if [ ! -f "$VENV_DIR/bin/python3" ] && [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "📦 Membuat virtual environment di $VENV_DIR (mode standalone --without-pip)..."
    rm -rf "$VENV_DIR"
    $PY_CMD -m venv --without-pip "$VENV_DIR"
fi

VENV_PY="$VENV_DIR/bin/python3"
if [ ! -f "$VENV_PY" ]; then
    VENV_PY="$VENV_DIR/bin/python"
fi

# 3. Bootstrap PIP & Setuptools ke dalam venv dari offline_wheels
if [ ! -f "$VENV_DIR/bin/pip" ]; then
    echo "🔧 Menginisialisasi pip ke dalam virtual environment secara offline..."
    
    PIP_WHL=$(find "$WHEELS_DIR" -name "pip-*.whl" | head -n 1)
    SETUPTOOLS_WHL=$(find "$WHEELS_DIR" -name "setuptools-*.whl" | head -n 1)
    WHEEL_WHL=$(find "$WHEELS_DIR" -name "wheel-*.whl" | head -n 1)
    
    if [ -n "$PIP_WHL" ]; then
        PYTHONPATH="$PIP_WHL:$SETUPTOOLS_WHL:$WHEEL_WHL" "$VENV_PY" -m pip install --no-index --find-links="$WHEELS_DIR" pip setuptools wheel || {
            if [ -f "$WHEELS_DIR/get-pip.py" ]; then
                echo "ℹ️  Mencoba bootstrap via get-pip.py..."
                "$VENV_PY" "$WHEELS_DIR/get-pip.py" --no-index --find-links="$WHEELS_DIR"
            fi
        }
    fi
fi

# 4. Install seluruh dependensi proyek dari offline_wheels
echo "📦 Memasang dependensi aplikasi secara offline dari $WHEELS_DIR..."
if [ -f "$VENV_DIR/bin/pip" ]; then
    "$VENV_DIR/bin/pip" install --no-index --find-links="$WHEELS_DIR" -r requirements.txt
else
    PIP_WHL=$(find "$WHEELS_DIR" -name "pip-*.whl" | head -n 1)
    PYTHONPATH="$PIP_WHL" "$VENV_PY" -m pip install --no-index --find-links="$WHEELS_DIR" -r requirements.txt
fi

# 5. Inisialisasi Database SQLite
echo "🗄️  Menginisialisasi database seminar..."
"$VENV_PY" -c "import database; database.init_db(); print('✅ Database SQLite siap.')"

# 6. Set permission executable
chmod +x start.sh stop.sh status.sh 2>/dev/null || true

echo ""
echo "=========================================================="
echo "🎉 INSTALASI OFFLINE BERHASIL!"
echo "=========================================================="
echo "Virtual Environment berhasil dibuat di: $VENV_DIR"
echo "Untuk menjalankan aplikasi:"
echo "  1. Menggunakan Script:"
echo "     ./start.sh"
echo "  2. Atau menggunakan PM2:"
echo "     pm2 restart absen-seminar   (atau: pm2 start ecosystem.config.js)"
echo "=========================================================="
