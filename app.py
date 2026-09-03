import os
import io
import csv
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_file, Response, session, redirect, url_for
import qrcode
from qrcode.image.pil import PilImage

import database
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
# Dukungan Reverse Proxy (Nginx / Apache subpath / header X-Forwarded-Prefix & Proto)
class PrefixMiddleware:
    def __init__(self, wsgi_app, prefix='/absenpeserta'):
        self.wsgi_app = wsgi_app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        path_info = environ.get('PATH_INFO', '')
        x_prefix = environ.get('HTTP_X_FORWARDED_PREFIX', '')
        
        if path_info.startswith(self.prefix):
            environ['PATH_INFO'] = path_info[len(self.prefix):] or '/'
            environ['SCRIPT_NAME'] = self.prefix
        elif x_prefix:
            environ['SCRIPT_NAME'] = x_prefix
        elif environ.get('HTTP_X_FORWARDED_HOST') or environ.get('HTTP_X_FORWARDED_FOR') or environ.get('HTTP_X_REAL_IP'):
            # Permintaan diteruskan dari Reverse Proxy Apache/Nginx (Production)
            environ['SCRIPT_NAME'] = self.prefix

        return self.wsgi_app(environ, start_response)

app.wsgi_app = PrefixMiddleware(ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1))

app.config['SECRET_KEY'] = 'seminar-secret-key-2026'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Inisialisasi Database
database.init_db()

ACTIVE_PORT = 5001

def get_local_ip():
    """Mendeteksi IP Address lokal di jaringan LAN / Wi-Fi"""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'

def find_available_port(start_port=5001, max_tries=20):
    """Mencari port bebas secara otomatis jika port default sedang digunakan program lain"""
    import socket
    if os.environ.get('PORT'):
        return int(os.environ.get('PORT'))
    for p in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(('0.0.0.0', p))
                return p
            except OSError:
                continue
    return start_port

def admin_required(f):
    """Decorator untuk membatasi akses khusus sesi admin yang valid"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Akses ditolak. Silakan login terlebih dahulu.'}), 401
            return redirect(url_for('console'))
        return f(*args, **kwargs)
    return decorated_function

def superadmin_required(f):
    """Decorator untuk membatasi akses khusus sesi Super Admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return jsonify({'success': False, 'message': 'Akses ditolak. Silakan login terlebih dahulu.'}), 401
        if session.get('admin_role') != 'superadmin':
            return jsonify({'success': False, 'message': 'Akses ditolak. Fitur ini hanya untuk Super Admin.'}), 403
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_settings():
    """Menyediakan variabel global pengaturan acara, IP lokal, dan status login ke seluruh template"""
    global ACTIVE_PORT
    settings = database.get_all_settings()
    local_ip = get_local_ip()
    port = ACTIVE_PORT
    
    # Pastikan file logo diakses melalui subpath prefix (misal /absenpeserta/static/uploads/...)
    logo_val = settings.get('event_logo', '')
    if logo_val and logo_val.startswith('/static/'):
        prefix = request.script_root or ''
        settings['event_logo'] = f"{prefix}{logo_val}"

    return {
        'event_settings': settings,
        'local_ip': local_ip,
        'server_port': port,
        'local_url': f"http://{local_ip}:{port}",
        'is_admin': session.get('admin_logged_in', False),
        'admin_id': session.get('admin_id'),
        'admin_username': session.get('admin_username', 'admin'),
        'admin_name': session.get('admin_name', 'Super Admin'),
        'admin_role': session.get('admin_role', 'admin'),
        'is_superadmin': session.get('admin_role') == 'superadmin'
    }

@app.route('/')
def index():
    """Halaman Pendaftaran Seminar (Publik Peserta)"""
    return render_template('register.html')

@app.route('/console')
def console():
    """Halaman Console Admin (menampilkan Form Login jika belum login, atau Dashboard jika sudah login)"""
    if not session.get('admin_logged_in'):
        return render_template('login.html')
    return render_template('admin.html')

@app.route('/admin')
def admin():
    """Redirect /admin ke /console"""
    return redirect(url_for('console'))

@app.route('/login')
def login():
    """Redirect /login ke /console"""
    return redirect(url_for('console'))

@app.route('/ticket/<qr_code>')
def ticket(qr_code):
    """Halaman E-Ticket Digital Peserta"""
    participant = database.get_participant_by_qr(qr_code)
    if not participant:
        return render_template('ticket.html', participant=None, error="Tiket QR Code tidak ditemukan.")
    return render_template('ticket.html', participant=participant, error=None)

