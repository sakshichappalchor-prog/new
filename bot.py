#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import qrcode
from io import BytesIO
import time
import random
import os
import hashlib
import string
from datetime import datetime, timedelta
import threading

# ========== CONFIGURATION ==========
BOT_TOKEN = "8656155838:AAEdk1vkwExsI_iW_HSmheKSdZBDEbYbC4s"
ADMIN_IDS = [8310174062, 8399267744]
# ===================================

bot = telebot.TeleBot(BOT_TOKEN)

# ========== DATABASE ==========
token_hash = hashlib.md5(BOT_TOKEN.encode()).hexdigest()[:10]
DB_NAME = f"bot_{token_hash}.db"
print(f"📀 Database: {DB_NAME}")

conn = sqlite3.connect(DB_NAME, check_same_thread=False)

def db_query(query, params=()):
    c = conn.cursor()
    c.execute(query, params)
    result = c.fetchall()
    c.close()
    return result

def db_execute(query, params=()):
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    c.close()

def db_insert(query, params=()):
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    last_id = c.lastrowid
    c.close()
    return last_id

# ========== CREATE ALL TABLES ==========
def ensure_schema():
    db_execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price INTEGER,
        reward TEXT
    )''')
    
    db_execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        joined TEXT
    )''')
    
    db_execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product TEXT,
        amount INTEGER,
        ssid TEXT,
        status TEXT,
        time TEXT
    )''')
    
    db_execute('''CREATE TABLE IF NOT EXISTS daily_payments (
        date TEXT PRIMARY KEY,
        count INTEGER,
        total_amount INTEGER
    )''')
    
    db_execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    db_execute('''CREATE TABLE IF NOT EXISTS claim_offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        upi TEXT,
        amount INTEGER,
        caption TEXT,
        active INTEGER
    )''')
    
    db_execute('''CREATE TABLE IF NOT EXISTS auto_msgs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        msg TEXT,
        interval INTEGER,
        active INTEGER
    )''')
    
    db_execute('''CREATE TABLE IF NOT EXISTS demo_settings (
        id INTEGER PRIMARY KEY,
        link TEXT,
        text TEXT
    )''')
    
    db_execute('''CREATE TABLE IF NOT EXISTS temp_payments (
        user_id INTEGER,
        payment_id INTEGER,
        product TEXT,
        amount INTEGER,
        product_id INTEGER,
        order_id TEXT,
        expiry TEXT
    )''')
    
    db_execute("INSERT OR IGNORE INTO settings VALUES ('upi', 'yourupi@okhdfcbank')")
    db_execute("INSERT OR IGNORE INTO settings VALUES ('welcome_image', '')")
    db_execute("INSERT OR IGNORE INTO settings VALUES ('welcome_text', '🌸 Welcome! Choose an option:')")
    db_execute("INSERT OR IGNORE INTO settings VALUES ('how_to_pay_video', '')")
    db_execute("INSERT OR IGNORE INTO demo_settings VALUES (1, 'https://t.me/telegram', 'Join our channel for updates!')")
    
    if not db_query("SELECT 1 FROM products LIMIT 1"):
        db_execute("INSERT INTO products (name, price, reward) VALUES ('🔍 DEMO (Preview Only)', 0, 'This is a demo product. No payment required. Upgrade to real plan!')")
        db_execute("INSERT INTO products (name, price, reward) VALUES ('✨ 1 Month Premium', 99, '🎉 You got 1 Month Premium!')")
        db_execute("INSERT INTO products (name, price, reward) VALUES ('✨ 3 Months Premium', 199, '🎉 You got 3 Months Premium!')")
        db_execute("INSERT INTO products (name, price, reward) VALUES ('✨ 6 Months Premium', 299, '🎉 You got 6 Months Premium!')")
        print("✅ Test products added")

ensure_schema()

# ========== HELPER FUNCTIONS ==========
def add_user(uid, name):
    if not db_query("SELECT 1 FROM users WHERE user_id=?", (uid,)):
        db_execute("INSERT INTO users VALUES (?,?,?)", (uid, name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

def get_setting(key):
    res = db_query("SELECT value FROM settings WHERE key=?", (key,))
    return res[0][0] if res else ""

def update_setting(key, val):
    db_execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, val))

def is_admin(user_id):
    return user_id in ADMIN_IDS

def generate_order_id():
    ts = datetime.now().strftime("%y%m%d%H%M%S")
    rnd = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ORD-{ts}-{rnd}"

def split_long_message(text, limit=4000):
    if len(text) <= limit:
        return [text]
    parts = []
    while len(text) > limit:
        split_at = text.rfind('\n', 0, limit)
        if split_at == -1:
            split_at = limit
        parts.append(text[:split_at])
        text = text[split_at:].lstrip()
    if text:
        parts.append(text)
    return parts

def update_daily_payment(amount):
    today = datetime.now().strftime("%Y-%m-%d")
    existing = db_query("SELECT count, total_amount FROM daily_payments WHERE date=?", (today,))
    if existing:
        new_count = existing[0][0] + 1
        new_total = existing[0][1] + amount
        db_execute("UPDATE daily_payments SET count=?, total_amount=? WHERE date=?", (new_count, new_total, today))
    else:
        db_execute("INSERT INTO daily_payments VALUES (?, ?, ?)", (today, 1, amount))

# ========== USER COMMANDS ==========
@bot.message_handler(commands=['start', 'premium'])
def start_cmd(m):
    add_user(m.from_user.id, m.from_user.username or "User")
    welcome_img = get_setting('welcome_image')
    welcome_txt = get_setting('welcome_text')
    demo_res = db_query("SELECT link FROM demo_settings WHERE id=1")
    demo_link = demo_res[0][0] if demo_res else "https://t.me/telegram"
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("💎 GET PREMIUM", callback_data="premium"))
    kb.add(InlineKeyboardButton("🎮 DEMO CHANNEL", url=demo_link))
    
    video_url = get_setting('how_to_pay_video')
    if video_url:
        kb.add(InlineKeyboardButton("📖 HOW TO PAY", url=video_url))
    
    if welcome_img:
        try:
            bot.send_photo(m.chat.id, welcome_img, caption=welcome_txt, reply_markup=kb)
        except:
            bot.send_message(m.chat.id, welcome_txt, reply_markup=kb)
    else:
        bot.send_message(m.chat.id, welcome_txt, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "premium")
def premium_cb(call):
    prods = db_query("SELECT id, name, price FROM products")
    if not prods:
        bot.send_message(call.message.chat.id, "❌ No products. Contact admin.")
        return
    kb = InlineKeyboardMarkup(row_width=1)
    for p in prods:
        kb.add(InlineKeyboardButton(f"📦 {p[1]} - ₹{p[2]}", callback_data=f"buy_{p[0]}"))
    kb.add(InlineKeyboardButton("🔙 BACK", callback_data="back_to_start"))
    bot.send_message(call.message.chat.id, "🛒 *AVAILABLE PLANS*\nChoose a plan:", reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def buy_cb(call):
    try:
        pid = int(call.data.split("_")[1])
        prod = db_query("SELECT name, price, reward FROM products WHERE id=?", (pid,))
        if not prod:
            bot.answer_callback_query(call.id, "Error!")
            return
        name, price, reward = prod[0]
        if price == 0:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🔙 BACK", callback_data="premium"))
            bot.send_message(call.message.chat.id, f"🔍 *DEMO PRODUCT*\n\n{reward}\n\nThis is just a preview. To get real premium plan, please select a paid plan.", reply_markup=kb, parse_mode="Markdown")
            bot.answer_callback_query(call.id)
            return
        upi = get_setting('upi')
        order_id = generate_order_id()
        expiry_time = datetime.now() + timedelta(minutes=20)
        expiry_str = expiry_time.strftime("%Y-%m-%d %H:%M:%S")
        upi_str = f"upi://pay?pa={upi}&am={price}&cu=INR"
        qr = qrcode.make(upi_str)
        qr_bytes = BytesIO()
        qr.save(qr_bytes, 'PNG')
        qr_bytes.seek(0)
        temp_id = random.randint(10000, 99999)
        db_execute("INSERT INTO temp_payments (user_id, payment_id, product, amount, product_id, order_id, expiry) VALUES (?,?,?,?,?,?,?)",
                   (call.from_user.id, temp_id, name, price, pid, order_id, expiry_str))
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("✅ I HAVE PAID", callback_data=f"paid_{temp_id}"))
        kb.add(InlineKeyboardButton("❌ CANCEL", callback_data="premium"))
        caption = f"🧾 *Please complete the following payment:*\n\n📦 *Plan Name:* {name}\n🆔 *Order ID:* `{order_id}`\n💰 *Amount:* ₹{price}\n\n1️⃣ Scan the QR code and pay\n2️⃣ Click 'I HAVE PAID'\n3️⃣ Send payment screenshot\n\n🗒️ *QR expires in 20 minutes*"
        bot.send_photo(call.message.chat.id, qr_bytes, caption=caption, reply_markup=kb, parse_mode="Markdown")
        bot.answer_callback_query(call.id)
    except Exception as e:
        bot.answer_callback_query(call.id, "Error! Try again.")
        print(f"Buy error: {e}")

bot.payment_ctx = {}

@bot.callback_query_handler(func=lambda call: call.data.startswith("paid_"))
def paid_cb(call):
    try:
        temp_id = int(call.data.split("_")[1])
        temp = db_query("SELECT user_id, product, amount, product_id, order_id FROM temp_payments WHERE payment_id=?", (temp_id,))
        if not temp or temp[0][0] != call.from_user.id:
            bot.answer_callback_query(call.id, "Error!")
            return
        uid, pname, amt, pid, order_id = temp[0]
        pay_id = db_insert("INSERT INTO payments (user_id, product, amount, status, time) VALUES (?,?,?,?,?)",
                           (uid, pname, amt, "pending", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        db_execute("DELETE FROM temp_payments WHERE payment_id=?", (temp_id,))
        bot.payment_ctx[call.from_user.id] = (pay_id, pname, amt)
        guide_msg = "📸 *PAYMENT GUIDE*\n\n1️⃣ Open UPI app\n2️⃣ Scan QR code\n3️⃣ Pay amount\n4️⃣ Take screenshot\n5️⃣ Send it here\n\n⚠️ Fake screenshots will be rejected!"
        bot.send_message(call.message.chat.id, guide_msg, parse_mode="Markdown")
        bot.send_message(call.message.chat.id, "Now send the payment screenshot:")
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, screenshot_handler)
        bot.answer_callback_query(call.id, "Waiting for screenshot...")
    except Exception as e:
        bot.answer_callback_query(call.id, "Error!")
        print(f"Paid error: {e}")

def screenshot_handler(m):
    user_id = m.from_user.id
    if user_id not in bot.payment_ctx:
        bot.send_message(m.chat.id, "❌ Session expired. Use /start")
        return
    pay_id, pname, amt = bot.payment_ctx[user_id]
    if not m.photo:
        bot.send_message(m.chat.id, "❌ Send a PHOTO! (Payment screenshot)")
        bot.register_next_step_handler_by_chat_id(m.chat.id, screenshot_handler)
        return
    fid = m.photo[-1].file_id
    db_execute("UPDATE payments SET ssid=? WHERE id=?", (fid, pay_id))
    bot.send_message(m.chat.id, "✅ Screenshot received! Waiting for admin approval.")
    user = m.from_user
    user_link = f"tg://user?id={user.id}"
    username = f"@{user.username}" if user.username else "No username"
    admin_msg = (f"🔔 *NEW PAYMENT*\n\n👤 *User:* {username}\n🆔 *User ID:* `{user.id}`\n📞 *Contact:* [Click here]({user_link})\n📦 *Product:* {pname}\n💰 *Amount:* ₹{amt}\n🆔 *Payment ID:* `{pay_id}`")
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("✅ APPROVE", callback_data=f"app_{pay_id}"))
    kb.add(InlineKeyboardButton("❌ REJECT", callback_data=f"rej_{pay_id}"))
    for admin_id in ADMIN_IDS:
        try:
            bot.send_photo(admin_id, fid, caption=admin_msg, reply_markup=kb, parse_mode="Markdown")
        except Exception as e:
            print(f"Failed to send to admin {admin_id}: {e}")
    del bot.payment_ctx[user_id]

@bot.callback_query_handler(func=lambda call: call.data.startswith("app_") or call.data.startswith("rej_"))
def admin_decision_cb(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Unauthorized!")
        return
    pay_id = int(call.data.split("_")[1])
    if call.data.startswith("app_"):
        pay_data = db_query("SELECT user_id, product, amount, ssid FROM payments WHERE id=?", (pay_id,))
        if not pay_data:
            bot.answer_callback_query(call.id, "Payment not found!")
            return
        uid, pname, amt, ssid = pay_data[0]
        prod = db_query("SELECT reward FROM products WHERE name=?", (pname,))
        reward_text = prod[0][0] if prod else "🎉 Thank you for your purchase!"
        try:
            bot.send_message(uid, f"✅ *PAYMENT APPROVED!*\n\n🎁 {reward_text}\n\nThank you!", parse_mode="Markdown")
        except Exception as e:
            print(f"Failed to send reward to user {uid}: {e}")
        db_execute("UPDATE payments SET status='approved' WHERE id=?", (pay_id,))
        update_daily_payment(amt)
        bot.answer_callback_query(call.id, "Approved & reward sent!")
    else:
        pay_data = db_query("SELECT user_id FROM payments WHERE id=?", (pay_id,))
        if pay_data:
            uid = pay_data[0][0]
            try:
                bot.send_message(uid, "❌ *PAYMENT REJECTED!*\nFake payment detected. Contact admin.", parse_mode="Markdown")
            except:
                pass
            db_execute("UPDATE payments SET status='rejected' WHERE id=?", (pay_id,))
            bot.answer_callback_query(call.id, "Rejected!")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_start")
def back_to_start_cb(call):
    start_cmd(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "back")
def back_cb(call):
    start_cmd(call.message)

@bot.message_handler(commands=['claim_offer'])
def claim_offer_cmd(m):
    add_user(m.from_user.id, m.from_user.username or "User")
    off = db_query("SELECT upi, amount, caption FROM claim_offers WHERE active=1 ORDER BY id DESC LIMIT 1")
    if off:
        upi, amt, cap = off[0]
        upi_str = f"upi://pay?pa={upi}&am={amt}&cu=INR"
        qr = qrcode.make(upi_str)
        qr_bytes = BytesIO()
        qr.save(qr_bytes, 'PNG')
        qr_bytes.seek(0)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ CANCEL", callback_data="back"))
        caption = cap if cap else f"🎁 *SPECIAL OFFER*\n💰 ₹{amt}\n📱 UPI: `{upi}`"
        bot.send_photo(m.chat.id, qr_bytes, caption=caption, reply_markup=kb, parse_mode="Markdown")
    else:
        bot.send_message(m.chat.id, "❌ No active offer right now!")

# ========== ADMIN PANEL ==========
@bot.message_handler(commands=['admin'])
def admin_panel(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ Unauthorized!")
        return
    users = db_query("SELECT COUNT(*) FROM users")[0][0]
    total_earn = db_query("SELECT SUM(amount) FROM payments WHERE status='approved'")[0][0] or 0
    pending = db_query("SELECT COUNT(*) FROM payments WHERE status='pending'")[0][0]
    today = datetime.now().strftime("%Y-%m-%d")
    today_data = db_query("SELECT count, total_amount FROM daily_payments WHERE date=?", (today,))
    today_count = today_data[0][0] if today_data else 0
    today_amount = today_data[0][1] if today_data else 0
    
    # Stylish credit banner for Gourav
    credit = """
   ╔═══════════════════════════════════════╗
   ║          🎩  G O U R A V  🎩           ║
   ║     Master Bot Architect & Creator     ║
   ║   ✨ All Controls Reinvented ✨        ║
   ╚═══════════════════════════════════════╝
"""
    stats = (
        f"{credit}\n\n"
        f"📊 *⚙️ STATISTICS ⚙️*\n"
        f"┌───────────────────────────┐\n"
        f"│ 👥 Users: {users}\n"
        f"│ 💰 Earnings: ₹{total_earn}\n"
        f"│ ⏳ Pending: {pending}\n"
        f"├───────────────────────────┤\n"
        f"│ 📅 Today: {today_count} payments\n"
        f"│ 💵 Amount: ₹{today_amount}\n"
        f"└───────────────────────────┘"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("➕ ADD PRODUCT", callback_data="add_prod"))
    kb.add(InlineKeyboardButton("✏️ EDIT PRODUCT", callback_data="edit_prod"))
    kb.add(InlineKeyboardButton("🗑️ DELETE PRODUCT", callback_data="del_prod"))
    kb.add(InlineKeyboardButton("📋 LIST PRODUCTS", callback_data="list_prod"))
    kb.add(InlineKeyboardButton("🎁 SET CLAIM OFFER", callback_data="set_offer"))
    kb.add(InlineKeyboardButton("🎮 SET DEMO CHANNEL", callback_data="set_demo"))
    kb.add(InlineKeyboardButton("💰 SET UPI", callback_data="set_upi"))
    kb.add(InlineKeyboardButton("🖼️ SET WELCOME IMAGE", callback_data="set_welcome_img"))
    kb.add(InlineKeyboardButton("📝 SET WELCOME TEXT", callback_data="set_welcome_txt"))
    kb.add(InlineKeyboardButton("📹 SET HOW TO PAY VIDEO", callback_data="set_how_to_pay_video"))
    kb.add(InlineKeyboardButton(f"⏳ PENDING ({pending})", callback_data="view_pending"))
    kb.add(InlineKeyboardButton("📢 BROADCAST", callback_data="broadcast"))
    kb.add(InlineKeyboardButton("⏰ AUTO MESSAGES", callback_data="auto_msg"))
    kb.add(InlineKeyboardButton("📊 PAYMENT DETAILS", callback_data="payment_details"))
    kb.add(InlineKeyboardButton("📈 DAILY STATS", callback_data="daily_stats"))
    kb.add(InlineKeyboardButton("🔄 RESET DATABASE", callback_data="reset_db"))
    
    bot.send_message(m.chat.id, stats, reply_markup=kb, parse_mode="Markdown")

# ========== EDIT PRODUCT CALLBACK ==========
@bot.callback_query_handler(func=lambda call: call.data == "edit_prod")
def edit_prod_list(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Unauthorized!")
        return
    prods = db_query("SELECT id, name, price, reward FROM products")
    if not prods:
        bot.send_message(call.message.chat.id, "📦 No products to edit.")
        return
    msg = "✏️ *EDIT PRODUCT*\n\nSend the product ID you want to edit:\n\n"
    for p in prods:
        msg += f"ID `{p[0]}` → {p[1]} | ₹{p[2]}\n   🎁 {p[3][:40]}...\n\n"
    bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")
    bot.register_next_step_handler(call.message, ask_edit_field)

def ask_edit_field(m):
    if not is_admin(m.from_user.id):
        return
    try:
        pid = int(m.text.strip())
        prod = db_query("SELECT id, name, price, reward FROM products WHERE id=?", (pid,))
        if not prod:
            bot.send_message(m.chat.id, "❌ Product not found.")
            return
        bot.send_message(m.chat.id, f"✏️ Editing product ID {pid}\n\nWhat do you want to change?\n\n1️⃣ Name\n2️⃣ Price\n3️⃣ Reward\n\nSend the number (1, 2, or 3):")
        bot.register_next_step_handler(m, lambda msg: get_edit_field(msg, pid))
    except:
        bot.send_message(m.chat.id, "❌ Send a valid product ID.")

def get_edit_field(m, pid):
    if not is_admin(m.from_user.id):
        return
    choice = m.text.strip()
    if choice == "1":
        bot.send_message(m.chat.id, "Send the new product name:")
        bot.register_next_step_handler(m, lambda msg: update_product_name(msg, pid))
    elif choice == "2":
        bot.send_message(m.chat.id, "Send the new price (only number):")
        bot.register_next_step_handler(m, lambda msg: update_product_price(msg, pid))
    elif choice == "3":
        bot.send_message(m.chat.id, "Send the new reward text/link:")
        bot.register_next_step_handler(m, lambda msg: update_product_reward(msg, pid))
    else:
        bot.send_message(m.chat.id, "❌ Invalid choice. Start over with /admin.")

def update_product_name(m, pid):
    if not is_admin(m.from_user.id):
        return
    new_name = m.text.strip()
    db_execute("UPDATE products SET name=? WHERE id=?", (new_name, pid))
    bot.send_message(m.chat.id, f"✅ Product ID {pid} name updated to: {new_name}")

def update_product_price(m, pid):
    if not is_admin(m.from_user.id):
        return
    try:
        new_price = int(m.text.strip())
        db_execute("UPDATE products SET price=? WHERE id=?", (new_price, pid))
        bot.send_message(m.chat.id, f"✅ Product ID {pid} price updated to: ₹{new_price}")
    except:
        bot.send_message(m.chat.id, "❌ Invalid price. Use a number.")

def update_product_reward(m, pid):
    if not is_admin(m.from_user.id):
        return
    new_reward = m.text.strip()
    db_execute("UPDATE products SET reward=? WHERE id=?", (new_reward, pid))
    bot.send_message(m.chat.id, f"✅ Product ID {pid} reward updated.")

# ========== OTHER ADMIN CALLBACKS ==========
@bot.callback_query_handler(func=lambda call: call.data == "payment_details")
def payment_details(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Unauthorized!")
        return
    payments = db_query("SELECT id, user_id, product, amount, status, time FROM payments ORDER BY id DESC LIMIT 50")
    if not payments:
        bot.send_message(call.message.chat.id, "No payment records found.")
        return
    msg = "📊 *PAYMENT DETAILS* (Last 50)\n\n"
    for p in payments:
        status_icon = "✅" if p[4] == "approved" else "⏳" if p[4] == "pending" else "❌"
        msg += f"🆔 {p[0]} | 👤 {p[1]} | {p[2]} | ₹{p[3]} | {status_icon}\n🕐 {p[5]}\n\n"
    for part in split_long_message(msg):
        bot.send_message(call.message.chat.id, part, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "daily_stats")
def daily_stats(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Unauthorized!")
        return
    stats = db_query("SELECT date, count, total_amount FROM daily_payments ORDER BY date DESC LIMIT 30")
    if not stats:
        bot.send_message(call.message.chat.id, "No daily payment records found.")
        return
    msg = "📅 *DAILY PAYMENT STATISTICS*\n\n"
    for s in stats:
        msg += f"📆 {s[0]}\n   📊 {s[1]} payments | 💵 ₹{s[2]}\n\n"
    for part in split_long_message(msg):
        bot.send_message(call.message.chat.id, part, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "add_prod")
def add_prod_cb(call):
    if not is_admin(call.from_user.id): return
    bot.send_message(call.message.chat.id, "📦 *ADD PRODUCT*\n\nSend: `Name | Price | Reward`\nExample: `Premium Plan | 99 | Your reward text`", parse_mode="Markdown")
    bot.register_next_step_handler(call.message, save_product)

def save_product(m):
    if not is_admin(m.from_user.id): return
    try:
        parts = [x.strip() for x in m.text.split("|")]
        if len(parts) != 3:
            raise ValueError
        name, price_str, reward = parts
        price = int(price_str)
        db_execute("INSERT INTO products (name, price, reward) VALUES (?,?,?)", (name, price, reward))
        bot.send_message(m.chat.id, f"✅ Product '{name}' added!\n💰 Price: ₹{price}")
    except:
        bot.send_message(m.chat.id, "❌ Use: `Name | Price | Reward`")

@bot.callback_query_handler(func=lambda call: call.data == "del_prod")
def del_prod_cb(call):
    if not is_admin(call.from_user.id): return
    prods = db_query("SELECT id, name FROM products")
    if not prods:
        bot.send_message(call.message.chat.id, "No products.")
        return
    txt = "Send product ID:\n"
    for p in prods:
        txt += f"ID {p[0]} → {p[1]}\n"
    bot.send_message(call.message.chat.id, txt)
    bot.register_next_step_handler(call.message, delete_product)

def delete_product(m):
    if not is_admin(m.from_user.id): return
    try:
        pid = int(m.text.strip())
        p = db_query("SELECT name FROM products WHERE id=?", (pid,))
        if p:
            db_execute("DELETE FROM products WHERE id=?", (pid,))
            bot.send_message(m.chat.id, f"✅ Deleted {p[0][0]}")
        else:
            bot.send_message(m.chat.id, "ID not found")
    except:
        bot.send_message(m.chat.id, "Send valid ID")

@bot.callback_query_handler(func=lambda call: call.data == "list_prod")
def list_prod_cb(call):
    if not is_admin(call.from_user.id): return
    prods = db_query("SELECT id, name, price FROM products")
    if not prods:
        bot.send_message(call.message.chat.id, "No products.")
        return
    txt = "📦 *PRODUCTS*\n"
    for p in prods:
        txt += f"ID {p[0]}: {p[1]} - ₹{p[2]}\n"
    bot.send_message(call.message.chat.id, txt, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "set_offer")
def set_offer_cb(call):
    if not is_admin(call.from_user.id): return
    bot.send_message(call.message.chat.id, "🎁 *SET CLAIM OFFER*\n\nSend: `UPI | Amount | Caption`\nExample: `admin@ok | 50 | Special Offer!`", parse_mode="Markdown")
    bot.register_next_step_handler(call.message, save_offer)

def save_offer(m):
    if not is_admin(m.from_user.id): return
    try:
        parts = [x.strip() for x in m.text.split("|")]
        upi, amount, caption = parts[0], int(parts[1]), parts[2]
        db_execute("UPDATE claim_offers SET active=0")
        db_execute("INSERT INTO claim_offers (upi, amount, caption, active) VALUES (?,?,?,1)", (upi, amount, caption))
        bot.send_message(m.chat.id, f"✅ Claim offer set!\nUPI: {upi}\nAmount: ₹{amount}")
    except:
        bot.send_message(m.chat.id, "Error! Use: `UPI | Amount | Caption`")

@bot.callback_query_handler(func=lambda call: call.data == "set_demo")
def set_demo_cb(call):
    if not is_admin(call.from_user.id): return
    bot.send_message(call.message.chat.id, "🎮 *SET DEMO CHANNEL LINK*\n\nSend invite link:\n`https://t.me/yourchannel`", parse_mode="Markdown")
    bot.register_next_step_handler(call.message, save_demo)

def save_demo(m):
    if not is_admin(m.from_user.id): return
    link = m.text.strip()
    if "t.me" in link or "http" in link:
        db_execute("UPDATE demo_settings SET link=? WHERE id=1", (link,))
        bot.send_message(m.chat.id, "✅ Demo channel link updated!")
    else:
        bot.send_message(m.chat.id, "❌ Invalid link.")

@bot.callback_query_handler(func=lambda call: call.data == "set_upi")
def set_upi_cb(call):
    if not is_admin(call.from_user.id): return
    bot.send_message(call.message.chat.id, "💰 *SET UPI*\n\nSend UPI ID:")
    bot.register_next_step_handler(call.message, save_upi)

def save_upi(m):
    if not is_admin(m.from_user.id): return
    update_setting('upi', m.text.strip())
    bot.send_message(m.chat.id, f"✅ UPI set to {m.text}")

@bot.callback_query_handler(func=lambda call: call.data == "set_welcome_img")
def set_welcome_img_cb(call):
    if not is_admin(call.from_user.id): return
    bot.send_message(call.message.chat.id, "🖼 *SET WELCOME IMAGE*\n\nSend the photo:", parse_mode="Markdown")
    bot.register_next_step_handler(call.message, save_welcome_img)

def save_welcome_img(m):
    if not is_admin(m.from_user.id): return
    if m.photo:
        update_setting('welcome_image', m.photo[-1].file_id)
        bot.send_message(m.chat.id, "✅ Welcome image updated!")
    else:
        bot.send_message(m.chat.id, "❌ Send a PHOTO.")
        bot.register_next_step_handler(m, save_welcome_img)

@bot.callback_query_handler(func=lambda call: call.data == "set_welcome_txt")
def set_welcome_txt_cb(call):
    if not is_admin(call.from_user.id): return
    bot.send_message(call.message.chat.id, "📝 *SET WELCOME TEXT*\n\nSend the welcome message:", parse_mode="Markdown")
    bot.register_next_step_handler(call.message, save_welcome_txt)

def save_welcome_txt(m):
    if not is_admin(m.from_user.id): return
    update_setting('welcome_text', m.text)
    bot.send_message(m.chat.id, "✅ Welcome text updated!")

@bot.callback_query_handler(func=lambda call: call.data == "set_how_to_pay_video")
def set_how_to_pay_video_cb(call):
    if not is_admin(call.from_user.id): return
    bot.send_message(call.message.chat.id, "📹 *SET HOW TO PAY VIDEO*\n\nSend video link (YouTube or any URL):", parse_mode="Markdown")
    bot.register_next_step_handler(call.message, save_how_to_pay_video)

def save_how_to_pay_video(m):
    if not is_admin(m.from_user.id): return
    url = m.text.strip()
    update_setting('how_to_pay_video', url)
    bot.send_message(m.chat.id, f"✅ Video link set: {url}")

@bot.callback_query_handler(func=lambda call: call.data == "view_pending")
def view_pending_cb(call):
    if not is_admin(call.from_user.id): return
    pend = db_query("SELECT id, user_id, product, amount FROM payments WHERE status='pending'")
    if not pend:
        bot.send_message(call.message.chat.id, "✅ No pending payments.")
        return
    txt = f"⏳ *PENDING PAYMENTS:* {len(pend)}\n\n"
    for p in pend:
        txt += f"ID {p[0]}: User {p[1]}, {p[2]}, ₹{p[3]}\n"
    bot.send_message(call.message.chat.id, txt, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "broadcast")
def broadcast_cb(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Unauthorized!")
        return
    bot.send_message(call.message.chat.id, "📢 *BROADCAST*\n\nSend message (text/photo/video) to ALL users:", parse_mode="Markdown")
    bot.register_next_step_handler(call.message, do_broadcast)

def do_broadcast(m):
    if not is_admin(m.from_user.id): return
    users = db_query("SELECT user_id FROM users")
    if not users:
        bot.send_message(m.chat.id, "❌ No users found.")
        return
    total = len(users)
    sent = 0
    fail = 0
    status_msg = bot.send_message(m.chat.id, f"📢 Broadcasting to {total} users...")
    if m.text:
        parts = split_long_message(m.text)
        for u in users:
            try:
                for part in parts:
                    bot.send_message(u[0], f"📢 *ANNOUNCEMENT*\n\n{part}", parse_mode="Markdown")
                sent += 1
            except:
                fail += 1
            time.sleep(0.05)
    elif m.photo:
        caption = m.caption or ""
        caption_parts = split_long_message(caption)
        fid = m.photo[-1].file_id
        for u in users:
            try:
                for i, part in enumerate(caption_parts):
                    if i == 0:
                        bot.send_photo(u[0], fid, caption=f"📢 *ANNOUNCEMENT*\n\n{part}", parse_mode="Markdown")
                    else:
                        bot.send_message(u[0], f"📢 *ANNOUNCEMENT* (cont.)\n\n{part}", parse_mode="Markdown")
                sent += 1
            except:
                fail += 1
            time.sleep(0.05)
    elif m.video:
        caption = m.caption or ""
        caption_parts = split_long_message(caption)
        fid = m.video.file_id
        for u in users:
            try:
                for i, part in enumerate(caption_parts):
                    if i == 0:
                        bot.send_video(u[0], fid, caption=f"📢 *ANNOUNCEMENT*\n\n{part}", parse_mode="Markdown")
                    else:
                        bot.send_message(u[0], f"📢 *ANNOUNCEMENT* (cont.)\n\n{part}", parse_mode="Markdown")
                sent += 1
            except:
                fail += 1
            time.sleep(0.05)
    else:
        bot.edit_message_text("❌ Unsupported.", status_msg.chat.id, status_msg.message_id)
        return
    bot.edit_message_text(f"✅ Done!\n✅ Sent: {sent}\n❌ Failed: {fail}\n📊 Total: {total}", status_msg.chat.id, status_msg.message_id, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "auto_msg")
def auto_msg_menu(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Unauthorized!")
        return
    msgs = db_query("SELECT id, msg, interval, active FROM auto_msgs ORDER BY id")
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("➕ ADD AUTO MESSAGE", callback_data="add_auto_msg"))
    for msg in msgs:
        icon = "✅" if msg[3] else "❌"
        keyboard.add(InlineKeyboardButton(f"{icon} ID {msg[0]}: Every {msg[2]}min", callback_data=f"edit_auto_msg_{msg[0]}"))
    keyboard.add(InlineKeyboardButton("🔙 BACK", callback_data="back_to_admin"))
    text = "⏰ *AUTO MESSAGES*\n\n"
    if msgs:
        for msg in msgs:
            text += f"• ID {msg[0]}: Every {msg[2]}min | {'Active' if msg[3] else 'Inactive'}\n   📝 {msg[1][:60]}\n\n"
    else:
        text += "No auto messages.\n\n"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "add_auto_msg")
def add_auto_msg_prompt(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Unauthorized!")
        return
    bot.send_message(call.message.chat.id, "➕ *ADD AUTO MESSAGE*\n\nSend: `Message | Minutes`\nExample: `Check offers! | 30`\nMinutes 1-1440.", parse_mode="Markdown")
    bot.register_next_step_handler(call.message, save_auto_msg)

def save_auto_msg(m):
    if not is_admin(m.from_user.id): return
    try:
        parts = [x.strip() for x in m.text.split("|")]
        msg_text, interval = parts[0], int(parts[1])
        if interval < 1 or interval > 1440:
            bot.send_message(m.chat.id, "❌ Interval 1-1440")
            return
        db_execute("INSERT INTO auto_msgs (msg, interval, active) VALUES (?,?,1)", (msg_text, interval))
        bot.send_message(m.chat.id, f"✅ Auto message added! Every {interval} min")
    except:
        bot.send_message(m.chat.id, "❌ Use: `Message | Minutes`")

@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_auto_msg_"))
def edit_auto_msg_menu(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Unauthorized!")
        return
    mid = int(call.data.split("_")[3])
    md = db_query("SELECT id, msg, interval, active FROM auto_msgs WHERE id=?", (mid,))
    if not md:
        bot.answer_callback_query(call.id, "Not found")
        return
    msg = md[0]
    kb = InlineKeyboardMarkup(row_width=2)
    togg = "🟢 DEACTIVATE" if msg[3] else "🔴 ACTIVATE"
    kb.add(InlineKeyboardButton(togg, callback_data=f"toggle_auto_{msg[0]}"))
    kb.add(InlineKeyboardButton("🗑 DELETE", callback_data=f"delete_auto_{msg[0]}"))
    kb.add(InlineKeyboardButton("🔙 BACK", callback_data="auto_msg"))
    text = f"✏️ *Edit Auto Message ID {msg[0]}*\n\n📝 {msg[1]}\n⏰ Every {msg[2]}min\n📊 {'Active' if msg[3] else 'Inactive'}"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("toggle_auto_"))
def toggle_auto_msg(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Unauthorized!")
        return
    mid = int(call.data.split("_")[2])
    cur = db_query("SELECT active FROM auto_msgs WHERE id=?", (mid,))
    if not cur:
        bot.answer_callback_query(call.id, "Not found")
        return
    new = 1 - cur[0][0]
    db_execute("UPDATE auto_msgs SET active=? WHERE id=?", (new, mid))
    bot.answer_callback_query(call.id, f"{'Activated' if new else 'Deactivated'}!")
    edit_auto_msg_menu(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_auto_"))
def delete_auto_msg(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Unauthorized!")
        return
    mid = int(call.data.split("_")[2])
    db_execute("DELETE FROM auto_msgs WHERE id=?", (mid,))
    bot.answer_callback_query(call.id, "Deleted!")
    auto_msg_menu(call)

@bot.callback_query_handler(func=lambda call: call.data == "reset_db")
def reset_db_cb(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Unauthorized!")
        return
    reset_db_cmd(call.message)
    bot.answer_callback_query(call.id, "Database reset!")

@bot.message_handler(commands=['resetdb'])
def reset_db_cmd(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ Unauthorized!")
        return
    tables = ['users', 'products', 'payments', 'temp_payments', 'claim_offers', 'auto_msgs', 'daily_payments']
    for table in tables:
        db_execute(f"DELETE FROM {table}")
    db_execute("INSERT INTO products (name, price, reward) VALUES ('🔍 DEMO (Preview Only)', 0, 'This is a demo product. No payment required. Upgrade to real plan!')")
    db_execute("INSERT INTO products (name, price, reward) VALUES ('✨ 1 Month Premium', 99, '🎉 You got 1 Month Premium!')")
    db_execute("INSERT INTO products (name, price, reward) VALUES ('✨ 3 Months Premium', 199, '🎉 You got 3 Months Premium!')")
    db_execute("INSERT INTO products (name, price, reward) VALUES ('✨ 6 Months Premium', 299, '🎉 You got 6 Months Premium!')")
    db_execute("UPDATE claim_offers SET active=0")
    bot.send_message(m.chat.id, "✅ Database reset! Default products restored.")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_admin")
def back_to_admin_cb(call):
    admin_panel(call.message)

# ========== AUTO MESSAGE LOOP ==========
def auto_msg_loop():
    while True:
        try:
            msgs = db_query("SELECT id, msg, interval FROM auto_msgs WHERE active=1")
            for mid, msg, interval in msgs:
                parts = split_long_message(msg)
                users = db_query("SELECT user_id FROM users")
                for user in users:
                    try:
                        for part in parts:
                            bot.send_message(user[0], f"⏰ *AUTO MESSAGE*\n\n{part}", parse_mode="Markdown")
                    except:
                        pass
                    time.sleep(0.1)
                time.sleep(interval * 60)
        except Exception as e:
            print(f"Auto msg error: {e}")
            time.sleep(60)

threading.Thread(target=auto_msg_loop, daemon=True).start()

# ========== RUN BOT ==========
if __name__ == "__main__":
    print("✨ Bot is running... ✨")
    print(f"👑 Admins: {ADMIN_IDS}")
    print(f"💾 Database: {DB_NAME}")
    print("🎩 Crafted by GOURAV")
    bot.infinity_polling()
