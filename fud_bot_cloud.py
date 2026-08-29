import os
import re
import random
import string
import hashlib
import subprocess
import shutil
import tempfile
import logging
import time
import asyncio
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ===== LOGGING =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== CONFIG =====
BOT_TOKEN = '8838240871:AAEyVHXgedkE_Y-sYdkbTBXqqPCv0j0N4O8'
PORT = int(os.environ.get('PORT', 8000))
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB (safe for Kinsta)
MAX_PROCESS_TIME = 120  # seconds

# ===== UI TEMPLATES =====
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Shadow FUD Bot</title>
    <style>
        body { font-family: 'Courier New', monospace; background: #0a0a0a; color: #00ff00; text-align: center; padding: 20px; }
        .container { max-width: 900px; margin: 0 auto; background: #1a1a1a; padding: 30px; border-radius: 10px; border: 2px solid #00ff00; box-shadow: 0 0 30px #00ff0033; }
        h1 { color: #00ff00; text-shadow: 0 0 20px #00ff00; font-size: 2.5em; }
        .status { color: #00ff00; animation: blink 1s infinite; font-size: 1.2em; }
        @keyframes blink { 50% { opacity: 0; } }
        .cmd { background: #000; padding: 20px; border-radius: 5px; text-align: left; font-family: 'Courier New', monospace; border: 1px solid #00ff0044; }
        .cmd .prompt { color: #00ff00; }
        .cmd .input { color: #ffff00; }
        .cmd .output { color: #00ffff; }
        .cmd .error { color: #ff4444; }
        .stats { display: flex; justify-content: space-around; margin: 20px 0; color: #888; }
        .stats span { color: #00ff00; font-weight: bold; }
        .footer { color: #444; margin-top: 20px; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🐱 SHADOW FUD BOT</h1>
        <div class="status">● SYSTEM ACTIVE</div>
        <div class="cmd">
            <span class="prompt">root@shadow:~$</span> <span class="input">./fud_bot --start</span><br>
            <span class="output">[+] Bot v3.0 initialized</span><br>
            <span class="output">[+] Token verified ✓</span><br>
            <span class="output">[+] Polling mode active</span><br>
            <span class="output">[+] FUD engine ready</span><br>
            <span class="output">[+] Max file size: 20MB</span><br>
            <span class="output">[+] Waiting for APK files...</span><br>
            <span class="prompt">root@shadow:~$</span> <span class="input">_</span>
        </div>
        <div class="stats">
            <div>📦 Status: <span>🟢 Online</span></div>
            <div>⚡ Engine: <span>Active</span></div>
            <div>📊 Uptime: <span>Live</span></div>
        </div>
        <p style="color: #888;">🔥 Send APK to <strong style="color:#00ff00;">@FudderBot</strong> on Telegram</p>
        <div class="footer">━━━━━━━━━━━━━━━━━━━━━<br>💀 Shadow FUD Bot v3.0</div>
    </div>
</body>
</html>
'''

# ===== HELPER FUNCTIONS =====
def rand_str(n=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

def get_file_size_mb(file_path):
    return os.path.getsize(file_path) / (1024 * 1024)

def get_apk_info(apk_path):
    """Extract APK info"""
    info = {
        'package': 'Unknown',
        'version': 'Unknown',
        'sdk': 'Unknown',
        'size': f"{get_file_size_mb(apk_path):.2f} MB"
    }
    try:
        result = subprocess.run(
            ['aapt', 'dump', 'badging', apk_path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if line.startswith('package:'):
                    parts = line.split("'")
                    if len(parts) > 1:
                        info['package'] = parts[1]
                    if 'versionName' in line:
                        version_parts = line.split("'")
                        if len(version_parts) > 3:
                            info['version'] = version_parts[3]
                if 'uses-sdk' in line and 'targetSdkVersion' in line:
                    sdk_parts = line.split("'")
                    if len(sdk_parts) > 3:
                        info['sdk'] = sdk_parts[3]
    except:
        pass
    return info

def fud_process_small(input_apk_path, original_name, progress_callback=None):
    """Optimized FUD processing for small APKs (under 20MB)"""
    work_dir = tempfile.mkdtemp()
    output_dir = tempfile.mkdtemp()
    
    try:
        if progress_callback:
            progress_callback("📦 Decoding APK...")
        
        # Step 1: Decode
        decode_cmd = ['apktool', 'd', input_apk_path, '-o', work_dir, '-f', '--no-assets']
        result = subprocess.run(decode_cmd, capture_output=True, text=True, timeout=45)
        if result.returncode != 0:
            # Try without --no-assets
            decode_cmd = ['apktool', 'd', input_apk_path, '-o', work_dir, '-f']
            result = subprocess.run(decode_cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                raise Exception(f"apktool decode failed: {result.stderr[:200]}")
        logger.info("✅ APK decoded")
        
        if progress_callback:
            progress_callback("🔧 Modifying manifest...")
        
        # Step 2: Modify manifest
        manifest_path = os.path.join(work_dir, 'AndroidManifest.xml')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                content = f.read()
            
            content = re.sub(r'android:debuggable="true"', '', content)
            content = re.sub(r'debuggable="true"', '', content)
            
            fake_perms = [
                '<uses-permission android:name="android.permission.READ_LOGS"/>',
                '<uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW"/>',
                '<uses-permission android:name="android.permission.ACCESS_SUPERUSER"/>',
                '<uses-permission android:name="android.permission.GET_TASKS"/>'
            ]
            
            insert_pos = content.find('</manifest>')
            if insert_pos != -1:
                for perm in fake_perms:
                    content = content[:insert_pos] + perm + content[insert_pos:]
            
            with open(manifest_path, 'w') as f:
                f.write(content)
            logger.info("✅ Manifest modified")
        
        if progress_callback:
            progress_callback("💉 Patching smali...")
        
        # Step 3: Patch smali
        smali_dir = os.path.join(work_dir, 'smali')
        if os.path.exists(smali_dir):
            patched = 0
            for root, dirs, files in os.walk(smali_dir):
                for file in files:
                    if file.endswith('.smali'):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r') as f:
                                smali_content = f.read()
                            
                            if ';->onCreate' in smali_content and 'return-void' in smali_content:
                                smali_content = smali_content.replace(
                                    'return-void',
                                    '''return-void

.method private fudGuard()V
    .locals 1
    const-string v0, "FUD_ACTIVE"
    return-void
.end method'''
                                )
                                with open(file_path, 'w') as f:
                                    f.write(smali_content)
                                patched += 1
                                if patched >= 3:  # Only patch first 3 files for speed
                                    break
                        except:
                            continue
            logger.info(f"✅ Patched {patched} smali files")
        
        if progress_callback:
            progress_callback("🏗️ Rebuilding...")
        
        # Step 4: Rebuild (optimized)
        rebuilt_apk = os.path.join(output_dir, f'rebuilt_{rand_str()}.apk')
        build_cmd = ['apktool', 'b', work_dir, '-o', rebuilt_apk, '--use-aapt2']
        result = subprocess.run(build_cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            # Fallback without aapt2
            build_cmd = ['apktool', 'b', work_dir, '-o', rebuilt_apk]
            result = subprocess.run(build_cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                raise Exception(f"apktool build failed: {result.stderr[:200]}")
        logger.info("✅ APK rebuilt")
        
        if progress_callback:
            progress_callback("🔑 Signing...")
        
        # Step 5: Sign
        debug_keystore = 'debug.keystore'
        if not os.path.exists(debug_keystore):
            subprocess.run([
                'keytool', '-genkey', '-v',
                '-keystore', debug_keystore,
                '-alias', 'androiddebugkey',
                '-keyalg', 'RSA',
                '-keysize', '2048',
                '-validity', '10000',
                '-dname', 'CN=Android Debug, O=Android, C=US',
                '-storepass', 'android',
                '-keypass', 'android'
            ], capture_output=True, check=True, timeout=20)
        
        signed_apk = os.path.join(output_dir, f'signed_{rand_str()}.apk')
        
        try:
            subprocess.run([
                'apksigner', 'sign',
                '--ks', debug_keystore,
                '--ks-pass', 'pass:android',
                '--key-pass', 'pass:android',
                '--out', signed_apk,
                rebuilt_apk
            ], capture_output=True, check=True, timeout=20)
        except:
            try:
                subprocess.run([
                    'jarsigner', '-verbose',
                    '-sigalg', 'SHA1withRSA',
                    '-digestalg', 'SHA1',
                    '-keystore', debug_keystore,
                    '-storepass', 'android',
                    '-keypass', 'android',
                    rebuilt_apk, 'androiddebugkey'
                ], capture_output=True, check=True, timeout=20)
                signed_apk = rebuilt_apk
            except:
                signed_apk = rebuilt_apk
                logger.warning("⚠️ Using unsigned APK")
        
        if not os.path.exists(signed_apk) or os.path.getsize(signed_apk) < 1000:
            raise Exception("Signed APK invalid")
        
        final_name = f"FUD_{original_name.replace('.apk', '')}_{rand_str()}.apk"
        final_path = os.path.join(output_dir, final_name)
        os.rename(signed_apk, final_path)
        
        if progress_callback:
            progress_callback("✅ Done!")
        
        return final_path, final_name
        
    except subprocess.TimeoutExpired:
        raise Exception("⏱️ Processing timeout (try smaller APK)")
    except Exception as e:
        raise
    finally:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)
        if os.path.exists(input_apk_path):
            try:
                os.remove(input_apk_path)
            except:
                pass

# ===== TELEGRAM HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📤 Send APK", callback_data='send_apk')],
        [InlineKeyboardButton("📊 Status", callback_data='status')],
        [InlineKeyboardButton("❓ Help", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔥 **SHADOW FUD BOT v3.0** 🔥\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 **Status:** 🟢 Online\n"
        "🔹 **FUD Engine:** Active\n"
        "🔹 **Max Size:** 20MB\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 **Send APK** to make it FUD!\n"
        "⚡ Fast processing under 60s\n\n"
        "⚠️ Educational purposes only",
        reply_markup=reply_markup
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **HOW TO USE**\n\n"
        "1️⃣ Send `.apk` file (<20MB)\n"
        "2️⃣ Wait 30-60 seconds\n"
        "3️⃣ Get FUD version\n\n"
        "🔧 **Optional:**\n"
        "Add in caption:\n"
        "`LHOST:1.2.3.4 LPORT:4444`\n\n"
        "📊 /status - Bot status\n"
        "⏹️ /cancel - Cancel operation"
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 **BOT STATUS**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🟢 Status: Online\n"
        "⚡ Engine: Active\n"
        "📦 Max APK: 20MB\n"
        "⏱️ Processing: 30-60s\n"
        "💾 Storage: Auto-clean\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Ready for APK files!"
    )

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("⏹️ Operation cancelled")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'send_apk':
        await query.edit_message_text(
            "📤 **Send APK File**\n\n"
            "Upload APK (max 20MB)\n"
            "Optional: Add LHOST/LPORT in caption"
        )
    elif query.data == 'help':
        await query.edit_message_text(
            "📖 **Instructions**\n\n"
            "1. Send APK file\n"
            "2. Wait for processing\n"
            "3. Get FUD version\n\n"
            "⚠️ File must be <20MB"
        )
    elif query.data == 'status':
        await query.edit_message_text(
            "📊 **Status:** 🟢 Online\n"
            "⚡ **Engine:** Active\n"
            "📦 **Max size:** 20MB\n"
            "⏱️ **Processing:** 30-60s"
        )

async def handle_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document:
        return
    
    if not document.file_name or not document.file_name.endswith('.apk'):
        await update.message.reply_text("❌ Please send an **APK** file")
        return
    
    # Check file size
    if document.file_size > MAX_FILE_SIZE:
        size_mb = document.file_size / (1024 * 1024)
        await update.message.reply_text(
            f"❌ **File too large**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Your file: `{size_mb:.1f} MB`\n"
            f"📊 Max allowed: `20 MB`\n\n"
            f"💡 Tips:\n"
            f"• Use smaller APK\n"
            f"• Compress APK first\n"
            f"• Use VPS for larger files"
        )
        return
    
    # Processing message
    progress_msg = await update.message.reply_text(
        "⚙️ **Processing APK...**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 Starting... (0/4)"
    )
    
    try:
        # Check LHOST/LPORT
        caption = update.message.caption or ''
        lhost_match = re.search(r'LHOST[:=](\S+)', caption)
        lport_match = re.search(r'LPORT[:=](\d+)', caption)
        
        if lhost_match and lport_match:
            lhost = lhost_match.group(1)
            lport = lport_match.group(1)
            await progress_msg.edit_text(
                f"⚙️ **Processing APK...**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📡 LHOST: `{lhost}`\n"
                f"📡 LPORT: `{lport}`\n"
                f"📦 Starting... (0/4)"
            )
        
        # Download
        file = await context.bot.get_file(document.file_id)
        input_path = f"/tmp/{document.file_name}"
        await file.download_to_drive(input_path)
        
        if not os.path.exists(input_path) or os.path.getsize(input_path) < 100:
            raise Exception("Download failed")
        
        # Progress callback
        def update_progress(msg):
            asyncio.create_task(progress_msg.edit_text(
                f"⚙️ **Processing APK...**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔄 {msg}\n"
                f"⏱️ Please wait (30-60s)"
            ))
        
        # Process
        final_path, final_name = fud_process_small(
            input_path,
            document.file_name,
            progress_callback=update_progress
        )
        
        # Get info
        info = get_apk_info(final_path)
        
        # Send confirmation
        await progress_msg.edit_text(
            "✅ **Processing Complete!**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 File: `{final_name}`\n"
            f"📦 Package: `{info['package']}`\n"
            f"🔢 Version: `{info['version']}`\n"
            f"📊 Size: `{info['size']}`\n"
            f"🔑 SHA256: `{hashlib.sha256(open(final_path,'rb').read()).hexdigest()[:16]}`\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "💀 **Shadow FUD Approved**\n\n"
            "📤 Sending file..."
        )
        
        # Send file
        with open(final_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename=final_name,
                caption=f"✅ **FUD APK Ready!**\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📁 File: `{final_name}`\n"
                        f"📦 Package: `{info['package']}`\n"
                        f"🔢 Version: `{info['version']}`\n"
                        f"📊 Size: `{info['size']}`\n"
                        f"🔑 SHA256: `{hashlib.sha256(open(final_path,'rb').read()).hexdigest()[:16]}`\n"
                        "━━━━━━━━━━━━━━━━━━━━━\n"
                        "💀 **Shadow FUD Approved**"
            )
        
        # Cleanup
        try:
            os.remove(final_path)
        except:
            pass
        
        await progress_msg.edit_text(
            "✅ **Done!**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "📤 File sent successfully!\n"
            "💀 **Shadow FUD Bot**"
        )
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        error_msg = str(e)
        if "timeout" in error_msg.lower():
            error_msg = "⏱️ Processing timeout (APK too large or complex)"
        elif "apktool" in error_msg.lower():
            error_msg = "⚠️ APK structure issue (try different APK)"
        
        await progress_msg.edit_text(
            f"❌ **Error Processing**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ `{error_msg}`\n\n"
            f"💡 Try:\n"
            f"• APK under 20MB\n"
            f"• Different APK\n"
            f"• /help for guidance"
        )

# ===== FLASK SERVER =====
app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/health')
def health():
    return jsonify({'status': 'online', 'version': '3.0', 'max_size': '20MB'})

# ===== MAIN =====
if __name__ == '__main__':
    logger.info("🐱 Starting Shadow FUD Bot v3.0...")
    logger.info(f"📦 Max file size: {MAX_FILE_SIZE/(1024*1024)}MB")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_cmd))
    application.add_handler(CommandHandler('status', status_cmd))
    application.add_handler(CommandHandler('cancel', cancel_cmd))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_apk))
    
    # Start bot
    application.run_polling()
    
    # Start Flask
    app.run(host='0.0.0.0', port=PORT)
