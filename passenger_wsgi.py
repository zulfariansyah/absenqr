import sys
import os

# Tambahkan path aplikasi ke sistem Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Inisialisasi database jika belum ada
import database
database.init_db()

from app import app as application
