import sqlite3
import random
import string
from datetime import datetime
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seminar.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn

from werkzeug.security import generate_password_hash, check_password_hash

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qr_code TEXT UNIQUE NOT NULL,
            nim_nip TEXT NOT NULL,
            nama_lengkap TEXT NOT NULL,
            no_hp TEXT DEFAULT '',
            institusi TEXT NOT NULL,
            pekerjaan TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pendaftar',
            created_at TEXT NOT NULL,
            attended_at TEXT
        )
    """)
    
    # Migrasi otomatis jika kolom no_hp belum ada
    cursor.execute("PRAGMA table_info(participants)")
    columns = [col['name'] for col in cursor.fetchall()]
    if 'no_hp' not in columns:
        cursor.execute("ALTER TABLE participants ADD COLUMN no_hp TEXT DEFAULT ''")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nama TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            created_at TEXT NOT NULL,
            last_login TEXT
        )
    """)
    # Set default event settings if not exist
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('event_name', 'Seminar Nasional Teknologi & Inovasi 2026')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('event_logo', '')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('event_favicon', '')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('event_info', '')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('title_peserta', '')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('title_console', '')")
    
    # Inisialisasi 5 User Admin Bawaan
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    default_hash = generate_password_hash('admin123', method='pbkdf2:sha256')
    
    default_admins = [
        ('admin', default_hash, 'Super Admin', 'superadmin', now_str),
        ('petugas1', default_hash, 'Petugas Absensi 1', 'admin', now_str),
        ('petugas2', default_hash, 'Petugas Absensi 2', 'admin', now_str),
        ('petugas3', default_hash, 'Petugas Absensi 3', 'admin', now_str),
        ('petugas4', default_hash, 'Petugas Absensi 4', 'admin', now_str),
    ]
    
    for u, h, n, r, c in default_admins:
        cursor.execute("""
            INSERT OR IGNORE INTO admins (username, password_hash, nama, role, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (u, h, n, r, c))
    
    conn.commit()
    conn.close()

def verify_admin(username, password):
    """Memverifikasi username dan password admin, mengembalikan objek admin jika valid"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins WHERE username = ?", (username.strip(),))
    admin = cursor.fetchone()
    conn.close()
    
    if not admin:
        return None
        
    try:
        if check_password_hash(admin['password_hash'], password):
            return dict(admin)
    except Exception:
        pass
            
    return None

def update_admin_last_login(admin_id):
    """Memperbarui timestamp login terakhir admin"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE admins SET last_login = ? WHERE id = ?", (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), admin_id
    ))
    conn.commit()
    conn.close()

def get_all_admins():
    """Mengambil daftar seluruh user admin"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, nama, role, created_at, last_login FROM admins ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_admin_by_id(admin_id):
    """Mengambil data admin berdasarkan ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, nama, role, created_at, last_login FROM admins WHERE id = ?", (admin_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_admin_password(admin_id, new_password):
    """Mengatur/mengubah password admin tertentu (fitur Super Admin & ganti password sendiri)"""
    if not new_password or not new_password.strip():
        return False
    hash_val = generate_password_hash(new_password.strip(), method='pbkdf2:sha256')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE admins SET password_hash = ? WHERE id = ?", (hash_val, admin_id))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected

def update_admin_profile(admin_id, nama, username=None, role=None):
    """Memperbarui informasi profil admin"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if nama and nama.strip():
        updates.append("nama = ?")
        params.append(nama.strip())
    if username and username.strip():
        updates.append("username = ?")
        params.append(username.strip())
    if role and role in ['superadmin', 'admin']:
        updates.append("role = ?")
        params.append(role)
        
    if not updates:
        conn.close()
        return False
        
    params.append(admin_id)
    query = f"UPDATE admins SET {', '.join(updates)} WHERE id = ?"
    try:
        cursor.execute(query, params)
        conn.commit()
        affected = cursor.rowcount > 0
    except sqlite3.IntegrityError:
        affected = False
    finally:
        conn.close()
    return affected

