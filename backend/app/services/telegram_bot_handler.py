import os
import sqlite3
import logging
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# Import dependencies
from app.api.auth import hash_password, verify_password
from app.services.yfinance_service import get_db_connection
from app.core.logger import logger

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if TELEGRAM_BOT_TOKEN:
    bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
else:
    bot = None

# Simple in-memory state dictionary for registration flows
user_states = {}

def get_user_by_chat_id(chat_id):
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE telegram_chat_id = ?", (chat_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"[TELEGRAM DB] Error get_user_by_chat_id: {e}")
        return None

def get_user_by_email(email):
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"[TELEGRAM DB] Error get_user_by_email: {e}")
        return None

def get_user_portfolios(user_id):
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM portfolios WHERE user_id = ?", (user_id,))
        portfolios = cursor.fetchall()
        conn.close()
        return [dict(p) for p in portfolios]
    except Exception as e:
        logger.error(f"[TELEGRAM DB] Error get_user_portfolios: {e}")
        return []

def create_portfolio(user_id, portfolio_type, initial_balance):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO portfolios (user_id, name, portfolio_type, initial_balance, balance, total_profit) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, f"Portofolio {portfolio_type.capitalize()}", portfolio_type, initial_balance, initial_balance, 0.0)
        )
        conn.commit()
        logger.info(f"[TELEGRAM DB] Berhasil membuat portofolio {portfolio_type} untuk user {user_id}")
    except Exception as e:
        logger.error(f"[TELEGRAM DB] Error creating portfolio: {e}")
    finally:
        conn.close()

def build_main_menu(user_id):
    portfolios = get_user_portfolios(user_id)
    has_saham = any(p['portfolio_type'] == 'saham' for p in portfolios)
    has_forex = any(p['portfolio_type'] == 'forex' for p in portfolios)

    markup = InlineKeyboardMarkup()
    
    if has_saham:
        markup.add(InlineKeyboardButton("📈 Saham (Aktif)", callback_data="status_saham_on"))
    else:
        markup.add(InlineKeyboardButton("➕ Tambah Portofolio Saham", callback_data="add_saham"))
        
    if has_forex:
        markup.add(InlineKeyboardButton("💱 Forex (Aktif)", callback_data="status_forex_on"))
    else:
        markup.add(InlineKeyboardButton("➕ Tambah Portofolio Forex", callback_data="add_forex"))
        
    markup.add(InlineKeyboardButton("🌐 Buka Web App", url="https://misc4.siberhub.id"))
    return markup