# ======================= AUTH & API ENDPOINTS =======================

@app.route('/api/login', methods=['POST'])
def api_login():
    """Memverifikasi username & password admin"""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username dan password wajib diisi!'}), 400

    admin_user = database.verify_admin(username, password)
    if admin_user:
        session['admin_logged_in'] = True
        session['admin_id'] = admin_user['id']
        session['admin_username'] = admin_user['username']
        session['admin_name'] = admin_user['nama']
        session['admin_role'] = admin_user['role']
        database.update_admin_last_login(admin_user['id'])
        return jsonify({
            'success': True,
            'message': f'Selamat datang, {admin_user["nama"]}!',
            'user': {
                'id': admin_user['id'],
                'username': admin_user['username'],
                'nama': admin_user['nama'],
                'role': admin_user['role']
            }
        })
    else:
        return jsonify({'success': False, 'message': 'Username atau password admin salah!'}), 401

@app.route('/api/logout', methods=['POST', 'GET'])
def api_logout():
    """Keluar dari sesi admin console"""
    session.clear()
    if request.method == 'GET':
        return redirect(url_for('console'))
    return jsonify({'success': True, 'message': 'Logout berhasil.'})

@app.route('/api/admin/change-credentials', methods=['POST'])
@admin_required
def api_change_credentials():
    """Mengubah password akun admin yang sedang login"""
    data = request.get_json() or {}
    current_pass = data.get('current_password', '').strip()
    new_pass = data.get('new_password', '').strip()
    new_nama = data.get('nama', '').strip()

    admin_id = session.get('admin_id')
    current_user = database.get_admin_by_id(admin_id) if admin_id else None
    
    if not current_user:
        return jsonify({'success': False, 'message': 'User tidak ditemukan.'}), 404

    # Verifikasi password saat ini
    valid = database.verify_admin(current_user['username'], current_pass)
    if not valid:
        return jsonify({'success': False, 'message': 'Password saat ini salah!'}), 400

    if new_nama:
        database.update_admin_profile(admin_id, nama=new_nama)
        session['admin_name'] = new_nama

    if new_pass:
        database.update_admin_password(admin_id, new_pass)

    return jsonify({'success': True, 'message': 'Kredensial berhasil diperbarui!'})

# ======================= SUPER ADMIN MANAGEMENT ENDPOINTS =======================

@app.route('/api/admin/users', methods=['GET'])
@superadmin_required
def api_get_admins():
    """Mengambil daftar seluruh user admin (Khusus Super Admin)"""
    admins = database.get_all_admins()
    return jsonify({'success': True, 'data': admins})

@app.route('/api/admin/users', methods=['POST'])
@superadmin_required
def api_create_admin():
    """Membuat user admin baru (Khusus Super Admin)"""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    nama = data.get('nama', '').strip()
    role = data.get('role', 'admin').strip()

    if not username or not password or not nama:
        return jsonify({'success': False, 'message': 'Username, nama, dan password wajib diisi!'}), 400

    new_admin = database.create_admin(username, password, nama, role)
    if not new_admin:
        return jsonify({'success': False, 'message': 'Username sudah digunakan, pilih username lain.'}), 400

    return jsonify({'success': True, 'message': f'Admin {nama} berhasil dibuat!', 'data': new_admin})

@app.route('/api/admin/users/<int:admin_id>/reset-password', methods=['POST'])
@superadmin_required
def api_reset_admin_password(admin_id):
    """Mengatur/Reset password admin manapun (Khusus Super Admin)"""
    data = request.get_json() or {}
    new_password = data.get('new_password', '').strip()

    if not new_password:
        return jsonify({'success': False, 'message': 'Password baru wajib diisi!'}), 400

    target_admin = database.get_admin_by_id(admin_id)
    if not target_admin:
        return jsonify({'success': False, 'message': 'User admin tidak ditemukan.'}), 404

    success = database.update_admin_password(admin_id, new_password)
    if success:
        return jsonify({'success': True, 'message': f'Password untuk {target_admin["nama"]} ({target_admin["username"]}) berhasil diperbarui!'})
    return jsonify({'success': False, 'message': 'Gagal memperbarui password.'}), 500

