# Sistem Absensi Seminar (QR Code)

Aplikasi web sistem registrasi dan absensi seminar modern berbasis **Python (Flask)**, **SQLite**, dan **Tailwind CSS**.

---

## 🎯 Fitur Utama

1. **Formulir Pendaftaran Publik (`/`)**:
   - Khusus untuk peserta: tidak ada tombol atau menu login admin yang terlihat oleh peserta.
   - Menampilkan identitas dan logo resmi acara yang dapat dikonfigurasi.
   - Kolom: **NIM / NIP**, **Nama Lengkap**, **Institusi**, **Pekerjaan** (Dropdown: *Mahasiswa, Dosen, Praktisi, Lainnya*).
   - Menghasilkan **QR Code 10 Karakter Acak Unik** untuk setiap pendaftar.
   - **Himbauan Penting**: Pendaftar diingatkan untuk segera mengambil tangkapan layar (*screenshot*) atau mengunduh QR Code sebagai tiket kehadiran.
   - Status awal tersimpan sebagai **Pendaftar** (belum hadir).

2. **Login & Admin Console (`/console`)**:
   - Sistem login admin privat dan aman dengan **5 Akun Bawaan**:
     - 👑 **Super Admin**: Username `admin` | Password `admin123`
     - 👤 **Petugas 1**: Username `petugas1` | Password `admin123`
     - 👤 **Petugas 2**: Username `petugas2` | Password `admin123`
     - 👤 **Petugas 3**: Username `petugas3` | Password `admin123`
     - 👤 **Petugas 4**: Username `petugas4` | Password `admin123`
   - Seluruh route & API panel admin dilindungi oleh autentikasi sesi (*session protection*).
   - **4 Menu Utama Console**:
     - **1. Scan Absensi**: Pemindai QR Code live camera + audio feedback + opsi ambil foto / manual code.
     - **2. Informasi Peserta**: Tab **Pendaftar** (belum hadir) vs **Peserta** (hadir), pencarian, filter, live stats, **Export CSV**, serta **Impor Data dari CSV** *(restore backup keseluruhan pendaftar & peserta)*.
     - **3. Pengaturan Acara**: Atur nama acara, upload logo acara (*Live Preview*), dan ganti password akun pribadi.
     - **4. Manajemen Admin (Khusus Super Admin)**: Kelola akun admin panitia, buat admin baru, edit profil, dan **atur/reset password untuk semua user admin**.
   - Tombol **Logout** untuk keluar dari sesi.

3. **Halaman E-Ticket Digital (`/ticket/<kode_qr>`)**:
   - Halaman tiket digital mandiri yang siap cetak (*print-friendly*).

---

## 🚀 Cara Menjalankan Aplikasi

### 1. Jalankan Aplikasi
Buka terminal di folder project, lalu jalankan:
```bash
.venv/bin/python app.py
```
Aplikasi akan aktif di:
- **Komputer Ini**: `http://127.0.0.1:5001`
- **Jaringan Wi-Fi / HP (LAN)**: `http://<IP_KOMPUTER>:5001` (misal: `http://10.10.200.230:5001`)

> 💡 **Fitur Akses Wi-Fi**: Tersedia tombol **"Akses Jaringan HP/Wi-Fi"** di navigasi atas yang menampilkan QR Code link pendaftaran agar peserta di ruangan dapat langsung scan menggunakan HP mereka.

### 2. (Opsional) Mengisi Data Percobaan
Jika ingin langsung mencoba dengan beberapa data simulasi:
```bash
.venv/bin/python seed_data.py
```

### 3. Menjalankan Unit Test
```bash
.venv/bin/python test_app.py
```

---

## 📂 Struktur Direktori

```
├── app.py              # Server Flask & API endpoints
├── database.py         # SQLite database & data queries
├── seed_data.py        # Skrip data simulasi
├── test_app.py         # Automated unit test suite
├── requirements.txt    # Daftar dependensi Python
├── seminar.db          # Database SQLite
├── templates/
│   ├── base.html       # Base template layout
│   ├── register.html   # Form pendaftaran & modal QR
│   ├── admin.html      # Panel admin (Scan & Info Peserta)
│   └── ticket.html     # Halaman E-ticket digital
```
