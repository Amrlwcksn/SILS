from flask import Flask, request, jsonify
import mysql.connector
from datetime import datetime, time
import requests
import os
from dotenv import load_dotenv

# === LOAD ENVIRONMENT ===
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
    """Kirim pesan ke Telegram"""
    try:
        payload = {
            'chat_id': chat_id,
            'text': pesan,
            'parse_mode': 'Markdown'
        }
        response = requests.post(TELEGRAM_API_URL, data=payload)
        if response.status_code == 200:
            print("📩 Telegram terkirim")
        else:
            print(f"⚠️ Gagal kirim Telegram: {response.text}")
    except Exception as e:
        print("❌ Error kirim Telegram:", e)


@app.route('/api/rfid', methods=['POST'])
def rfid_data():
    """Menerima UID RFID dari ESP32 dan catat presensi"""
    data = request.get_json()
    uid = data.get('uid', '').strip()

    if not uid:
        return jsonify({"status": "error", "message": "UID kosong"}), 400

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # === Cari siswa berdasarkan UID ===
        cursor.execute("SELECT * FROM tabel_siswa WHERE UID = %s", (uid,))
        siswa = cursor.fetchone()

        if not siswa:
            print(f"⚠️ UID tidak terdaftar: {uid}")
            return jsonify({"status": "unknown", "message": "UID tidak ditemukan"}), 404

        nis = siswa['NIS']
        nama_siswa = siswa['nama_siswa']
        id_ortu = siswa['id_ortu']

        # === Hitung status presensi ===
        waktu_sekarang = datetime.now()
        waktu_tap = waktu_sekarang.strftime("%Y-%m-%d %H:%M:%S")
        batas_waktu = time(7, 15)  # jam 07:15

        if waktu_sekarang.time() <= batas_waktu:
            status_db = "Tepat Waktu"
            status_emoji = "✅ Tepat Waktu"
        else:
            status_db = "Terlambat"
            status_emoji = "⚠️ Terlambat"

        # === Simpan ke database ===
        cursor.execute("""
            INSERT INTO tabel_presensi (NIS, waktu, status)
            VALUES (%s, %s, %s)
        """, (nis, waktu_tap, status_db))
        conn.commit()

        print(f"✅ Presensi tercatat: {nama_siswa} ({status_db})")

        # === Kirim notifikasi ke orang tua ===
        cursor.execute("SELECT nama_ortu, telegram_id FROM tabel_ortu WHERE id_ortu = %s", (id_ortu,))
        ortu = cursor.fetchone()

        if ortu and ortu['telegram_id']:
            pesan = (
                f"👋 Halo {ortu['nama_ortu']}!\n\n"
                f"Ananda *{nama_siswa}* baru saja melakukan presensi.\n"
                f"🕒 Waktu: {waktu_tap}\n"
                f"Status: {status_emoji}"
            )
            kirim_pesan_telegram(ortu['telegram_id'], pesan)
        else:
            print("⚠️ Orang tua tidak memiliki Telegram ID atau tidak ditemukan")

        return jsonify({"status": "ok", "message": f"Presensi tercatat untuk {nama_siswa}"})

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# === API GET PRESENSI ===
@app.route('/api/presensi', methods=['GET'])
def get_presensi():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Ambil semua data presensi
        query = """
            SELECT p.id_presensi, s.NIS, s.nama_siswa, s.kelas, p.waktu, p.status
            FROM tabel_presensi p
            JOIN tabel_siswa s USING(NIS)
            ORDER BY p.waktu DESC
        """
        cursor.execute(query)
        data = cursor.fetchall()

        return jsonify({"status": "success", "total": len(data), "data": data})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