@app.route('/api/admin/users/<int:admin_id>/edit', methods=['POST'])
@superadmin_required
def api_edit_admin_profile(admin_id):
    """Mengubah nama, username, atau role admin (Khusus Super Admin)"""
    data = request.get_json() or {}
    nama = data.get('nama', '').strip()
    username = data.get('username', '').strip()
    role = data.get('role', '').strip()

    target_admin = database.get_admin_by_id(admin_id)
    if not target_admin:
        return jsonify({'success': False, 'message': 'User admin tidak ditemukan.'}), 404

    # Proteksi: Jangan hapus status superadmin jika diri sendiri sedang login
    if admin_id == session.get('admin_id') and role and role != 'superadmin':
        return jsonify({'success': False, 'message': 'Anda tidak dapat menurunkan role akun Anda sendiri.'}), 400

    success = database.update_admin_profile(admin_id, nama=nama, username=username, role=role if role else None)
    if success:
        return jsonify({'success': True, 'message': 'Data admin berhasil diperbarui!'})
    return jsonify({'success': False, 'message': 'Gagal memperbarui data admin (kemungkinan username sudah dipakai).'}), 400

@app.route('/api/admin/users/<int:admin_id>', methods=['DELETE'])
@superadmin_required
def api_delete_admin(admin_id):
    """Menghapus user admin (Khusus Super Admin)"""
    if admin_id == session.get('admin_id'):
        return jsonify({'success': False, 'message': 'Anda tidak dapat menghapus akun Anda sendiri!'}), 400

    target = database.get_admin_by_id(admin_id)
    if not target:
        return jsonify({'success': False, 'message': 'User tidak ditemukan.'}), 404

    database.delete_admin(admin_id)
    return jsonify({'success': True, 'message': f'Admin {target["nama"]} berhasil dihapus.'})

import html
import time

# In-Memory Rate Limiter untuk mencegah spam / flood pendaftaran
registration_history = {}

def is_rate_limited(ip_address, max_requests=5, window_seconds=60):
    """Mencegah spam pendaftaran dengan membatasi maksimal 5 pendaftaran per menit per IP"""
    now = time.time()
    timestamps = registration_history.get(ip_address, [])
    # Hapus timestamp yang sudah lebih dari window_seconds
    valid_timestamps = [t for t in timestamps if now - t < window_seconds]
    if len(valid_timestamps) >= max_requests:
        registration_history[ip_address] = valid_timestamps
        return True
    valid_timestamps.append(now)
    registration_history[ip_address] = valid_timestamps
    return False

@app.route('/api/register', methods=['POST'])
def api_register():
    """Menerima pendaftaran peserta baru dengan proteksi Rate Limit, Anti-Bot Honeypot, XSS Sanitization, dan Cek Duplikasi"""
    data = request.get_json() or {}
    
    # 1. Anti-Bot Honeypot: Jika field bot terisi, tolak langsung
    if data.get('website_url') or data.get('hp_secondary'):
        return jsonify({
            'success': False,
            'message': 'Permintaan pendaftaran ditolak oleh sistem keamanan.'
        }), 400

    # 2. Rate Limiting: Maksimal 5 registrasi per 60 detik per IP
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1')
    if is_rate_limited(client_ip, max_requests=5, window_seconds=60):
        return jsonify({
            'success': False,
            'message': 'Terlalu banyak permintaan pendaftaran. Mohon tunggu 1 menit sebelum mencoba lagi.'
        }), 429
    
    raw_nim = data.get('nim_nip', '').strip()
    raw_nama = data.get('nama_lengkap', '').strip()
    raw_no_hp = data.get('no_hp', '').strip()
    raw_institusi = data.get('institusi', '').strip()
    raw_pekerjaan = data.get('pekerjaan', '').strip()
    
    # 3. Validasi Keberadaan Input
    if not raw_nim or not raw_nama or not raw_no_hp or not raw_institusi or not raw_pekerjaan:
        return jsonify({
            'success': False,
            'message': 'Semua kolom formulir (No. Identitas, Nama Lengkap, No. HP / WhatsApp, Institusi, Pekerjaan) wajib diisi!'
        }), 400
        
    # 4. Validasi Panjang Karakter (Mencegah Buffer/Payload Abuse)
    if len(raw_nim) < 3 or len(raw_nim) > 30:
        return jsonify({
            'success': False,
            'message': 'No. Identitas (NIM/NIP/NIDN/NUPTK/KTP) harus berisi antara 3 hingga 30 karakter!'
        }), 400

    if len(raw_nama) < 2 or len(raw_nama) > 100:
        return jsonify({
            'success': False,
            'message': 'Nama Lengkap harus berisi antara 2 hingga 100 karakter!'
        }), 400

    if len(raw_no_hp) < 8 or len(raw_no_hp) > 20:
        return jsonify({
            'success': False,
            'message': 'Nomor HP / WhatsApp harus berisi antara 8 hingga 20 karakter!'
        }), 400

    if len(raw_institusi) < 2 or len(raw_institusi) > 120:
        return jsonify({
            'success': False,
            'message': 'Nama Institusi harus berisi antara 2 hingga 120 karakter!'
        }), 400
        
    valid_jobs = ['Mahasiswa', 'Dosen', 'Praktisi', 'Lainnya']
    if raw_pekerjaan not in valid_jobs:
        return jsonify({
            'success': False,
            'message': f'Pekerjaan harus salah satu dari: {", ".join(valid_jobs)}'
        }), 400

    # 5. XSS Sanitization: Escape karakter khusus HTML (<, >, &, ", ')
    nim_nip = html.escape(raw_nim)
    nama_lengkap = html.escape(raw_nama)
    no_hp = html.escape(raw_no_hp)
    institusi = html.escape(raw_institusi)
    pekerjaan = html.escape(raw_pekerjaan)

    # 6. Deteksi Duplikasi Nomor Identitas: Jika sudah ada, langsung kembalikan data pendaftaran sebelumnya
    existing = database.get_participant_by_nim(nim_nip)
    if existing:
        return jsonify({
            'success': True,
            'is_duplicate': True,
            'code': 'DUPLICATE_NIM',
            'message': f'No. Identitas "{nim_nip}" sudah pernah terdaftar atas nama {existing["nama_lengkap"]}.',
            'data': existing
        }), 200
        
    try:
        participant = database.register_participant(nim_nip, nama_lengkap, no_hp, institusi, pekerjaan)
        return jsonify({
            'success': True,
            'message': 'Pendaftaran berhasil!',
            'data': participant
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Gagal mendaftarkan peserta: {str(e)}'
        }), 500

