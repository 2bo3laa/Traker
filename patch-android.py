#!/usr/bin/env python3
"""Runs in CI after `npx cap add android`.
Adds: switchable launcher icons (6 activity-aliases), a tiny native plugin
(IconSwitcher) and the notification permission. Writes the manifest last."""
import json, re, os, sys
from PIL import Image, ImageDraw

PRESETS = [  # same order as ICP in index.html: bg1, bg2, accent1, accent2
    ("#3d2166", "#140b1f", "#ffc857", "#ff5f6d"),
    ("#262626", "#050505", "#d4af37", "#f5d77a"),
    ("#0f3d2e", "#04120c", "#2ee59d", "#c6f24e"),
    ("#0f2a5a", "#050d1f", "#4da3ff", "#7c5cff"),
    ("#5a1a3a", "#1a0a14", "#ff5c93", "#ffa3c4"),
    ("#4a1a0a", "#120706", "#ff6a1a", "#ffc21a"),
]
N, SS = 432, 4

def rgb(h): return tuple(int(h[i:i+2], 16) for i in (1, 3, 5))

def gradient(c1, c2):
    a, b = rgb(c1), rgb(c2)
    img = Image.new("RGB", (N, N))
    px = img.load()
    for y in range(N):
        for x in range(N):
            t = (0.35 * x + 0.65 * y) / N
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return img

def make_icon(p):
    k = SS * N / 1024.0
    base = gradient(p[0], p[1]).convert("RGBA")
    # progress ring
    m = Image.new("L", (N * SS, N * SS), 0); d = ImageDraw.Draw(m)
    c, r, w = N * SS / 2, 270 * k, 64 * k
    box = [c - r - w / 2, c - r - w / 2, c + r + w / 2, c + r + w / 2]
    d.arc(box, -90, -90 + 360 * 0.78, fill=255, width=int(w))
    import math
    for ang in (-90, -90 + 360 * 0.78):
        ex, ey = c + r * math.cos(math.radians(ang)), c + r * math.sin(math.radians(ang))
        d.ellipse([ex - w / 2, ey - w / 2, ex + w / 2, ey + w / 2], fill=255)
    m = m.resize((N, N), Image.LANCZOS)
    track = Image.new("L", (N * SS, N * SS), 0); ImageDraw.Draw(track).ellipse(
        [c - r - w / 2, c - r - w / 2, c + r + w / 2, c + r + w / 2], fill=41)
    ImageDraw.Draw(track).ellipse([c - r + w / 2, c - r + w / 2, c + r - w / 2, c + r - w / 2], fill=0)
    track = track.resize((N, N), Image.LANCZOS)
    base.paste(Image.new("RGBA", (N, N), (255, 244, 234, 255)), mask=track)
    base.paste(gradient(p[2], p[3]).convert("RGBA"), mask=m)
    # check mark
    cm = Image.new("L", (N * SS, N * SS), 0); d = ImageDraw.Draw(cm)
    pts = [(392 * k, 522 * k), (478 * k, 608 * k), (640 * k, 424 * k)]
    d.line(pts, fill=255, width=int(76 * k), joint="curve")
    for (x, y) in pts:
        d.ellipse([x - 38 * k, y - 38 * k, x + 38 * k, y + 38 * k], fill=255)
    cm = cm.resize((N, N), Image.LANCZOS)
    base.paste(Image.new("RGBA", (N, N), (255, 244, 234, 255)), mask=cm)
    # rounded corners
    rm = Image.new("L", (N * SS, N * SS), 0)
    ImageDraw.Draw(rm).rounded_rectangle([0, 0, N * SS - 1, N * SS - 1], radius=int(0.22 * N * SS), fill=255)
    rm = rm.resize((N, N), Image.LANCZOS)
    out = Image.new("RGBA", (N, N), (0, 0, 0, 0)); out.paste(base, mask=rm)
    return out

def fetch_pages(app):
    """Exact 604-page (Madani mushaf) boundaries -> pages.json (optional; app falls back to an estimate)."""
    import urllib.request, time
    for attempt in range(3):
        try:
            req = urllib.request.Request("https://api.alquran.cloud/v1/quran/quran-uthmani", headers={"User-Agent": "Mozilla/5.0"})
            d = json.load(urllib.request.urlopen(req, timeout=60))
            starts, last, g = [], 0, 0
            for s in d["data"]["surahs"]:
                for a in s["ayahs"]:
                    if a["page"] != last:
                        starts.append(g); last = a["page"]
                    g += 1
            assert len(starts) == 604 and last == 604 and g == 6236, (len(starts), last, g)
            out = f"{app}/assets/public"; os.makedirs(out, exist_ok=True)
            json.dump(starts, open(f"{out}/pages.json", "w"))
            print("pages.json OK")
            return
        except Exception as e:
            print("pages fetch attempt", attempt + 1, "failed:", e); time.sleep(2)
    print("WARNING: pages.json not created; the app will estimate pages")

