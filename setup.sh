#!/bin/bash
apt-get update
apt-get install -y --no-install-recommends \
    apktool \
    openjdk-17-jdk \
    aapt \
    wget \
    unzip

# Create debug keystore
if [ ! -f "debug.keystore" ]; then
    keytool -genkey -v \
        -keystore debug.keystore \
        -alias androiddebugkey \
        -keyalg RSA \
        -keysize 2048 \
        -validity 10000 \
        -dname "CN=Android Debug, O=Android, C=US" \
        -storepass android \
        -keypass android
fi

echo "✅ Setup complete!"
