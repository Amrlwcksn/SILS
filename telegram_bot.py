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
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "sils_db"
}

# === COMMAND /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    await update.message.reply_text(
        f"Halo {user.first_name or 'Orang Tua'} 👋\n"
        f"Selamat datang di *SILS Notification Bot*\n\n"
        f"Kirim ID SISWA anak Anda untuk mendaftar.\n"
        f"Contoh: `12345`",
        parse_mode="Markdown"
    )

# === HANDLE TEKS (ID SISWA) ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id

    # validasi input
    if not text.isdigit():
        await update.message.reply_text("⚠️ Kirim hanya angka ID SISWA ya!")
        return

    id_siswa = int(text)

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # cari orang tua dari siswa
        cursor.execute("""
            SELECT o.id_ortu, o.nama_ortu
            FROM tabel_siswa s
            JOIN tabel_ortu o ON s.id_ortu = o.id_ortu
            WHERE s.id_siswa = %s
        """, (id_siswa,))
        ortu = cursor.fetchone()

        if ortu:
            cursor.execute("UPDATE tabel_ortu SET telegram_id = %s WHERE id_ortu = %s",
                           (chat_id, ortu["id_ortu"]))
            conn.commit()
            await update.message.reply_text(
                f"✅ Berhasil! Telegram Anda sudah terhubung dengan akun *{ortu['nama_ortu']}*.\n"
                f"Sekarang Anda akan menerima notifikasi setiap anak presensi di sekolah.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ ID SISWA tidak ditemukan di sistem.")

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

    print("🤖 Bot Telegram SILS (v21.x) siap menerima pesan…")
    app.run_polling()

if __name__ == "__main__":
    main()
