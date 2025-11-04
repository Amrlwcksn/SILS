from flask import Flask, request, jsonify
import mysql.connector
from datetime import datetime, time
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# === KONFIG DATABASE ===
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': ''
}

# === KONFIG TELEGRAM ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def kirim_pesan_telegram(chat_id, pesan):
    """Fungsi kirim pesan ke Telegram"""
    try:
        payload = {
            'chat_id': chat_id,
            'text': pesan,
            'parse_mode': 'Markdown'
        }
        response = requests.post(TELEGRAM_API_URL, data=payload)
        if response.status_code == 200:
            print(f"📩 Pesan terkirim!")
        else:
            print(f"⚠️ Gagal kirim pesan: {response.text}")
    except Exception as e:
        print("❌ Error kirim telegram:", e)


@app.route('/api/rfid', methods=['POST'])
def rfid_data():
    data = request.get_json()
    uid = data.get('uid', '').strip()

    if not uid:
        return jsonify({"status": "error", "message": "UID kosong"}), 400

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # 1️⃣ CARI SISWA BERDASARKAN UID
        cursor.execute("SELECT * FROM tabel_siswa WHERE uid_tag = %s", (uid,))
        siswa = cursor.fetchone()
        print("DEBUG SISWA:", siswa)
        
        if siswa:
            id_siswa = siswa['id_siswa']
            nama_siswa = siswa['nama_siswa']
            id_ortu = siswa['id_ortu']

            # 2️⃣ CATAT PRESENSI DI tabel_absensi
            waktu_sekarang = datetime.now()
            waktu_tap = waktu_sekarang.strftime("%Y-%m-%d %H:%M:%S")

            batas_waktu = time(7,15)

            if waktu_sekarang.time()<= batas_waktu:
                status = "✅Tepat Waktu"
            else:
                status = "⚠️Terlambat"

            cursor.execute("""
                INSERT INTO tabel_presensi (id_siswa, waktu, status)
                VALUES (%s, %s, %s)
            """, (id_siswa, waktu_tap, status))
            conn.commit()

            print(f"Presensi tercatat: {nama_siswa}({status})")

            # 3️⃣ AMBIL DATA ORANG TUA UNTUK KIRIM NOTIFIKASI
            cursor.execute("SELECT nama_ortu, telegram_id FROM tabel_ortu WHERE id_ortu = %s", (id_ortu,))
            ortu = cursor.fetchone()

            if ortu and ortu['telegram_id']:
                pesan = (
                    f"👋 Halo {ortu['nama_ortu']}!\n\n"
                    f"Ananda *{nama_siswa}* baru saja melakukan presensi pada:\n"
                    f"🕓 {waktu_tap}\n\n"
                    f"Status: Hadir di sekolah. {status}"
                )
                kirim_pesan_telegram(ortu['telegram_id'], pesan)
            else:
                print("⚠️ Orang tua tidak memiliki Telegram ID atau tidak ditemukan.")

            return jsonify({"status": "ok", "message": f"Presensi tercatat untuk {nama_siswa}"})

        else:
            print(f"⚠️ UID tidak dikenali: {uid}")
            return jsonify({"status": "unknown", "message": "UID tidak terdaftar"})

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"status": "error", "message": str(e)})

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


@app.route('/api/presensi', methods=['GET'])
def get_presensi():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Ambil parameter dari query string (kalau ada)
        nama = request.args.get('nama', '').strip()
        tanggal = request.args.get('tanggal', '').strip()

        # Base query
        query = """
            SELECT 
                p.id_presensi,
                s.nama_siswa,
                s.uid_tag,
                p.waktu,
                p.status
            FROM tabel_presensi p
            JOIN tabel_siswa s ON p.id_siswa = s.id_siswa
        """
        params = []

        # Tambahkan filter sesuai parameter
        conditions = []
        if nama:
            conditions.append("s.nama_siswa LIKE %s")
            params.append(f"%{nama}%")
        if tanggal:
            conditions.append("DATE(p.waktu) = %s")
            params.append(tanggal)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY p.waktu DESC"

        cursor.execute(query, params)
        data = cursor.fetchall()

        return jsonify({
            "status": "success",
            "total": len(data),
            "filters": {
                "nama": nama or None,
                "tanggal": tanggal or None
            },
            "data": data
        }), 200

    except Exception as e:
        print("❌ Error ambil presensi:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