@app.route('/api/scan', methods=['POST'])
@admin_required
def api_scan():
    """
    Menerima hasil scan QR code dari kamera admin.
    Memvalidasi dan mengubah status dari pendaftar menjadi peserta.
    """
    data = request.get_json() or {}
    qr_code = data.get('qr_code', '').strip()
    
    if not qr_code:
        return jsonify({
            'success': False,
            'code': 'EMPTY_CODE',
            'message': 'Kode QR tidak boleh kosong.'
        }), 400
        
    result = database.mark_attendance(qr_code)
    return jsonify(result)

@app.route('/api/participants', methods=['GET'])
@admin_required
def api_participants():
    """Mengambil data peserta berdasarkan status (pendaftar/peserta), pencarian, dan pekerjaan"""
    status = request.args.get('status')
    search = request.args.get('search')
    pekerjaan = request.args.get('pekerjaan')
    
    rows = database.get_participants(status=status, search=search, pekerjaan=pekerjaan)
    return jsonify({
        'success': True,
        'count': len(rows),
        'data': rows
    })

@app.route('/api/stats', methods=['GET'])
@admin_required
def api_stats():
    """Mengambil data statistik jumlah pendaftar, peserta hadir, dan persentase"""
    stats = database.get_stats()
    return jsonify({
        'success': True,
        'stats': stats
    })

@app.route('/api/participant/<int:participant_id>/toggle', methods=['POST'])
@admin_required
def api_toggle_status(participant_id):
    """Mengubah status pendaftar <-> peserta secara manual"""
    updated = database.toggle_status(participant_id)
    if not updated:
        return jsonify({'success': False, 'message': 'Peserta tidak ditemukan.'}), 404
        
    return jsonify({
        'success': True,
        'message': f'Status berhasil diubah menjadi {updated["status"].capitalize()}',
        'data': updated
    })

@app.route('/api/participant/<int:participant_id>', methods=['GET'])
@admin_required
def api_get_participant(participant_id):
    """Mengambil data 1 orang peserta berdasarkan ID untuk keperluan edit"""
    participant = database.get_participant_by_id(participant_id)
    if not participant:
        return jsonify({'success': False, 'message': 'Peserta tidak ditemukan.'}), 404
    return jsonify({
        'success': True,
        'data': participant
    })

