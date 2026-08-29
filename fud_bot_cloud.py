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
import zipfile
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
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB

# ===== UI TEMPLATES =====
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Shadow FUD Bot Ultimate</title>
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
        .cmd .success { color: #00ff00; font-weight: bold; }
        .stats { display: flex; justify-content: space-around; margin: 20px 0; color: #888; }
        .stats span { color: #00ff00; font-weight: bold; }
        .footer { color: #444; margin-top: 20px; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🐱 SHADOW FUD BOT</h1>
        <div class="status">● ULTIMATE EDITION</div>
        <div class="cmd">
            <span class="prompt">root@shadow:~$</span> <span class="input">./fud_bot --ultimate</span><br>
            <span class="output">[+] Bot v4.0 Ultimate initialized</span><br>
            <span class="output">[+] Token verified ✓</span><br>
            <span class="output">[+] Fast processing mode: ACTIVE</span><br>
            <span class="output">[+] FUD engine: OPTIMIZED</span><br>
            <span class="output">[+] Max file size: 25MB</span><br>
            <span class="output">[+] Processing time: 15-30s</span><br>
            <span class="success">[+] READY FOR APK FILES</span><br>
            <span class="prompt">root@shadow:~$</span> <span class="input">_</span>
        </div>
        <div class="stats">
            <div>📦 Status: <span>🟢 Online</span></div>
            <div>⚡ Engine: <span>Ultimate</span></div>
            <div>⏱️ Speed: <span>Fast</span></div>
        </div>
        <p style="color: #888;">🔥 Send APK to <strong style="color:#00ff00;">@FudderBot</strong> on Telegram</p>
        <div class="footer">━━━━━━━━━━━━━━━━━━━━━<br>💀 Shadow FUD Bot Ultimate v4.0</div>
    </div>
</body>
</html>
'''

# ===== HELPER FUNCTIONS =====
def rand_str(n=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

def get_file_size_mb(file_path):
    return os.path.getsize(file_path) / (1024 * 1024)

def get_apk_info(apk_path):
    info = {
        'package': 'Unknown',
        'version': 'Unknown',
        'sdk': 'Unknown',
        'size': f"{get_file_size_mb(apk_path):.2f} MB"
    }
    try:
        result = subprocess.run(
            ['aapt', 'dump', 'badging', apk_path],
            capture_output=True, text=True, timeout=5
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

def fast_fud_process(input_apk_path, original_name, progress_callback=None):
    """ULTRA FAST FUD processing - optimized for Kinsta"""
    work_dir = tempfile.mkdtemp()
    output_dir = tempfile.mkdtemp()
    
    try:
        start_time = time.time()
        
        if progress_callback:
            progress_callback("📦 Decoding (fast mode)...")
        
        # Step 1: Decode with minimal options
        decode_cmd = [
            'apktool', 'd', 
            input_apk_path, 
            '-o', work_dir, 
            '-f',
            '--no-assets',  # Skip assets for speed
            '--match-original'  # Keep original structure
        ]
        result = subprocess.run(decode_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            # If no-assets fails, try without it
            decode_cmd = ['apktool', 'd', input_apk_path, '-o', work_dir, '-f']
            result = subprocess.run(decode_cmd, capture_output=True, text=True, timeout=40)
            if result.returncode != 0:
                raise Exception(f"apktool failed: {result.stderr[:150]}")
        
        logger.info(f"✅ Decoded in {time.time() - start_time:.1f}s")
        
        if progress_callback:
            progress_callback("🔧 Modifying manifest...")
        
        # Step 2: Quick manifest modification
        manifest_path = os.path.join(work_dir, 'AndroidManifest.xml')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                content = f.read()
            
            # Simple modifications
            content = re.sub(r'android:debuggable="true"', '', content)
            content = re.sub(r'debuggable="true"', '', content)
            
            # Add fake permissions quickly
            fake_perms = [
                '<uses-permission android:name="android.permission.READ_LOGS"/>',
                '<uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW"/>'
            ]
            
            insert_pos = content.find('</manifest>')
            if insert_pos != -1:
                for perm in fake_perms:
                    content = content[:insert_pos] + perm + content[insert_pos:]
            
            with open(manifest_path, 'w') as f:
                f.write(content)
            logger.info("✅ Manifest modified")
        
        if progress_callback:
            progress_callback("💉 Quick smali patch...")
        
        # Step 3: Quick smali patch (only main files)
        smali_dir = os.path.join(work_dir, 'smali')
        if os.path.exists(smali_dir):
            patched = 0
            # Find main activity
            main_files = []
            for root, dirs, files in os.walk(smali_dir):
                for file in files:
                    if file.endswith('.smali') and ('Main' in file or 'Activity' in file):
                        main_files.append(os.path.join(root, file))
                        if len(main_files) >= 3:
                            break
                if len(main_files) >= 3:
                    break
            
            for file_path in main_files:
                try:
                    with open(file_path, 'r') as f:
                        smali_content = f.read()
                    
                    if ';->onCreate' in smali_content and 'return-void' in smali_content:
                        smali_content = smali_content.replace(
                            'return-void',
                            'return-void\n\n.method private fudGuard()V\n    .locals 1\n    const-string v0, "FUD_ACTIVE"\n    return-void\n.end method'
                        )
                        with open(file_path, 'w') as f:
                            f.write(smali_content)
                        patched += 1
                except:
                    continue
            logger.info(f"✅ Patched {patched} files")
        
        if progress_callback:
            progress_callback("🏗️ Rebuilding (optimized)...")
        
        # Step 4: Rebuild with speed optimizations
        rebuilt_apk = os.path.join(output_dir, f'rebuilt_{rand_str()}.apk')
        build_cmd = [
            'apktool', 'b', 
            work_dir, 
            '-o', rebuilt_apk,
            '--use-aapt2',  # Faster
            '--no-crunch'   # Skip resource crunching
        ]
        result = subprocess.run(build_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            # Fallback without optimizations
            build_cmd = ['apktool', 'b', work_dir, '-o', rebuilt_apk]
            result = subprocess.run(build_cmd, capture_output=True, text=True, timeout=40)
            if result.returncode != 0:
                raise Exception(f"apktool build failed: {result.stderr[:150]}")
        
        logger.info(f"✅ Rebuilt in {time.time() - start_time:.1f}s")
        
        if progress_callback:
            progress_callback("🔑 Signing...")
        
        # Step 5: Sign (use pre-created keystore)
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
            ], capture_output=True, check=True, timeout=15)
        
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
            ], capture_output=True, check=True, timeout=15)
        except:
            # Try jarsigner
            try:
                subprocess.run([
                    'jarsigner',
                    '-sigalg', 'SHA1withRSA',
                    '-digestalg', 'SHA1',
                    '-keystore', debug_keystore,
                    '-storepass', 'android',
                    '-keypass', 'android',
                    rebuilt_apk, 'androiddebugkey'
                ], capture_output=True, check=True, timeout=15)
                signed_apk = rebuilt_apk
            except:
                signed_apk = rebuilt_apk
                logger.warning("⚠️ Using unsigned APK")
        
        # Verify signed APK
        if not os.path.exists(signed_apk) or os.path.getsize(signed_apk) < 1000:
            raise Exception("Signing failed")
        
        # Finalize
        final_name = f"FUD_{original_name.replace('.apk', '')}_{rand_str()}.apk"
        final_path = os.path.join(output_dir, final_name)
        os.rename(signed_apk, final_path)
        
        total_time = time.time() - start_time
        logger.info(f"✅ FUD APK created in {total_time:.1f}s")
        
        if progress_callback:
            progress_callback(f"✅ Done! ({total_time:.0f}s)")
        
        return final_path, final_name
        
    except subprocess.TimeoutExpired:
        raise Exception(f"⏱️ Processing timeout (try smaller APK)")
    except Exception as e:
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
        [InlineKeyboardButton("📊 Status", callback_data='status')],
        [InlineKeyboardButton("❓ Help", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔥 **SHADOW FUD BOT ULTIMATE** 🔥\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 **Version:** v4.0 Ultimate\n"
        "🔹 **Status:** 🟢 Online\n"
        "🔹 **FUD Engine:** Optimized\n"
        "🔹 **Max Size:** 25MB\n"
        "🔹 **Speed:** 15-30 seconds\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 **Send APK** to make it FUD!\n"
        "⚡ Fastest processing on Kinsta\n\n"
        "⚠️ Educational purposes only",
        reply_markup=reply_markup
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **HOW TO USE**\n\n"
        "1️⃣ Send `.apk` file (<25MB)\n"
        "2️⃣ Wait 15-30 seconds\n"
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
        "⚡ Engine: Ultimate Optimized\n"
        "📦 Max APK: 25MB\n"
        "⏱️ Processing: 15-30s\n"
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
            "Upload APK (max 25MB)\n"
            "Optional: Add LHOST/LPORT in caption"
        )
    elif query.data == 'help':
        await query.edit_message_text(
            "📖 **Instructions**\n\n"
            "1. Send APK file\n"
            "2. Wait 15-30 seconds\n"
            "3. Get FUD version\n\n"
            "⚠️ File must be <25MB"
        )
    elif query.data == 'status':
        await query.edit_message_text(
            "📊 **Status:** 🟢 Online\n"
            "⚡ **Engine:** Ultimate\n"
            "📦 **Max size:** 25MB\n"
            "⏱️ **Processing:** 15-30s"
        )

async def handle_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document:
        return
    
    if not document.file_name or not document.file_name.endswith('.apk'):
        await update.message.reply_text("❌ Please send an **APK** file")
        return
    
    # Check file size
    size_mb = document.file_size / (1024 * 1024)
    if document.file_size > MAX_FILE_SIZE:
        await update.message.reply_text(
            f"❌ **File too large**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Your file: `{size_mb:.1f} MB`\n"
            f"📊 Max allowed: `25 MB`\n\n"
            f"💡 Use smaller APK"
        )
        return
    
    # Processing message
    progress_msg = await update.message.reply_text(
        f"⚙️ **Processing APK...**\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Size: `{size_mb:.1f} MB`\n"
        f"🔄 Starting... (0/4)"
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
                f"📊 Size: `{size_mb:.1f} MB`\n"
                f"📡 LHOST: `{lhost}`\n"
                f"📡 LPORT: `{lport}`\n"
                f"🔄 Starting... (0/4)"
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
                f"📊 Size: `{size_mb:.1f} MB`\n"
                f"🔄 {msg}\n"
                f"⏱️ Please wait (15-30s)"
            ))
        
        # Process
        final_path, final_name = fast_fud_process(
            input_path,
            document.file_name,
            progress_callback=update_progress
        )
        
        # Get info
        info = get_apk_info(final_path)
        final_size = get_file_size_mb(final_path)
        
        # Send confirmation
        await progress_msg.edit_text(
            "✅ **Processing Complete!**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 File: `{final_name}`\n"
            f"📦 Package: `{info['package']}`\n"
            f"🔢 Version: `{info['version']}`\n"
            f"📊 Size: `{final_size:.2f} MB`\n"
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
                        f"📊 Size: `{final_size:.2f} MB`\n"
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
            "💀 **Shadow FUD Bot Ultimate**"
        )
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        error_msg = str(e)
        if "timeout" in error_msg.lower():
            error_msg = "⏱️ Processing timeout (APK may be complex)"
        elif "apktool" in error_msg.lower():
            error_msg = "⚠️ APK structure issue (try different APK)"
        elif "memory" in error_msg.lower():
            error_msg = "💾 Memory limit reached (try smaller APK)"
        
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
    return jsonify({'status': 'online', 'version': '4.0 Ultimate', 'max_size': '25MB'})

# ===== MAIN =====
if __name__ == '__main__':
    logger.info("🐱 Starting Shadow FUD Bot Ultimate v4.0...")
    logger.info(f"📦 Max file size: {MAX_FILE_SIZE/(1024*1024)}MB")
    logger.info("⚡ Optimized for fast processing")
    
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
