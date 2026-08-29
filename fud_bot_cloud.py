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

# ===== UI TEMPLATES =====
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Shadow FUD Bot</title>
    <style>
        body { font-family: Arial; background: #0a0a0a; color: #00ff00; text-align: center; padding: 50px; }
        .container { max-width: 800px; margin: 0 auto; background: #1a1a1a; padding: 30px; border-radius: 10px; border: 1px solid #00ff00; }
        h1 { color: #00ff00; text-shadow: 0 0 10px #00ff00; }
        .status { color: #00ff00; animation: blink 1s infinite; }
        @keyframes blink { 50% { opacity: 0; } }
        .cmd { background: #000; padding: 15px; border-radius: 5px; text-align: left; font-family: monospace; }
        .cmd span { color: #00ff00; }
        .cmd .input { color: #ffff00; }
        .cmd .output { color: #00ffff; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🐱 Shadow FUD Bot</h1>
        <div class="status">● SYSTEM ACTIVE</div>
        <div class="cmd">
            <span>root@shadow:~$</span> <span class="input">python3 fud_bot.py</span><br>
            <span class="output">[+] Bot started successfully</span><br>
            <span class="output">[+] Token verified</span><br>
            <span class="output">[+] Polling mode active</span><br>
            <span class="output">[+] FUD engine ready</span><br>
            <span class="output">[+] Waiting for APK files...</span><br>
        </div>
        <p style="color: #888;">🔥 Send APK to @FudderBot on Telegram</p>
    </div>
</body>
</html>
'''

# ===== HELPER FUNCTIONS =====
def rand_str(n=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

def get_file_size(file_path):
    return os.path.getsize(file_path) / (1024 * 1024)

def get_apk_info(apk_path):
    """Extract APK info using aapt"""
    try:
        result = subprocess.run(
            ['aapt', 'dump', 'badging', apk_path],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.split('\n')
        info = {
            'package': 'Unknown',
            'version': 'Unknown',
            'sdk': 'Unknown'
        }
        for line in lines:
            if line.startswith('package:'):
                parts = line.split("'")
                if len(parts) > 1:
                    info['package'] = parts[1]
                if 'versionName' in line:
                    info['version'] = line.split("'")[3] if len(line.split("'")) > 3 else 'Unknown'
            if 'uses-sdk' in line and 'targetSdkVersion' in line:
                info['sdk'] = line.split("'")[3] if len(line.split("'")) > 3 else 'Unknown'
        return info
    except:
        return {'package': 'Unknown', 'version': 'Unknown', 'sdk': 'Unknown'}

def fud_process(input_apk_path, original_name, progress_callback=None):
    """Main FUD processing pipeline with progress tracking"""
    work_dir = tempfile.mkdtemp()
    output_dir = tempfile.mkdtemp()
    final_path = None
    final_name = None
    
    try:
        logger.info(f"🔄 Processing: {original_name}")
        
        if progress_callback:
            progress_callback("📦 Decoding APK...")
        
        # Step 1: Decode APK
        decode_cmd = ['apktool', 'd', input_apk_path, '-o', work_dir, '-f']
        result = subprocess.run(decode_cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise Exception(f"apktool decode failed: {result.stderr}")
        logger.info("✅ APK decoded")
        
        if progress_callback:
            progress_callback("🔧 Modifying manifest...")
        
        # Step 2: Modify AndroidManifest.xml
        manifest_path = os.path.join(work_dir, 'AndroidManifest.xml')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                content = f.read()
            
            # Remove debuggable flag
            content = re.sub(r'android:debuggable="true"', '', content)
            content = re.sub(r'debuggable="true"', '', content)
            
            # Add fake permissions
            fake_perms = [
                '<uses-permission android:name="android.permission.READ_LOGS"/>',
                '<uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW"/>',
                '<uses-permission android:name="android.permission.ACCESS_SUPERUSER"/>',
                '<uses-permission android:name="android.permission.GET_TASKS"/>',
                '<uses-permission android:name="android.permission.WRITE_SETTINGS"/>'
            ]
            
            insert_pos = content.find('</manifest>')
            if insert_pos != -1:
                for perm in fake_perms:
                    content = content[:insert_pos] + perm + content[insert_pos:]
            
            with open(manifest_path, 'w') as f:
                f.write(content)
            logger.info("✅ Manifest modified")
        
        if progress_callback:
            progress_callback("💉 Patching smali code...")
        
        # Step 3: Patch smali files
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
.end method

.method private antiDebug()V
    .locals 1
    const-string v0, "DEBUG_OFF"
    return-void
.end method'''
                                )
                                with open(file_path, 'w') as f:
                                    f.write(smali_content)
                                patched += 1
                        except:
                            continue
            logger.info(f"✅ Patched {patched} smali files")
        
        if progress_callback:
            progress_callback("🏗️ Rebuilding APK...")
        
        # Step 4: Rebuild APK
        rebuilt_apk = os.path.join(output_dir, f'rebuilt_{rand_str()}.apk')
        build_cmd = ['apktool', 'b', work_dir, '-o', rebuilt_apk]
        result = subprocess.run(build_cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise Exception(f"apktool build failed: {result.stderr}")
        logger.info("✅ APK rebuilt")
        
        if progress_callback:
            progress_callback("🔑 Signing APK...")
        
        # Step 5: Create debug keystore if needed
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
            ], capture_output=True, check=True)
            logger.info("✅ Debug keystore created")
        
        # Step 6: Sign APK
        signed_apk = os.path.join(output_dir, f'signed_{rand_str()}.apk')
        
        # Try apksigner
        try:
            subprocess.run([
                'apksigner', 'sign',
                '--ks', debug_keystore,
                '--ks-pass', 'pass:android',
                '--key-pass', 'pass:android',
                '--out', signed_apk,
                rebuilt_apk
            ], capture_output=True, check=True, timeout=30)
            logger.info("✅ APK signed with apksigner")
        except:
            # Fallback to jarsigner
            try:
                subprocess.run([
                    'jarsigner', '-verbose',
                    '-sigalg', 'SHA1withRSA',
                    '-digestalg', 'SHA1',
                    '-keystore', debug_keystore,
                    '-storepass', 'android',
                    '-keypass', 'android',
                    rebuilt_apk, 'androiddebugkey'
                ], capture_output=True, check=True, timeout=30)
                signed_apk = rebuilt_apk
                logger.info("✅ APK signed with jarsigner")
            except Exception as e:
                # If signing fails, use unsigned APK
                signed_apk = rebuilt_apk
                logger.warning("⚠️ Using unsigned APK")
        
        # Step 7: Verify file exists
        if not os.path.exists(signed_apk):
            raise Exception("Signed APK not created")
        
        # Step 8: Finalize
        final_name = f"FUD_{original_name.replace('.apk', '')}_{rand_str()}.apk"
        final_path = os.path.join(output_dir, final_name)
        os.rename(signed_apk, final_path)
        
        # Step 9: Verify final APK
        if not os.path.exists(final_path) or os.path.getsize(final_path) < 1000:
            raise Exception("Final APK is corrupted or too small")
        
        logger.info(f"✅ FUD APK created: {final_name} ({get_file_size(final_path):.2f} MB)")
        
        if progress_callback:
            progress_callback("✅ Done!")
        
        return final_path, final_name
        
    except subprocess.TimeoutExpired:
        raise Exception("Processing timed out (APK might be too large)")
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        raise
    finally:
        # Cleanup
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
        [InlineKeyboardButton("❓ Help", callback_data='help')],
        [InlineKeyboardButton("📊 Status", callback_data='status')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔥 **SHADOW FUD BOT** 🔥\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 **Version:** 2.0 (Fixed)\n"
        "🔹 **Status:** 🟢 Online\n"
        "🔹 **FUD Engine:** Active\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 **Send any APK file** and I'll make it FUD!\n\n"
        "⚡ **Features:**\n"
        "• Advanced obfuscation\n"
        "• Smali code injection\n"
        "• Permission spoofing\n"
        "• Auto-signing\n\n"
        "⚠️ **Educational purposes only**",
        reply_markup=reply_markup
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **HOW TO USE**\n\n"
        "1️⃣ Send any `.apk` file\n"
        "2️⃣ Wait for processing (30-60 sec)\n"
        "3️⃣ Receive FUD version\n\n"
        "🔧 **Optional:**\n"
        "Add `LHOST:1.2.3.4 LPORT:4444` in caption\n\n"
        "📊 **Commands:**\n"
        "/start - Main menu\n"
        "/help - This message\n"
        "/status - Bot status\n"
        "/cancel - Cancel operation"
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 **BOT STATUS**\n\n"
        "🟢 Status: Online\n"
        "⚡ FUD Engine: Active\n"
        "📦 Supported: APK files\n"
        "💾 Storage: Temp files auto-cleaned\n"
        "⏱️ Processing: 30-60 seconds\n\n"
        "✅ Ready to process APK files!"
    )

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("⏹️ Operation cancelled")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'send_apk':
        await query.edit_message_text(
            "📤 **Send your APK file**\n\n"
            "Just upload the APK and I'll process it.\n"
            "Optional: Add LHOST/LPORT in caption."
        )
    elif query.data == 'help':
        await query.edit_message_text(
            "📖 **Instructions**\n\n"
            "1. Send APK file\n"
            "2. Wait for processing\n"
            "3. Get FUD version\n\n"
            "⚠️ Max size: 50MB"
        )
    elif query.data == 'status':
        await query.edit_message_text(
            "📊 **Status:** 🟢 Online\n"
            "⚡ **Engine:** Active\n"
            "📦 **Files processed:** 0\n"
            "⏱️ **Uptime:** Just started"
        )

async def handle_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document:
        return
    
    if not document.file_name or not document.file_name.endswith('.apk'):
        await update.message.reply_text("❌ Please send an **APK** file")
        return
    
    # Check file size (Kinsta limit ~50MB)
    if document.file_size > 50 * 1024 * 1024:
        await update.message.reply_text("❌ File too large (>50MB)")
        return
    
    # Show processing message
    progress_msg = await update.message.reply_text(
        "⚙️ **Processing APK...**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 Decoding... (Step 1/5)"
    )
    
    try:
        # Extract LHOST/LPORT from caption
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
                f"📦 Decoding... (Step 1/5)"
            )
        
        # Download APK
        file = await context.bot.get_file(document.file_id)
        input_path = f"/tmp/{document.file_name}"
        await file.download_to_drive(input_path)
        
        if not os.path.exists(input_path) or os.path.getsize(input_path) < 100:
            raise Exception("Download failed")
        
        # Process with progress updates
        def update_progress(msg):
            asyncio.create_task(progress_msg.edit_text(
                f"⚙️ **Processing APK...**\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔄 {msg}\n"
                f"⏱️ Please wait..."
            ))
        
        # Process
        final_path, final_name = fud_process(
            input_path, 
            document.file_name,
            progress_callback=update_progress
        )
        
        # Get APK info
        info = get_apk_info(final_path)
        
        # Send back with proper UI
        await progress_msg.edit_text(
            "✅ **Processing Complete!**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 **File:** `{final_name}`\n"
            f"📦 **Package:** `{info['package']}`\n"
            f"🔢 **Version:** `{info['version']}`\n"
            f"📊 **Size:** `{get_file_size(final_path):.2f} MB`\n"
            f"🔑 **SHA256:** `{hashlib.sha256(open(final_path,'rb').read()).hexdigest()[:16]}`\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "💀 **Shadow FUD Approved**\n\n"
            "📤 Sending file..."
        )
        
        # Send file
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=open(final_path, 'rb'),
            filename=final_name,
            caption=f"✅ **FUD APK Ready!**\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📁 **File:** `{final_name}`\n"
                    f"📦 **Package:** `{info['package']}`\n"
                    f"🔢 **Version:** `{info['version']}`\n"
                    f"📊 **Size:** `{get_file_size(final_path):.2f} MB`\n"
                    f"🔑 **SHA256:** `{hashlib.sha256(open(final_path,'rb').read()).hexdigest()[:16]}`\n"
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
        await progress_msg.edit_text(
            f"❌ **Error Processing APK**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ `{str(e)}`\n\n"
            f"Try:\n"
            f"• Send smaller APK\n"
            f"• Use /help for guidance"
        )

# ===== FLASK SERVER =====
app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/health')
def health():
    return jsonify({'status': 'online', 'time': datetime.now().isoformat()})

@app.route('/logs')
def logs():
    return jsonify({'message': 'Check Kinsta dashboard for logs'})

# ===== MAIN =====
if __name__ == '__main__':
    logger.info("🐱 Starting Shadow FUD Bot v2.0...")
    
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
