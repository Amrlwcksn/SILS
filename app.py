from flask import Flask, request, jsonify
import mysql.connector
from datetime import datetime
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
            waktu_tap = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO tabel_presensi (id_siswa, waktu, status)
                VALUES (%s, %s, %s)
            """, (id_siswa, waktu_tap, "Hadir"))
            conn.commit()

            print(f"✅ Presensi tercatat: {nama_siswa} (UID: {uid})")

            # 3️⃣ AMBIL DATA ORANG TUA UNTUK KIRIM NOTIFIKASI
            cursor.execute("SELECT nama_ortu, telegram_id FROM tabel_ortu WHERE id_ortu = %s", (id_ortu,))
            ortu = cursor.fetchone()

            if ortu and ortu['telegram_id']:
                pesan = (
                    f"👋 Halo {ortu['nama_ortu']}!\n\n"
                    f"Ananda *{nama_siswa}* baru saja melakukan presensi pada:\n"
                    f"🕓 {waktu_tap}\n\n"
                    f"Status: ✅ Hadir di sekolah."
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
