"""
Skrip untuk mengisi data dummy awal (pendaftar & peserta) untuk pengujian.
Jalankan: .venv/bin/python seed_data.py
"""
import database

database.init_db()

dummy_registrants = [
    ("2110511001", "Ahmad Fauzi", "Universitas Indonesia", "Mahasiswa"),
    ("198501012010121001", "Dr. Siti Rahmawati, M.Kom.", "Institut Teknologi Bandung", "Dosen"),
    ("197903152005012002", "Prof. Bambang Supriyanto", "Universitas Gadjah Mada", "Dosen"),
    ("PR-99201", "Kevin Sanjaya, S.T.", "PT Digital Inovasi Asia", "Praktisi"),
    ("2210512045", "Nadia Putri Maharani", "Universitas Diponegoro", "Mahasiswa"),
    ("L-88301", "Rina Kusuma Dewi", "Yayasan Pendidikan Nusantara", "Lainnya")
]

print("🌱 Menambahkan data simulasi seminar...")
created_participants = []
for nim, nama, inst, job in dummy_registrants:
    p = database.register_participant(nim, nama, inst, job)
    created_participants.append(p)
    print(f"  + Terdaftar: {nama} ({job}) -> QR Code: {p['qr_code']} [Status: {p['status']}]")

# Simulasikan 2 orang sudah scan absensi (menjadi Peserta)
print("\n📷 Mensimulasikan pemindaian absensi 2 orang...")
for p in created_participants[:2]:
    res = database.mark_attendance(p['qr_code'])
    print(f"  ✓ Absen Berhasil: {res['data']['nama_lengkap']} -> Status sekarang: {res['data']['status']} [Waktu: {res['data']['attended_at']}]")

stats = database.get_stats()
print(f"\n📊 Ringkasan Statistik:")
print(f"  - Total Registrasi : {stats['total']}")
print(f"  - Pendaftar (Belum): {stats['pendaftar']}")
print(f"  - Peserta (Hadir)  : {stats['peserta']}")
print(f"  - Kehadiran        : {stats['attendance_rate']}%\n")
print("✅ Selesai! Buka http://127.0.0.1:5001/admin untuk melihat data di panel admin.")