if bot:
    @bot.message_handler(commands=['start', 'menu'])
    def send_welcome(message):
        chat_id = message.chat.id
        logger.info(f"[TELEGRAM BOT] Menerima command {message.text} dari chat_id: {chat_id}")
        
        # Reset state jika user mengetik /start di tengah-tengah proses
        if chat_id in user_states:
            del user_states[chat_id]
            logger.info(f"[TELEGRAM BOT] State di-reset untuk chat_id: {chat_id}")
            
        try:
            user = get_user_by_chat_id(chat_id)
            
            if user:
                logger.info(f"[TELEGRAM BOT] User sudah terdaftar: {user['username']}")
                markup = build_main_menu(user['id'])
                bot.send_message(
                    chat_id, 
                    f"Halo {user['username']}! Selamat datang di Dashboard Swingmaster AI.\n\nSinyal Anda akan dikirim ke chat ini. Silakan atur portofolio Anda:", 
                    reply_markup=markup
                )
            else:
                logger.info(f"[TELEGRAM BOT] User baru, menampilkan menu registrasi.")
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🆕 Daftar Akun Baru", callback_data="register_new"))
                markup.add(InlineKeyboardButton("🔗 Hubungkan Akun Web", callback_data="link_account"))
                bot.send_message(
                    chat_id,
                    "Selamat datang di Swingmaster AI! 🤖\n\nUntuk menerima sinyal trading, Anda harus menghubungkan Telegram Anda dengan akun Web Swingmaster.",
                    reply_markup=markup
                )
        except Exception as e:
            logger.error(f"[TELEGRAM BOT] Error di send_welcome: {e}")
            bot.send_message(chat_id, "Terjadi kesalahan internal. Silakan coba lagi nanti.")

    @bot.callback_query_handler(func=lambda call: True)
    def handle_query(call):
        chat_id = call.message.chat.id
        data = call.data
        logger.info(f"[TELEGRAM BOT] Menerima callback_query: {data} dari chat_id: {chat_id}")
        
        try:
            if data == "register_new":
                user_states[chat_id] = {'step': 'reg_username'}
                bot.send_message(chat_id, "Silakan ketik **Username** yang ingin Anda gunakan:", parse_mode="Markdown")
                
            elif data == "link_account":
                user_states[chat_id] = {'step': 'link_email'}
                bot.send_message(chat_id, "Silakan ketik **Email** akun Web Anda:", parse_mode="Markdown")
                
            elif data == "add_saham":
                user = get_user_by_chat_id(chat_id)
                if user:
                    create_portfolio(user['id'], 'saham', 100000000.0)
                    bot.answer_callback_query(call.id, "Portofolio Saham berhasil dibuat!")
                    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=build_main_menu(user['id']))
                    
            elif data == "add_forex":
                user = get_user_by_chat_id(chat_id)
                if user:
                    create_portfolio(user['id'], 'forex', 5000.0)
                    bot.answer_callback_query(call.id, "Portofolio Forex berhasil dibuat!")
                    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=build_main_menu(user['id']))
                    
            elif data in ["status_saham_on", "status_forex_on"]:
                bot.answer_callback_query(call.id, "Sinyal ini sudah aktif.")
        except Exception as e:
            logger.error(f"[TELEGRAM BOT] Error di handle_query: {e}")
            bot.send_message(chat_id, "Terjadi kesalahan saat memproses permintaan.")

    @bot.message_handler(func=lambda message: True)
    def handle_text(message):
        chat_id = message.chat.id
        text = message.text.strip()
        
        if chat_id not in user_states:
            # Abaikan pesan teks jika tidak sedang dalam state registrasi
            return
            
        state = user_states[chat_id]
        step = state.get('step')
        logger.info(f"[TELEGRAM BOT] Menangani input teks untuk state '{step}' dari chat_id: {chat_id}")
        
        try:
            # --- Flow Registrasi ---
            if step == 'reg_username':
                state['username'] = text
                state['step'] = 'reg_email'
                bot.send_message(chat_id, "Bagus! Sekarang silakan ketik **Email** Anda:", parse_mode="Markdown")
                
            elif step == 'reg_email':
                state['email'] = text
                state['step'] = 'reg_password'
                bot.send_message(chat_id, "Terakhir, silakan ketik **Password** rahasia Anda.\n\n_Pesan ini akan terekam di riwayat chat Anda._", parse_mode="Markdown")
                
            elif step == 'reg_password':
                username = state['username']
                email = state['email']
                password = text
                hashed_pw = hash_password(password)
                
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "INSERT INTO users (username, email, password, telegram_chat_id, telegram_username) VALUES (?, ?, ?, ?, ?)",
                        (username, email, hashed_pw, chat_id, message.from_user.username)
                    )
                    user_id = cursor.lastrowid
                    conn.commit()
                    logger.info(f"[TELEGRAM BOT] Registrasi sukses untuk username: {username}")
                    
                    bot.send_message(chat_id, "✅ Pendaftaran berhasil! Anda sekarang bisa login di Web App.\n\n⚠️ **PERINGATAN PENTING**: Mohon segera **hapus pesan password Anda** di atas demi keamanan akun Anda.")
                    
                    markup = build_main_menu(user_id)
                    bot.send_message(chat_id, "Silakan pilih sinyal market yang ingin diaktifkan (membuat portofolio baru):", reply_markup=markup)
                    
                except sqlite3.IntegrityError as e:
                    logger.warning(f"[TELEGRAM BOT] Registrasi gagal (IntegrityError): {e}")
                    bot.send_message(chat_id, "❌ Gagal mendaftar. Username atau email mungkin sudah digunakan. Silakan ketik /start untuk mencoba lagi.")
                finally:
                    conn.close()
                    del user_states[chat_id]
                    
            # --- Flow Link Account ---
            elif step == 'link_email':
                state['email'] = text
                state['step'] = 'link_password'
                bot.send_message(chat_id, "Silakan ketik **Password** akun Anda:", parse_mode="Markdown")
                
            elif step == 'link_password':
                email = state['email']
                password = text
                
                user = get_user_by_email(email)
                if user:
                    # Logging tanpa mengekspos password
                    logger.info(f"[TELEGRAM BOT] Mencoba menghubungkan akun untuk email: {email}")
                    if verify_password(password, user['password']):
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        try:
                            # Cek apakah chat_id sudah digunakan user lain
                            cursor.execute("SELECT id FROM users WHERE telegram_chat_id = ? AND id != ?", (chat_id, user['id']))
                            conflict = cursor.fetchone()
                            if conflict:
                                # Hapus chat_id dari user lama
                                cursor.execute("UPDATE users SET telegram_chat_id = NULL WHERE telegram_chat_id = ?", (chat_id,))
                                logger.info(f"[TELEGRAM BOT] Menghapus chat_id dari user lama ID {conflict['id']}")
                                
                            cursor.execute(
                                "UPDATE users SET telegram_chat_id = ?, telegram_username = ? WHERE id = ?",
                                (chat_id, message.from_user.username, user['id'])
                            )
                            conn.commit()
                            logger.info(f"[TELEGRAM BOT] Berhasil menghubungkan akun {user['username']}")
                            bot.send_message(chat_id, f"✅ Berhasil terhubung dengan akun {user['username']}!\n\n⚠️ Mohon segera hapus pesan password Anda di atas demi keamanan.")
                            markup = build_main_menu(user['id'])
                            bot.send_message(chat_id, "Berikut adalah pengaturan portofolio Anda:", reply_markup=markup)
                        except Exception as e:
                            logger.error(f"[TELEGRAM BOT] Link update error: {e}")
                            bot.send_message(chat_id, "Terjadi kesalahan internal saat menghubungkan akun.")
                        finally:
                            conn.close()
                    else:
                        logger.warning(f"[TELEGRAM BOT] Password salah untuk email: {email}")
                        bot.send_message(chat_id, "❌ Password salah. Silakan ketik /start untuk mencoba lagi.")
                else:
                    logger.warning(f"[TELEGRAM BOT] Email tidak ditemukan: {email}")
                    bot.send_message(chat_id, "❌ Email tidak ditemukan. Silakan ketik /start untuk mencoba lagi.")
                    
                del user_states[chat_id]
        except Exception as e:
            logger.error(f"[TELEGRAM BOT] Error di handle_text: {e}")
            bot.send_message(chat_id, "Terjadi kesalahan sistem saat memproses input Anda. Silakan ketik /start ulang.")
            if chat_id in user_states:
                del user_states[chat_id]

def start_polling():
    if bot:
        logger.info("[TELEGRAM BOT] Memulai background polling...")
        bot.infinity_polling()
    else:
        logger.warning("[TELEGRAM BOT] Token tidak diset, bot tidak dijalankan.")

def run_bot_in_thread():
    thread = threading.Thread(target=start_polling, daemon=True)
    thread.start()