@app.route('/api/participant/<int:participant_id>/edit', methods=['POST', 'PUT'])
@app.route('/api/participant/<int:participant_id>', methods=['PUT'])
@admin_required
def api_edit_participant(participant_id):
    """Memperbarui informasi data peserta (Fitur Edit)"""
    data = request.get_json() or {}
    raw_nim = data.get('nim_nip', '').strip()
    raw_nama = data.get('nama_lengkap', '').strip()
    raw_no_hp = data.get('no_hp', '').strip()
    raw_institusi = data.get('institusi', '').strip()
    raw_pekerjaan = data.get('pekerjaan', '').strip()
    raw_status = data.get('status', '').strip().lower()

    if not raw_nim or not raw_nama or not raw_institusi or not raw_pekerjaan:
        return jsonify({
            'success': False,
            'message': 'Kolom No. Identitas, Nama Lengkap, Institusi, dan Pekerjaan wajib diisi!'
        }), 400

    if len(raw_nim) < 3 or len(raw_nim) > 30:
        return jsonify({'success': False, 'message': 'No. Identitas harus berisi antara 3 hingga 30 karakter!'}), 400

    if len(raw_nama) < 2 or len(raw_nama) > 100:
        return jsonify({'success': False, 'message': 'Nama Lengkap harus berisi antara 2 hingga 100 karakter!'}), 400

    if raw_no_hp and (len(raw_no_hp) < 8 or len(raw_no_hp) > 20):
        return jsonify({'success': False, 'message': 'Nomor HP / WA harus berisi antara 8 hingga 20 karakter!'}), 400

    valid_jobs = ['Mahasiswa', 'Dosen', 'Praktisi', 'Lainnya']
    if raw_pekerjaan not in valid_jobs:
        return jsonify({'success': False, 'message': f'Pekerjaan harus salah satu dari: {", ".join(valid_jobs)}'}), 400

    nim_nip = html.escape(raw_nim)
    nama_lengkap = html.escape(raw_nama)
    no_hp = html.escape(raw_no_hp) if raw_no_hp else ''
    institusi = html.escape(raw_institusi)
    pekerjaan = html.escape(raw_pekerjaan)
    status = raw_status if raw_status in ['pendaftar', 'peserta'] else None

    result = database.update_participant(participant_id, nim_nip, nama_lengkap, no_hp, institusi, pekerjaan, status)
    if not result:
        return jsonify({'success': False, 'message': 'Peserta tidak ditemukan atau gagal diperbarui.'}), 404
        
    if isinstance(result, dict) and 'error' in result:
        return jsonify({'success': False, 'message': result['message']}), 400

    return jsonify({
        'success': True,
        'message': 'Data peserta berhasil diperbarui!',
        'data': result
    })

@app.route('/api/participant/<int:participant_id>', methods=['DELETE'])
@admin_required
def api_delete_participant(participant_id):
    """Menghapus data pendaftar/peserta"""
    deleted = database.delete_participant(participant_id)
    if not deleted:
        return jsonify({'success': False, 'message': 'Data tidak ditemukan atau gagal dihapus.'}), 404
        
    return jsonify({
        'success': True,
        'message': 'Data berhasil dihapus.'
    })

@app.route('/api/participants/bulk-delete', methods=['POST'])
@admin_required
def api_bulk_delete_participants():
    """Menghapus banyak peserta sekaligus (Bulk Delete)"""
    data = request.get_json() or {}
    ids = data.get('ids', [])
    if not ids or not isinstance(ids, list):
        return jsonify({'success': False, 'message': 'Tidak ada data peserta yang dipilih untuk dihapus.'}), 400

    deleted_count = database.bulk_delete_participants(ids)
    return jsonify({
        'success': True,
        'message': f'Berhasil menghapus {deleted_count} data peserta terpilih.',
        'deleted_count': deleted_count
    })

@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    """Mengambil data pengaturan nama acara & logo saat ini"""
    settings = database.get_all_settings()
    return jsonify({
        'success': True,
        'settings': settings
    })

@app.route('/api/settings', methods=['POST'])
@admin_required
def api_update_settings():
    """Memperbarui nama acara dan mengunggah logo acara"""
    event_name = request.form.get('event_name', '').strip()
    if event_name:
        database.set_setting('event_name', event_name)

    if 'event_info' in request.form:
        event_info = request.form.get('event_info', '').strip()
        database.set_setting('event_info', event_info)

    # Periksa apakah ada file logo yang diunggah
    if 'event_logo' in request.files:
        file = request.files['event_logo']
        if file and file.filename != '':
            ext = os.path.splitext(file.filename)[1].lower()
            allowed_extensions = ['.png', '.jpg', '.jpeg', '.svg', '.webp', '.ico']
            if ext not in allowed_extensions:
                return jsonify({
                    'success': False,
                    'message': 'Format logo tidak didukung! Gunakan PNG, JPG, JPEG, SVG, atau WEBP.'
                }), 400

            filename = f"event_logo_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Simpan relative URL
            logo_url = f"/static/uploads/{filename}"
            database.set_setting('event_logo', logo_url)

    updated_settings = database.get_all_settings()
    return jsonify({
        'success': True,
        'message': 'Pengaturan acara berhasil disimpan!',
        'settings': updated_settings
    })

