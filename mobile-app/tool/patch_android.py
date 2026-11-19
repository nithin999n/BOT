"""
Run after `flutter create` (CI does this). Adds the permissions BOT needs to
android/app/src/main/AndroidManifest.xml and names the app "BOT".
"""
import pathlib
import re
import sys

manifest = pathlib.Path("android/app/src/main/AndroidManifest.xml")
s = manifest.read_text(encoding="utf-8")

PERMISSIONS = [
    "android.permission.INTERNET",
    "android.permission.RECORD_AUDIO",
    "android.permission.ACCESS_NETWORK_STATE",
    "android.permission.ACCESS_WIFI_STATE",
]
SPEECH_QUERY = """    <queries>
        <intent>
            <action android:name="android.speech.RecognitionService" />
        </intent>
    </queries>
"""

if "usesCleartextTraffic" not in s:  # LAN uses plain ws:// on your own Wi-Fi
    s = s.replace("<application", '<application\n        android:usesCleartextTraffic="true"', 1)

s = re.sub(r'android:label="[^"]*"', 'android:label="BOT"', s, count=1)

for perm in PERMISSIONS:
    if perm not in s:
        s = s.replace("<application", f'<uses-permission android:name="{perm}" />\n    <application', 1)

if "android.speech.RecognitionService" not in s:
    s = s.replace("</manifest>", SPEECH_QUERY + "</manifest>", 1)

manifest.write_text(s, encoding="utf-8")
print(s)
if "RECORD_AUDIO" not in s or "RecognitionService" not in s:
    sys.exit("patching AndroidManifest.xml failed")