def create_admin(username, password, nama, role='admin'):
    """Membuat user admin baru"""
    hash_val = generate_password_hash(password.strip(), method='pbkdf2:sha256')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO admins (username, password_hash, nama, role, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (username.strip(), hash_val, nama.strip(), role, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return get_admin_by_id(new_id)
    except sqlite3.IntegrityError:
        conn.close()
        return None

def delete_admin(admin_id):
    """Menghapus user admin (Super Admin tidak boleh menghapus akun dirinya sendiri)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admins WHERE id = ?", (admin_id,))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected

def get_setting(key, default=''):
    """Mengambil nilai setting berdasarkan key"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default

def set_setting(key, value):
    """Menyimpan atau memperbarui nilai setting"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
    conn.commit()
    conn.close()

def get_all_settings():
    """Mengambil seluruh data settings dalam bentuk dictionary"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    settings = {row['key']: row['value'] for row in rows}
    if 'event_name' not in settings:
        settings['event_name'] = 'Seminar Nasional Teknologi & Inovasi 2026'
    if 'event_logo' not in settings:
        settings['event_logo'] = ''
    if 'event_favicon' not in settings:
        settings['event_favicon'] = ''
    if 'event_info' not in settings:
        settings['event_info'] = ''
    if 'title_peserta' not in settings:
        settings['title_peserta'] = ''
    if 'title_console' not in settings:
        settings['title_console'] = ''
    return settings

def generate_unique_qr_code():
    """Menghasilkan 10 karakter alfanumerik acak kapital yang unik"""
    chars = string.ascii_uppercase + string.digits
    conn = get_db_connection()
    cursor = conn.cursor()
    while True:
        code = "".join(random.choices(chars, k=10))
        cursor.execute("SELECT id FROM participants WHERE qr_code = ?", (code,))
        if cursor.fetchone() is None:
            conn.close()
            return code

def register_participant(nim_nip, nama_lengkap, no_hp, institusi, pekerjaan):
    """Mendaftarkan pendaftar baru dengan status default 'pendaftar'"""
    qr_code = generate_unique_qr_code()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO participants (qr_code, nim_nip, nama_lengkap, no_hp, institusi, pekerjaan, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'pendaftar', ?)
    """, (qr_code, nim_nip.strip(), nama_lengkap.strip(), (no_hp or '').strip(), institusi.strip(), pekerjaan.strip(), created_at))
    conn.commit()
    inserted_id = cursor.lastrowid
    
    cursor.execute("SELECT * FROM participants WHERE id = ?", (inserted_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)

def upsert_participant_from_csv(qr_code, nim_nip, nama_lengkap, no_hp='', institusi='-', pekerjaan='Lainnya', status='pendaftar', created_at=None, attended_at=None, overwrite=True):
    """
    Menyimpan atau memperbarui data peserta dari file CSV backup (pendaftar & peserta).
    Jika data sudah ada (berdasarkan qr_code atau nim_nip):
    - Jika overwrite=True: data diperbarui.
    - Jika overwrite=False: data dilewati (skip).
    """
    if not qr_code or len(qr_code.strip()) < 5:
        qr_code = generate_unique_qr_code()
    else:
        qr_code = qr_code.strip().upper()
        
    cleaned_nim = nim_nip.strip()
    cleaned_nama = nama_lengkap.strip()
    cleaned_hp = (no_hp or '').strip()
    cleaned_inst = institusi.strip()
    cleaned_job = pekerjaan.strip() if pekerjaan else 'Lainnya'
    
    status_lower = (status or 'pendaftar').strip().lower()
    final_status = 'peserta' if ('peserta' in status_lower or 'hadir' in status_lower) and 'belum' not in status_lower else 'pendaftar'
    
    final_created_at = created_at.strip() if created_at and created_at.strip() != '-' else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    final_attended_at = None
    if final_status == 'peserta':
        if attended_at and attended_at.strip() != '-':
            final_attended_at = attended_at.strip()
        else:
            final_attended_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM participants WHERE qr_code = ? OR nim_nip = ?", (qr_code, cleaned_nim))
    existing = cursor.fetchone()
    
    if existing:
        if overwrite:
            cursor.execute("""
                UPDATE participants 
                SET qr_code = ?, nim_nip = ?, nama_lengkap = ?, no_hp = ?, institusi = ?, pekerjaan = ?, status = ?, created_at = ?, attended_at = ?
                WHERE id = ?
            """, (qr_code, cleaned_nim, cleaned_nama, cleaned_hp, cleaned_inst, cleaned_job, final_status, final_created_at, final_attended_at, existing['id']))
            conn.commit()
            conn.close()
            return 'updated'
        else:
            conn.close()
            return 'skipped'
    else:
        cursor.execute("""
            INSERT INTO participants (qr_code, nim_nip, nama_lengkap, no_hp, institusi, pekerjaan, status, created_at, attended_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (qr_code, cleaned_nim, cleaned_nama, cleaned_hp, cleaned_inst, cleaned_job, final_status, final_created_at, final_attended_at))
        conn.commit()
        conn.close()
        return 'inserted'

def get_participant_by_nim(nim_nip):
    """Mencari data peserta berdasarkan NIM/NIP untuk deteksi duplikasi pendaftaran"""
    if not nim_nip:
        return None
    cleaned = nim_nip.strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM participants WHERE nim_nip = ?", (cleaned,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_participant_by_qr(qr_code):
    """Mencari data peserta berdasarkan QR Code"""
    if not qr_code:
        return None
    code_cleaned = qr_code.strip().upper()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM participants WHERE UPPER(qr_code) = ?", (code_cleaned,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_participant_by_id(participant_id):
    """Mencari data peserta berdasarkan ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM participants WHERE id = ?", (participant_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def mark_attendance(qr_code):
    """
    Memproses pemindaian QR Code.
    Mengubah status 'pendaftar' menjadi 'peserta' dan mencatat waktu hadir.
    """
    participant = get_participant_by_qr(qr_code)
    if not participant:
        return {
            "success": False,
            "code": "NOT_FOUND",
            "message": f"QR Code '{qr_code}' tidak ditemukan dalam database pendaftar."
        }
    
    if participant["status"] == "peserta":
        return {
            "success": False,
            "code": "ALREADY_ATTENDED",
            "message": f"Peserta '{participant['nama_lengkap']}' sudah melakukan absensi sebelumnya pada {participant['attended_at']}.",
            "data": participant
        }
    
    attended_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE participants
        SET status = 'peserta', attended_at = ?
        WHERE id = ?
    """, (attended_at, participant["id"]))
    conn.commit()
    
    cursor.execute("SELECT * FROM participants WHERE id = ?", (participant["id"],))
    updated_row = dict(cursor.fetchone())
    conn.close()
    
    return {
        "success": True,
        "code": "SUCCESS",
        "message": f"Absensi berhasil! Status '{updated_row['nama_lengkap']}' kini resmi menjadi Peserta.",
        "data": updated_row
    }

def toggle_status(participant_id):
    """Mengubah status pendaftar <-> peserta secara manual dari tabel admin"""
    participant = get_participant_by_id(participant_id)
    if not participant:
        return None
    
    new_status = "peserta" if participant["status"] == "pendaftar" else "pendaftar"
    attended_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_status == "peserta" else None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE participants
        SET status = ?, attended_at = ?
        WHERE id = ?
    """, (new_status, attended_at, participant_id))
    conn.commit()
    
    cursor.execute("SELECT * FROM participants WHERE id = ?", (participant_id,))
    updated = dict(cursor.fetchone())
    conn.close()
    return updated

def delete_participant(participant_id):
    """Menghapus data pendaftar/peserta"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM participants WHERE id = ?", (participant_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def bulk_delete_participants(ids):
    """Menghapus banyak peserta sekaligus berdasarkan daftar ID"""
    if not ids or not isinstance(ids, list):
        return 0
    valid_ids = [int(i) for i in ids if str(i).isdigit() or isinstance(i, int)]
    if not valid_ids:
        return 0
    placeholders = ', '.join(['?'] * len(valid_ids))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM participants WHERE id IN ({placeholders})", valid_ids)
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count

def update_participant(participant_id, nim_nip, nama_lengkap, no_hp, institusi, pekerjaan, status=None):
    """Memperbarui informasi data peserta (Fitur Edit)"""
    participant = get_participant_by_id(participant_id)
    if not participant:
        return None
        
    cleaned_nim = nim_nip.strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Cek apakah No. Identitas baru sudah dipakai oleh peserta lain
    cursor.execute("SELECT id FROM participants WHERE nim_nip = ? AND id != ?", (cleaned_nim, participant_id))
    existing_other = cursor.fetchone()
    if existing_other:
        conn.close()
        return {"error": "DUPLICATE_NIM", "message": f'Nomor Identitas "{cleaned_nim}" sudah digunakan oleh peserta lain.'}
        
    current_status = status if status in ['pendaftar', 'peserta'] else participant['status']
    attended_at = participant['attended_at']
    if current_status == 'peserta' and not attended_at:
        attended_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elif current_status == 'pendaftar':
        attended_at = None

    cursor.execute("""
        UPDATE participants
        SET nim_nip = ?, nama_lengkap = ?, no_hp = ?, institusi = ?, pekerjaan = ?, status = ?, attended_at = ?
        WHERE id = ?
    """, (cleaned_nim, nama_lengkap.strip(), no_hp.strip(), institusi.strip(), pekerjaan.strip(), current_status, attended_at, participant_id))
    conn.commit()
    
    cursor.execute("SELECT * FROM participants WHERE id = ?", (participant_id,))
    updated = dict(cursor.fetchone())
    conn.close()
    return updated

def get_participants(status=None, search=None, pekerjaan=None):
    """
    Mengambil data peserta dengan filter status ('pendaftar'/'peserta'),
    kata kunci pencarian (NIM/NIP, Nama, Institusi, QR), dan jenis pekerjaan.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM participants WHERE 1=1"
    params = []
    
    if status in ['pendaftar', 'peserta']:
        query += " AND status = ?"
        params.append(status)
        
    if pekerjaan and pekerjaan != 'Semua':
        query += " AND pekerjaan = ?"
        params.append(pekerjaan)
        
    if search:
        search_pattern = f"%{search.strip()}%"
        query += " AND (nim_nip LIKE ? OR nama_lengkap LIKE ? OR no_hp LIKE ? OR institusi LIKE ? OR qr_code LIKE ?)"
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern, search_pattern])
        
    if status == 'peserta':
        query += " ORDER BY attended_at DESC, id DESC"
    else:
        query += " ORDER BY created_at DESC, id DESC"
        
    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_stats():
    """Mengambil ringkasan statistik kehadiran seminar dan per rincian pekerjaan peserta hadir"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM participants")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM participants WHERE status = 'pendaftar'")
    pendaftar_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM participants WHERE status = 'peserta'")
    peserta_count = cursor.fetchone()[0]

    # Rincian peserta hadir per pekerjaan/profesi
    cursor.execute("SELECT pekerjaan, COUNT(*) FROM participants WHERE status = 'peserta' GROUP BY pekerjaan")
    job_rows = cursor.fetchall()
    job_counts = {row['pekerjaan']: row[1] for row in job_rows}
    
    conn.close()
    
    attendance_rate = round((peserta_count / total * 100), 1) if total > 0 else 0
    
    return {
        "total": total,
        "pendaftar": pendaftar_count,
        "peserta": peserta_count,
        "attendance_rate": attendance_rate,
        "peserta_by_job": {
            "mhs_s1": job_counts.get("Mahasiswa S1", 0) + job_counts.get("Mahasiswa", 0),
            "mhs_s2": job_counts.get("Mahasiswa S2", 0),
            "dosen": job_counts.get("Dosen", 0),
            "praktisi": job_counts.get("Praktisi", 0),
            "lainnya": job_counts.get("Lainnya", 0)
        }
    }