@app.route('/api/settings/reset-logo', methods=['POST'])
@admin_required
def api_reset_logo():
    """Mereset logo acara kembali ke logo default sistem"""
    database.set_setting('event_logo', '')
    return jsonify({
        'success': True,
        'message': 'Logo acara berhasil direset ke default.',
        'settings': database.get_all_settings()
    })

@app.route('/api/network-info')
def api_network_info():
    """Mengembalikan informasi IP jaringan lokal dan link akses"""
    port = int(os.environ.get('PORT', 5001))
    local_ip = get_local_ip()
    prefix = request.script_root.rstrip('/')
    base_lan = f"http://{local_ip}:{port}{prefix}"
    base_local = f"http://127.0.0.1:{port}{prefix}"
    public_base = request.host_url.rstrip('/') + prefix
    
    # Jika diakses lewat domain/proxy (ada script_root atau bukan localhost)
    is_behind_domain = bool(request.script_root or (request.host and not request.host.startswith('127.0.0.1') and not request.host.startswith('localhost') and not request.host.startswith('0.0.0.0')))
    
    return jsonify({
        'local_ip': local_ip,
        'port': port,
        'prefix': prefix,
        'register_url_local': base_local,
        'register_url_lan': public_base if is_behind_domain else base_lan,
        'admin_url_local': f"{base_local}/console",
        'admin_url_lan': f"{public_base}/console" if is_behind_domain else f"{base_lan}/console",
    })

@app.route('/api/qr-url.png')
def api_qr_url():
    """Menghasilkan QR Code untuk URL (misal link registrasi lokal / server)"""
    url_data = request.args.get('data', '').strip()
    if not url_data:
        port = int(os.environ.get('PORT', 5001))
        local_ip = get_local_ip()
        prefix = request.script_root.rstrip('/')
        is_behind_domain = bool(request.script_root or (request.host and not request.host.startswith('127.0.0.1') and not request.host.startswith('localhost') and not request.host.startswith('0.0.0.0')))
        if is_behind_domain:
            url_data = request.host_url.rstrip('/') + prefix
        else:
            url_data = f"http://{local_ip}:{port}{prefix}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(url_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    return send_file(buffer, mimetype='image/png')

