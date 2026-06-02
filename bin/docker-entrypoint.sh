#!/bin/bash

wget  --user-agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36' \
      -O dexcom.stock.apk \
      https://d.apkpure.com/b/APK/com.dexcom.g7?versionCode=4537
bin/build.sh ./dexcom.stock.apk
mv dexcom.patched.apk /output
