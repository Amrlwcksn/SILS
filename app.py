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
    'password': 'root123',
    'database': 'silslaravel'
}

# === TELEGRAM ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def kirim_pesan_telegram(chat_id, pesan):
    try:
        resp = requests.post(TELEGRAM_API_URL, data={
            'chat_id': chat_id,
            'text': pesan,
            'parse_mode': 'Markdown'
        })
        print("Telegram sent:", resp.text)
    except Exception as e:
        print("Telegram error:", e)


@app.route('/api/rfid', methods=['POST'])
def rfid_data():
    data = request.get_json()
    uid = data.get('uid', '').strip()

    if not uid:
        return jsonify({"status": "error", "message": "UID kosong"}), 400

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # === CARI SISWA BERDASARKAN UID ===
        cursor.execute("SELECT * FROM tabel_siswa WHERE UID = %s", (uid,))
        siswa = cursor.fetchone()

        if not siswa:
            return jsonify({"status": "unknown", "message": "UID tidak ditemukan"}), 404

        siswa_id = siswa['id']
        nama_siswa = siswa['nama']
        id_ortu = siswa['id_ortu']

        # === HITUNG STATUS ===
        batas = time(7, 15)
        now = datetime.now()

        if now.time() <= batas:
            status = "Tepat Waktu"
            status_emoji = "✅ Tepat Waktu"
        else:
            status = "Terlambat"
            status_emoji = "⚠️ Terlambat"

        # === INSERT PRESENSI ===
        cursor.execute("""
            INSERT INTO tabel_presensi (siswa_id, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s)
        """, (siswa_id, status, now, now))
        conn.commit()

        # === CARI ORANG TUA ===
        cursor.execute("SELECT * FROM tabel_ortu WHERE id_ortu = %s", (id_ortu,))
        ortu = cursor.fetchone()

        if ortu and ortu.get('telegram_id'):
            pesan = (
                f"👋 Halo {ortu['nama_ortu']}!\n\n"
                f"Ananda *{nama_siswa}* telah melakukan presensi.\n"
                f"🕒 Waktu: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Status: {status_emoji}"
            )
            kirim_pesan_telegram(ortu['telegram_id'], pesan)

        return jsonify({"status": "ok", "message": f"Presensi tercatat untuk {nama_siswa}"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


# === GET PRESENSI ===
@app.route('/api/presensi', methods=['GET'])
def get_presensi():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT 
                p.id_presensi,
                s.NIS,
                s.nama,
                s.kelas,
                p.status,
                p.created_at
            FROM tabel_presensi p
            JOIN tabel_siswa s ON p.siswa_id = s.id
            ORDER BY p.created_at DESC
        """)
        data = cursor.fetchall()

        return jsonify({"status": "success", "total": len(data), "data": data})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
