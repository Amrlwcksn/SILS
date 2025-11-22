import os
import mysql.connector
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# === LOAD ENVIRONMENT ===
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# === KONFIG DATABASE ===
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root123',
    'database': 'silslaravel'
}

# === COMMAND /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    await update.message.reply_text(
        f"Halo {user.first_name or 'Orang Tua'} 👋\n"
        f"Selamat datang di *SILS Notification Bot*\n\n"
        f"Kirim *NIS Siswa* untuk mendaftar.\n"
        f"Contoh: `2201345`",
        parse_mode="Markdown"
    )

# === HANDLE TEKS (NIS) ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id

    # Harus angka → validasi input
    if not text.isdigit():
        await update.message.reply_text("⚠️ Kirim hanya NIS (angka) ya!")
        return

    nis = text

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # === CEK CHAT ID SUDAH DIPAKAI ===
        cursor.execute("""
            SELECT nama_ortu FROM tabel_ortu WHERE telegram_id = %s
        """, (chat_id,))
        existing_chat = cursor.fetchone()

        if existing_chat:
            await update.message.reply_text(
                f"🔒 Akun Telegram ini sudah terhubung dengan orang tua *{existing_chat['nama_ortu']}*.\n"
                f"Jika ingin mengganti akun, hubungi admin sekolah."
            )
            return

        # === CARI DATA SISWA BERDASARKAN NIS ===
        cursor.execute("""
            SELECT 
                s.id AS siswa_id,
                s.NIS,
                s.nama AS nama_siswa,
                s.id_ortu,
                o.nama_ortu,
                o.telegram_id
            FROM tabel_siswa s
            JOIN tabel_ortu o ON s.id_ortu = o.id_ortu
            WHERE s.NIS = %s
        """, (nis,))
        siswa = cursor.fetchone()

        if not siswa:
            await update.message.reply_text("❌ NIS tidak ditemukan di database.")
            return

        # === ORANG TUA SUDAH TERHUBUNG DENGAN TELEGRAM LAIN? ===
        if siswa["telegram_id"] is not None:
            await update.message.reply_text(
                f"🔐 Orang tua *{siswa['nama_ortu']}* sudah terhubung dengan Telegram lain.\n"
                f"Untuk mengganti nomor, silakan hubungi admin."
            )
            return

        # === SIMPAN CHAT ID ===
        cursor.execute("""
            UPDATE tabel_ortu SET telegram_id = %s WHERE id_ortu = %s
        """, (chat_id, siswa["id_ortu"]))
        conn.commit()

        await update.message.reply_text(
            f"✅ Pendaftaran berhasil!\n"
            f"Akun ini kini terhubung dengan orang tua dari *{siswa['nama_siswa']}*.\n"
            f"Anda akan menerima notifikasi presensi otomatis.",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Terjadi kesalahan: {e}")

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# === MAIN ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot Telegram SILS siap menerima pesan…")
    app.run_polling()

if __name__ == "__main__":
    main()