def main():
    cfg = json.load(open("capacitor.config.json", encoding="utf-8"))
    pkg = cfg["appId"]
    app = "android/app/src/main"
    man_path = f"{app}/AndroidManifest.xml"
    man = open(man_path, encoding="utf-8").read()

    # --- 1. compute the new manifest first (fail early, before touching anything)
    pat = re.compile(r'<intent-filter>\s*<action android:name="android.intent.action.MAIN"\s*/>\s*'
                     r'<category android:name="android.intent.category.LAUNCHER"\s*/>\s*</intent-filter>')
    if not pat.search(man):
        sys.exit("launcher intent-filter not found; manifest left untouched")
    man = pat.sub("", man, count=1)
    aliases = ""
    for i in range(len(PRESETS)):
        aliases += f'''
        <activity-alias android:name=".Alias{i}" android:targetActivity=".MainActivity"
            android:enabled="{"true" if i == 0 else "false"}" android:exported="true"
            android:icon="@drawable/ic_alias_{i}" android:roundIcon="@drawable/ic_alias_{i}"
            android:label="@string/app_name">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity-alias>'''
    man = man.replace("</application>", aliases + "\n    </application>", 1)
    if "POST_NOTIFICATIONS" not in man:
        man = man.replace("</manifest>",
            '    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />\n</manifest>', 1)

    if "USE_EXACT_ALARM" not in man:
        man = man.replace("</manifest>",
            '    <uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" />\n    <uses-permission android:name="android.permission.USE_EXACT_ALARM" />\n</manifest>', 1)

    if "ACCESS_COARSE_LOCATION" not in man:
        man = man.replace("</manifest>",
            '    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />\n    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />\n</manifest>', 1)

    # --- adhan sound (optional): put adhan.mp3 next to index.html
    import shutil
    for nm in ("adhan.mp3", "adhan_fajr.mp3"):
        if os.path.exists(nm):
            os.makedirs(f"{app}/res/raw", exist_ok=True)
            shutil.copy(nm, f"{app}/res/raw/{nm}")

    # --- 2. icons
    dr = f"{app}/res/drawable-nodpi"; os.makedirs(dr, exist_ok=True)
    for i, p in enumerate(PRESETS):
        make_icon(p).save(f"{dr}/ic_alias_{i}.png")

    # --- 3. native plugin + MainActivity
    jd = f"{app}/java/{pkg.replace('.', '/')}"; os.makedirs(jd, exist_ok=True)
    open(f"{jd}/IconSwitcherPlugin.java", "w", encoding="utf-8").write(f'''package {pkg};

import android.content.ComponentName;
import android.content.pm.PackageManager;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "IconSwitcher")
public class IconSwitcherPlugin extends Plugin {{
    private static final int COUNT = {len(PRESETS)};

    @PluginMethod
    public void setIcon(PluginCall call) {{
        Integer idx = call.getInt("index");
        if (idx == null || idx < 0 || idx >= COUNT) {{ call.reject("bad index"); return; }}
        PackageManager pm = getContext().getPackageManager();
        String pkg = getContext().getPackageName();
        pm.setComponentEnabledSetting(new ComponentName(pkg, "{pkg}.Alias" + idx),
            PackageManager.COMPONENT_ENABLED_STATE_ENABLED, PackageManager.DONT_KILL_APP);
        for (int i = 0; i < COUNT; i++) {{
            if (i == idx) continue;
            pm.setComponentEnabledSetting(new ComponentName(pkg, "{pkg}.Alias" + i),
                PackageManager.COMPONENT_ENABLED_STATE_DISABLED, PackageManager.DONT_KILL_APP);
        }}
        call.resolve();
    }}
}}
''')
    open(f"{jd}/MainActivity.java", "w", encoding="utf-8").write(f'''package {pkg};

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {{
    @Override
    public void onCreate(Bundle savedInstanceState) {{
        registerPlugin(IconSwitcherPlugin.class);
        registerPlugin(WidgetBridgePlugin.class);
        registerPlugin(AdhanPlugin.class);
        super.onCreate(savedInstanceState);
    }}
}}
''')

    # --- 3b. home-screen widgets
    import patch_widgets
    man = patch_widgets.apply(app, pkg, man)
    import patch_adhan
    man = patch_adhan.apply(app, pkg, man)

    fetch_pages(app)

    # --- 4. manifest last
    open(man_path, "w", encoding="utf-8").write(man)
    print("patched OK")

main()
