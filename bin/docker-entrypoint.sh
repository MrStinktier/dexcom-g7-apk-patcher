#!/bin/bash

git clone https://github.com/LuigiVampa92/xapk-to-apk
cd xapk-to-apk
chmod +x xapktoapk.py

cd ..

wget  --user-agent='Mozilla/5.0' \
      -O dexcom.stock.xapk \
      https://d.apkpure.com/b/APK/com.dexcom.g7?version=1.6.1.4537

python ./xapk-to-apk/xapktoapk.py dexcom.stock.xapk

bin/build.sh ./dexcom.stock.apk
mv dexcom.patched.apk /output