@app.route('/api/qr/<qr_code>.png')
def api_qr_image(qr_code):
    """Menghasilkan file gambar PNG QR Code secara dinamis"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(qr_code.strip().upper())
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#1e293b", back_color="#ffffff")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='image/png',
        as_attachment=False,
        download_name=f"qr_semnasretro_{qr_code}.png"
    )

@app.route('/api/export-csv')
@admin_required
def export_csv():
    """Mengekspor daftar pendaftar/peserta ke file CSV dengan format UTF-8 (kompatibel Excel)"""
    status_filter = request.args.get('status') # 'pendaftar', 'peserta', or all
    rows = database.get_participants(status=status_filter)
    
    output = io.StringIO()
    # BOM untuk Excel agar encoding UTF-8 terbaca dengan rapi di Windows/Mac
    output.write('\ufeff')
    writer = csv.writer(output)
    
    writer.writerow(['No', 'Kode QR', 'No. Identitas (NIM/NIP/NIDN/NUPTK)', 'Nama Lengkap', 'No. HP / WA', 'Institusi', 'Pekerjaan', 'Status', 'Waktu Pendaftaran', 'Waktu Hadir'])
    
    for idx, row in enumerate(rows, start=1):
        status_label = 'Peserta (Hadir)' if row['status'] == 'peserta' else 'Pendaftar (Belum Hadir)'
        writer.writerow([
            idx,
            row['qr_code'],
            row['nim_nip'],
            row['nama_lengkap'],
            row['no_hp'] or '-',
            row['institusi'],
            row['pekerjaan'],
            status_label,
            row['created_at'],
            row['attended_at'] or '-'
        ])
        
    filename = f"daftar_seminar_{status_filter or 'semua'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@app.route('/api/import-csv', methods=['POST'])
@admin_required
def import_csv():
    """Mengimpor data pendaftar & peserta keseluruhan dari file CSV backup"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'File CSV tidak ditemukan dalam permintaan.'}), 400
        
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'success': False, 'message': 'Silakan pilih file CSV yang ingin diimpor.'}), 400
        
    overwrite = request.form.get('overwrite', 'true').lower() in ['true', '1', 'yes']

    try:
        raw_bytes = file.read()
        text = None
        for enc in ['utf-8-sig', 'utf-8', 'latin-1']:
            try:
                text = raw_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
                
        if text is None:
            return jsonify({'success': False, 'message': 'Format encoding file tidak didukung.'}), 400

        stream = io.StringIO(text)
        csv_reader = csv.reader(stream)
        
        rows = []
        for line in csv_reader:
            if line and any(field.strip() for field in line):
                rows.append([f.strip() for f in line])
                
        if not rows:
            return jsonify({'success': False, 'message': 'File CSV kosong atau tidak memiliki baris data.'}), 400

        first_row = [c.lower() for c in rows[0]]
        has_header = False
        header_map = {}
        
        known_headers = {
            'qr_code': ['kode qr', 'qr_code', 'qr', 'kode', 'qrcode'],
            'nim_nip': ['no. identitas (nim/nip/nidn/nuptk)', 'no. identitas', 'no identitas', 'nomor identitas', 'nim / nip', 'nim/nip', 'nim_nip', 'nim', 'nip', 'nidn', 'nuptk', 'nik', 'ktp', 'nomor induk'],
            'nama_lengkap': ['nama lengkap', 'nama_lengkap', 'nama', 'fullname', 'name'],
            'no_hp': ['no. hp / wa', 'no hp / wa', 'no. hp', 'no hp', 'nomor hp', 'no telepon', 'telepon', 'whatsapp', 'no wa', 'phone', 'mobile', 'no_hp'],
            'institusi': ['institusi', 'instansi', 'universitas', 'kampus', 'perusahaan', 'institution'],
            'pekerjaan': ['pekerjaan', 'profesi', 'kategori', 'job', 'occupation'],
            'status': ['status', 'status kehadiran', 'kehadiran', 'attendance'],
            'created_at': ['waktu pendaftaran', 'created_at', 'tanggal daftar', 'waktu daftar', 'created'],
            'attended_at': ['waktu hadir', 'attended_at', 'waktu absen', 'waktu scan', 'attended']
        }
        
        for col_idx, col_name in enumerate(first_row):
            cleaned_col = col_name.strip().lower()
            for key, aliases in known_headers.items():
                if cleaned_col in aliases:
                    header_map[key] = col_idx
                    has_header = True
                    break

        data_rows = rows[1:] if has_header else rows
        
        if not data_rows:
            return jsonify({'success': False, 'message': 'Tidak ada baris data peserta dalam file CSV.'}), 400

        inserted_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for row_num, row in enumerate(data_rows, start=2 if has_header else 1):
            if not row or not any(row):
                continue
                
            try:
                if has_header and 'nim_nip' in header_map and 'nama_lengkap' in header_map:
                    qr_code = row[header_map['qr_code']] if 'qr_code' in header_map and header_map['qr_code'] < len(row) else ''
                    nim_nip = row[header_map['nim_nip']] if header_map['nim_nip'] < len(row) else ''
                    nama_lengkap = row[header_map['nama_lengkap']] if header_map['nama_lengkap'] < len(row) else ''
                    no_hp = row[header_map['no_hp']] if 'no_hp' in header_map and header_map['no_hp'] < len(row) else ''
                    institusi = row[header_map['institusi']] if 'institusi' in header_map and header_map['institusi'] < len(row) else '-'
                    pekerjaan = row[header_map['pekerjaan']] if 'pekerjaan' in header_map and header_map['pekerjaan'] < len(row) else 'Lainnya'
                    status = row[header_map['status']] if 'status' in header_map and header_map['status'] < len(row) else 'pendaftar'
                    created_at = row[header_map['created_at']] if 'created_at' in header_map and header_map['created_at'] < len(row) else None
                    attended_at = row[header_map['attended_at']] if 'attended_at' in header_map and header_map['attended_at'] < len(row) else None
                else:
                    if len(row) >= 10 and row[0].isdigit():
                        # [No, QR, NIM, Nama, NoHP, Institusi, Pekerjaan, Status, WaktuDaftar, WaktuHadir]
                        qr_code = row[1]
                        nim_nip = row[2]
                        nama_lengkap = row[3]
                        no_hp = row[4]
                        institusi = row[5]
                        pekerjaan = row[6]
                        status = row[7]
                        created_at = row[8]
                        attended_at = row[9]
                    elif len(row) >= 9 and row[0].isdigit():
                        # Legacy 9 cols with No: [No, QR, NIM, Nama, Institusi, Pekerjaan, Status, WaktuDaftar, WaktuHadir]
                        qr_code = row[1]
                        nim_nip = row[2]
                        nama_lengkap = row[3]
                        no_hp = ''
                        institusi = row[4]
                        pekerjaan = row[5]
                        status = row[6]
                        created_at = row[7]
                        attended_at = row[8]
                    elif len(row) >= 9:
                        # [QR, NIM, Nama, NoHP, Institusi, Pekerjaan, Status, WaktuDaftar, WaktuHadir]
                        qr_code = row[0]
                        nim_nip = row[1]
                        nama_lengkap = row[2]
                        no_hp = row[3]
                        institusi = row[4]
                        pekerjaan = row[5]
                        status = row[6]
                        created_at = row[7]
                        attended_at = row[8]
                    elif len(row) >= 8:
                        # Legacy 8 cols: [QR, NIM, Nama, Institusi, Pekerjaan, Status, WaktuDaftar, WaktuHadir]
                        qr_code = row[0]
                        nim_nip = row[1]
                        nama_lengkap = row[2]
                        no_hp = ''
                        institusi = row[3]
                        pekerjaan = row[4]
                        status = row[5]
                        created_at = row[6]
                        attended_at = row[7]
                    elif len(row) >= 4:
                        qr_code = ''
                        nim_nip = row[0]
                        nama_lengkap = row[1]
                        no_hp = row[2] if len(row) > 4 else ''
                        institusi = row[3] if len(row) > 4 else row[2]
                        pekerjaan = row[4] if len(row) > 5 else (row[3] if len(row) > 3 else 'Lainnya')
                        status = row[5] if len(row) > 5 else 'pendaftar'
                        created_at = row[6] if len(row) > 6 else None
                        attended_at = row[7] if len(row) > 7 else None
                    else:
                        error_count += 1
                        continue

                if not nim_nip or not nama_lengkap:
                    error_count += 1
                    continue
                    
                nim_nip = html.escape(nim_nip[:30])
                nama_lengkap = html.escape(nama_lengkap[:100])
                no_hp = html.escape((no_hp or '')[:20])
                institusi = html.escape((institusi or '-')[:120])
                pekerjaan = html.escape((pekerjaan or 'Lainnya')[:50])

                res = database.upsert_participant_from_csv(
                    qr_code=qr_code,
                    nim_nip=nim_nip,
                    nama_lengkap=nama_lengkap,
                    no_hp=no_hp,
                    institusi=institusi,
                    pekerjaan=pekerjaan,
                    status=status,
                    created_at=created_at,
                    attended_at=attended_at,
                    overwrite=overwrite
                )
                
                if res == 'inserted':
                    inserted_count += 1
                elif res == 'updated':
                    updated_count += 1
                else:
                    skipped_count += 1
            except Exception:
                error_count += 1
                continue

        total_processed = inserted_count + updated_count + skipped_count
        msg = f"Impor data CSV selesai! {inserted_count} data baru ditambahkan, {updated_count} data diperbarui."
        if skipped_count > 0:
            msg += f" ({skipped_count} data dilewati)."
            
        return jsonify({
            'success': True,
            'message': msg,
            'summary': {
                'total': total_processed,
                'inserted': inserted_count,
                'updated': updated_count,
                'skipped': skipped_count,
                'errors': error_count
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Gagal memproses file CSV: {str(e)}'}), 500

if __name__ == '__main__':
    ACTIVE_PORT = find_available_port(start_port=5001)
    local_ip = get_local_ip()
    
    print("\n" + "="*65)
    print("🚀 SISTEM ABSEN SEMINAR AKTIF & TERKONEKSI KE JARINGAN LOKAL")
    print("="*65)
    print(f"📍 Akses Publik (Pendaftar):")
    print(f"   • Form Pendaftaran : http://127.0.0.1:{ACTIVE_PORT}")
    print(f"   • Via Wi-Fi/HP     : http://{local_ip}:{ACTIVE_PORT}")
    print(f"\n🔐 Akses Khusus Panitia (Admin Console):")
    print(f"   • Login Console    : http://127.0.0.1:{ACTIVE_PORT}/console")
    print(f"   • Via Wi-Fi/HP     : http://{local_ip}:{ACTIVE_PORT}/console")
    print("="*65 + "\n")
    app.run(host='0.0.0.0', port=ACTIVE_PORT, debug=False)
