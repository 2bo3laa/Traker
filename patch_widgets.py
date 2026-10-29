#!/usr/bin/env python3
"""Home-screen widgets for جدولي. Called from patch-android.py (CI).
apply(app, pkg, manifest_text) writes java/xml/drawable files and returns the manifest."""
import os

def esc(src):
    out = []
    for ch in src:
        if ord(ch) < 128:
            out.append(ch)
        else:
            b = ch.encode("utf-16-be")
            for i in range(0, len(b), 2):
                out.append("\\u%02x%02x" % (b[i], b[i + 1]))
    return "".join(out)

def w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(text)

NS = 'xmlns:android="http://schemas.android.com/apk/res/android"'

UTIL = r'''package __PKG__;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.os.Build;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.ForegroundColorSpan;
import android.os.SystemClock;
import android.view.View;
import android.widget.RemoteViews;
import org.json.JSONObject;
import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.Date;
import java.util.Iterator;
import java.util.Locale;

public final class WidgetUtil {
    private WidgetUtil() {}

    static final String PREFS = "jadwali_widget";
    static final String[] KEYS = {"f", "s", "d", "a", "m", "i"};
    static final String[] NAMES = {"الفجر", "الشروق", "الظهر", "العصر", "المغرب", "العشاء"};
    static final int[] T_IDS = {R.id.wd_t0, R.id.wd_t1, R.id.wd_t2, R.id.wd_t3, R.id.wd_t4, R.id.wd_t5};
    static final int[] N_IDS = {R.id.wd_n0, R.id.wd_n1, R.id.wd_n2, R.id.wd_n3, R.id.wd_n4, R.id.wd_n5};
    static final int YELLOW = 0xFFFFEB3B;
    static final int WHITE = 0xFFFFFFFF;

    static void save(Context c, String json) {
        c.getSharedPreferences(PREFS, 0).edit().putString("data", json).apply();
    }

    static JSONObject load(Context c) {
        try {
            return new JSONObject(c.getSharedPreferences(PREFS, 0).getString("data", "{}"));
        } catch (Exception e) {
            return new JSONObject();
        }
    }

    static String dateKey(long ms) {
        Calendar cal = Calendar.getInstance();
        cal.setTimeInMillis(ms);
        return String.format(Locale.US, "%04d-%02d-%02d", cal.get(Calendar.YEAR), cal.get(Calendar.MONTH) + 1, cal.get(Calendar.DAY_OF_MONTH));
    }

    static String ar(int n) {
        String s = String.valueOf(n);
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            if (ch >= '0' && ch <= '9') b.append((char) (0x0660 + (ch - '0')));
            else b.append(ch);
        }
        return b.toString();
    }

    /** returns {index into KEYS, millis} of the next prayer (sunrise excluded), or null */
    static long[] nextPrayer(JSONObject days, long now) {
        if (days == null) return null;
        long best = Long.MAX_VALUE;
        int bi = -1;
        Iterator<String> it = days.keys();
        while (it.hasNext()) {
            JSONObject d = days.optJSONObject(it.next());
            if (d == null) continue;
            for (int i = 0; i < 6; i++) {
                if (i == 1) continue;
                long t = d.optLong(KEYS[i], 0);
                if (t > now && t < best) { best = t; bi = i; }
            }
        }
        return bi < 0 ? null : new long[]{bi, best};
    }

    static PendingIntent openApp(Context c) {
        Intent li = c.getPackageManager().getLaunchIntentForPackage(c.getPackageName());
        if (li == null) return null;
        return PendingIntent.getActivity(c, 0, li, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    static void countdown(RemoteViews v, int labelId, int cdId, int txtId, long[] nx, long now) {
        if (nx == null) {
            v.setTextViewText(labelId, "افتح التطبيق لتحديث المواقيت");
            v.setViewVisibility(cdId, View.GONE);
            v.setViewVisibility(txtId, View.VISIBLE);
            v.setTextViewText(txtId, "--:--");
            return;
        }
        v.setTextViewText(labelId, "باقي على " + NAMES[(int) nx[0]]);
        if (Build.VERSION.SDK_INT >= 24) {
            v.setViewVisibility(txtId, View.GONE);
            v.setViewVisibility(cdId, View.VISIBLE);
            v.setChronometerCountDown(cdId, true);
            v.setChronometer(cdId, SystemClock.elapsedRealtime() + (nx[1] - now), null, true);
        } else {
            v.setViewVisibility(cdId, View.GONE);
            v.setViewVisibility(txtId, View.VISIBLE);
            long mins = Math.max(0, (nx[1] - now) / 60000);
            v.setTextViewText(txtId, ar((int) (mins / 60)) + ":" + ar((int) (mins % 60)));
        }
    }

    static final class Th {
        int bg = 0xFF140B1F, panel = 0xFF1F1333, ink = 0xFFFFF4EA, soft = 0xFFBBA8CC, acc = 0xFFFFB547;
    }

    static int pc(JSONObject o, String k, int d) {
        try { return Color.parseColor(o.optString(k, "")); } catch (Exception e) { return d; }
    }

    static Th theme(JSONObject data) {
        Th t = new Th();
        JSONObject o = data.optJSONObject("th");
        if (o == null) return t;
        t.bg = pc(o, "bg", t.bg);
        t.panel = pc(o, "panel", t.panel);
        t.ink = pc(o, "ink", t.ink);
        t.soft = pc(o, "soft", t.soft);
        t.acc = pc(o, "acc", t.acc);
        return t;
    }

    static void paint(RemoteViews v, int id, int color) {
        v.setInt(id, "setColorFilter", color);
    }

    static void clicks(Context c, RemoteViews v) {
        PendingIntent pi = openApp(c);
        if (pi != null) v.setOnClickPendingIntent(R.id.wd_root, pi);
    }

    static RemoteViews buildBig(Context c, JSONObject data, Th t, long[] nx, long now, String todayKey) {
        RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.widget_big);
        JSONObject days = data.optJSONObject("days");
        JSONObject today = days == null ? null : days.optJSONObject(todayKey);
        SimpleDateFormat f = new SimpleDateFormat("HH:mm", Locale.US);
        paint(v, R.id.wd_bg, t.bg);
        paint(v, R.id.wd_pbg, t.panel);
        for (int i = 0; i < 6; i++) {
            long tm = today == null ? 0 : today.optLong(KEYS[i], 0);
            v.setTextViewText(T_IDS[i], tm > 0 ? f.format(new Date(tm)) : "--:--");
            v.setTextViewText(N_IDS[i], NAMES[i]);
            int col = (nx != null && nx[0] == i) ? t.acc : t.ink;
            v.setTextColor(T_IDS[i], col);
            v.setTextColor(N_IDS[i], col);
        }
        countdown(v, R.id.wd_label, R.id.wd_cd, R.id.wd_cd_txt, nx, now);
        v.setTextColor(R.id.wd_label, t.ink);
        v.setTextColor(R.id.wd_cd, t.acc);
        v.setTextColor(R.id.wd_cd_txt, t.acc);
        clicks(c, v);
        return v;
    }

    static RemoteViews buildSmall(Context c, Th t, long[] nx, long now) {
        RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.widget_small);
        paint(v, R.id.wd_bg, t.bg);
        countdown(v, R.id.wd_label, R.id.wd_cd, R.id.wd_cd_txt, nx, now);
        v.setTextColor(R.id.wd_label, t.ink);
        v.setTextColor(R.id.wd_cd, t.acc);
        v.setTextColor(R.id.wd_cd_txt, t.acc);
        clicks(c, v);
        return v;
    }

    static RemoteViews buildHabits(Context c, JSONObject data, Th t, String todayKey) {
        RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.widget_habits);
        JSONObject h = data.optJSONObject("habits");
        boolean ok = h != null && todayKey.equals(h.optString("date"));
        int done = ok ? h.optInt("done", 0) : 0;
        int total = ok ? h.optInt("total", 0) : 0;
        paint(v, R.id.wd_bg, t.bg);
        v.setTextViewText(R.id.wd_title, "عاداتك النهاردة");
        v.setTextColor(R.id.wd_title, t.soft);
        v.setTextColor(R.id.wd_count, t.acc);
        v.setTextColor(R.id.wd_sub, t.ink);
        int filled = 0;
        if (ok && total > 0) {
            filled = Math.round(10f * Math.min(done, total) / total);
            if (done > 0 && filled == 0) filled = 1;
            v.setTextViewText(R.id.wd_count, ar(done) + " / " + ar(total));
            v.setTextViewText(R.id.wd_sub, done >= total ? "كل عاداتك خلصت 🎉" : "فاضل " + ar(total - done));
        } else if (ok) {
            v.setTextViewText(R.id.wd_count, "—");
            v.setTextViewText(R.id.wd_sub, "مفيش عادات النهاردة");
        } else {
            v.setTextViewText(R.id.wd_count, "—");
            v.setTextViewText(R.id.wd_sub, "افتح التطبيق لتحديث العادات");
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 10; i++) sb.append(i < filled ? "●" : "○");
        SpannableString sp = new SpannableString(sb.toString());
        if (filled > 0) sp.setSpan(new ForegroundColorSpan(t.acc), 0, filled, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        if (filled < 10) sp.setSpan(new ForegroundColorSpan(t.soft), filled, 10, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        v.setTextViewText(R.id.wd_bar, sp);
        clicks(c, v);
        return v;
    }

    static RemoteViews buildHijri(Context c, JSONObject data, Th t, long[] nx, long now, String todayKey) {
        RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.widget_hijri);
        JSONObject days = data.optJSONObject("days");
        JSONObject today = days == null ? null : days.optJSONObject(todayKey);
        paint(v, R.id.wd_bg, t.bg);
        String day = new SimpleDateFormat("EEEE", new Locale("ar")).format(new Date(now));
        String hij = today == null ? "" : today.optString("h", "");
        v.setTextViewText(R.id.wd_hijri, hij.length() > 0 ? day + " " + hij : day);
        v.setTextColor(R.id.wd_hijri, t.ink);
        v.setTextColor(R.id.wd_next, t.acc);
        if (nx != null) {
            String tm = new SimpleDateFormat("HH:mm", Locale.US).format(new Date(nx[1]));
            v.setTextViewText(R.id.wd_next, "الجاية: " + NAMES[(int) nx[0]] + "  " + tm);
        } else {
            v.setTextViewText(R.id.wd_next, "افتح التطبيق لتحديث المواقيت");
        }
        clicks(c, v);
        return v;
    }

    static int[] ids(AppWidgetManager m, Context c, Class<?> k) {
        return m.getAppWidgetIds(new ComponentName(c, k));
    }

    public static void refreshAll(Context c) {
        try {
            AppWidgetManager m = AppWidgetManager.getInstance(c);
            long now = System.currentTimeMillis();
            String todayKey = dateKey(now);
            JSONObject data = load(c);
            long[] nx = nextPrayer(data.optJSONObject("days"), now);
            Th th = theme(data);
            int[] big = ids(m, c, PrayerBigWidget.class);
            int[] small = ids(m, c, PrayerSmallWidget.class);
            int[] habits = ids(m, c, HabitsWidget.class);
            int[] hijri = ids(m, c, HijriWidget.class);
            for (int id : big) m.updateAppWidget(id, buildBig(c, data, th, nx, now, todayKey));
            for (int id : small) m.updateAppWidget(id, buildSmall(c, th, nx, now));
            for (int id : habits) m.updateAppWidget(id, buildHabits(c, data, th, todayKey));
            for (int id : hijri) m.updateAppWidget(id, buildHijri(c, data, th, nx, now, todayKey));
            int total = big.length + small.length + habits.length + hijri.length;
            schedule(c, total == 0, nx == null ? null : Long.valueOf(nx[1]), now);
        } catch (Exception e) {
            // never crash the app because of a widget
        }
    }

    static void schedule(Context c, boolean cancelOnly, Long nextMs, long now) {
        AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
        if (am == null) return;
        Intent i = new Intent(c, WidgetRefreshReceiver.class);
        i.setAction("__PKG__.WIDGET_TICK");
        PendingIntent pi = PendingIntent.getBroadcast(c, 7731, i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        if (cancelOnly) { am.cancel(pi); return; }
        Calendar cal = Calendar.getInstance();
        cal.setTimeInMillis(now);
        cal.add(Calendar.DAY_OF_YEAR, 1);
        cal.set(Calendar.HOUR_OF_DAY, 0);
        cal.set(Calendar.MINUTE, 0);
        cal.set(Calendar.SECOND, 0);
        cal.set(Calendar.MILLISECOND, 0);
        long at = cal.getTimeInMillis();
        if (nextMs != null && nextMs.longValue() < at) at = nextMs.longValue();
        at += 1500;
        if (at <= now) at = now + 60000;
        try {
            if (Build.VERSION.SDK_INT >= 31 && !am.canScheduleExactAlarms()) {
                am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi);
            } else {
                am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi);
            }
        } catch (SecurityException e) {
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi);
        }
    }
}
'''

PLUGIN = r'''package __PKG__;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "WidgetBridge")
public class WidgetBridgePlugin extends Plugin {
    @PluginMethod
    public void setData(PluginCall call) {
        String json = call.getString("json");
        if (json == null) { call.reject("no json"); return; }
        WidgetUtil.save(getContext(), json);
        WidgetUtil.refreshAll(getContext());
        call.resolve();
    }
}
'''

RECEIVER = r'''package __PKG__;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class WidgetRefreshReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        WidgetUtil.refreshAll(context);
    }
}
'''

PROVIDER = r'''package __PKG__;

import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;

public class __NAME__ extends AppWidgetProvider {
    @Override
    public void onUpdate(Context c, AppWidgetManager m, int[] ids) { WidgetUtil.refreshAll(c); }
    @Override
    public void onEnabled(Context c) { WidgetUtil.refreshAll(c); }
    @Override
    public void onDisabled(Context c) { WidgetUtil.refreshAll(c); }
}
'''

def tv(id_, size, bold=False, color="#FFFFFF", gravity=None, extra=""):
    g = f'\n        android:gravity="{gravity}"' if gravity else ""
    st = '\n        android:textStyle="bold"' if bold else ""
    return (f'    <TextView android:id="@+id/{id_}"\n        android:layout_width="wrap_content"\n        android:layout_height="wrap_content"\n'
            f'        android:textSize="{size}sp"\n        android:textColor="{color}"{st}{g}{extra} />\n')

def rows():
    out = ""
    for i in range(6):
        out += f'''        <LinearLayout android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1" android:orientation="horizontal" android:gravity="center_vertical">
            <TextView android:id="@+id/wd_t{i}" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:gravity="start" android:textSize="14sp" android:textStyle="bold" android:textColor="#FFFFFF" android:text="--:--" />
            <TextView android:id="@+id/wd_n{i}" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:gravity="end" android:textSize="14sp" android:textStyle="bold" android:textColor="#FFFFFF" android:text="--" />
        </LinearLayout>
'''
    return out

def bg_img(i="wd_bg", d="wd_round18"):
    return (f'    <ImageView android:id="@+id/{i}" android:layout_width="match_parent" android:layout_height="match_parent" '
            f'android:scaleType="fitXY" android:src="@drawable/{d}" />\n')

LAYOUT_BIG = f'''<?xml version="1.0" encoding="utf-8"?>
<FrameLayout {NS}
    android:id="@+id/wd_root"
    android:layout_width="match_parent"
    android:layout_height="match_parent">
{bg_img()}    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:orientation="horizontal"
        android:layoutDirection="ltr"
        android:baselineAligned="false"
        android:padding="10dp">
        <LinearLayout android:layout_width="0dp" android:layout_height="match_parent" android:layout_weight="1" android:orientation="vertical" android:paddingStart="6dp" android:paddingEnd="12dp">
{rows()}        </LinearLayout>
        <FrameLayout android:layout_width="0dp" android:layout_height="match_parent" android:layout_weight="1">
{bg_img("wd_pbg", "wd_round14")}            <LinearLayout android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical" android:gravity="center" android:padding="8dp">
                <TextView android:id="@+id/wd_label" android:layout_width="wrap_content" android:layout_height="wrap_content" android:textSize="16sp" android:textStyle="bold" android:textColor="#FFFFFF" android:gravity="center" android:text="--" />
                <Chronometer android:id="@+id/wd_cd" android:layout_width="wrap_content" android:layout_height="wrap_content" android:textSize="32sp" android:textStyle="bold" android:textColor="#FFFFFF" />
                <TextView android:id="@+id/wd_cd_txt" android:layout_width="wrap_content" android:layout_height="wrap_content" android:textSize="32sp" android:textStyle="bold" android:textColor="#FFFFFF" android:visibility="gone" />
            </LinearLayout>
        </FrameLayout>
    </LinearLayout>
</FrameLayout>
'''

LAYOUT_SMALL = f'''<?xml version="1.0" encoding="utf-8"?>
<FrameLayout {NS}
    android:id="@+id/wd_root"
    android:layout_width="match_parent"
    android:layout_height="match_parent">
{bg_img()}    <LinearLayout android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical" android:gravity="center" android:padding="10dp">
        <TextView android:id="@+id/wd_label" android:layout_width="wrap_content" android:layout_height="wrap_content" android:textSize="14sp" android:textStyle="bold" android:textColor="#FFFFFF" android:gravity="center" android:text="--" />
        <Chronometer android:id="@+id/wd_cd" android:layout_width="wrap_content" android:layout_height="wrap_content" android:textSize="28sp" android:textStyle="bold" android:textColor="#FFFFFF" />
        <TextView android:id="@+id/wd_cd_txt" android:layout_width="wrap_content" android:layout_height="wrap_content" android:textSize="28sp" android:textStyle="bold" android:textColor="#FFFFFF" android:visibility="gone" />
    </LinearLayout>
</FrameLayout>
'''

LAYOUT_HABITS = f'''<?xml version="1.0" encoding="utf-8"?>
<FrameLayout {NS}
    android:id="@+id/wd_root"
    android:layout_width="match_parent"
    android:layout_height="match_parent">
{bg_img()}    <LinearLayout android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical" android:gravity="center" android:padding="14dp">
        <TextView android:id="@+id/wd_title" android:layout_width="wrap_content" android:layout_height="wrap_content" android:textSize="13sp" android:textStyle="bold" android:textColor="#FFFFFF" android:text="--" />
        <TextView android:id="@+id/wd_count" android:layout_width="wrap_content" android:layout_height="wrap_content" android:textSize="30sp" android:textStyle="bold" android:textColor="#FFFFFF" android:text="--" />
        <TextView android:id="@+id/wd_bar" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginTop="4dp" android:textSize="14sp" android:textDirection="ltr" android:textColor="#FFFFFF" android:text="" />
        <TextView android:id="@+id/wd_sub" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginTop="6dp" android:textSize="12sp" android:textColor="#FFFFFF" android:gravity="center" android:text="--" />
    </LinearLayout>
</FrameLayout>
'''

LAYOUT_HIJRI = f'''<?xml version="1.0" encoding="utf-8"?>
<FrameLayout {NS}
    android:id="@+id/wd_root"
    android:layout_width="match_parent"
    android:layout_height="match_parent">
{bg_img()}    <LinearLayout android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical" android:gravity="center" android:padding="12dp">
        <TextView android:id="@+id/wd_hijri" android:layout_width="wrap_content" android:layout_height="wrap_content" android:textSize="17sp" android:textStyle="bold" android:textColor="#FFFFFF" android:gravity="center" android:text="--" />
        <TextView android:id="@+id/wd_next" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginTop="4dp" android:textSize="14sp" android:textColor="#FFFFFF" android:gravity="center" android:text="--" />
    </LinearLayout>
</FrameLayout>
'''

def shape(color, radius=18, gradient=None):
    if gradient:
        body = f'<gradient android:angle="315" android:startColor="{gradient[0]}" android:endColor="{gradient[1]}" />'
    else:
        body = f'<solid android:color="{color}" />'
    return f'''<?xml version="1.0" encoding="utf-8"?>
<shape {NS} android:shape="rectangle">
    {body}
    <corners android:radius="{radius}dp" />
</shape>
'''

def info(minw, minh, layout, desc, period="1800000"):
    return f'''<?xml version="1.0" encoding="utf-8"?>
<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android"
    android:minWidth="{minw}dp"
    android:minHeight="{minh}dp"
    android:updatePeriodMillis="{period}"
    android:initialLayout="@layout/{layout}"
    android:resizeMode="horizontal|vertical"
    android:widgetCategory="home_screen"
    android:description="@string/{desc}" />
'''

STRINGS = '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="wd_big">جدولي · المواقيت والعداد</string>
    <string name="wd_big_desc">مواقيت الصلاة الخمس مع عداد تنازلي للصلاة الجاية</string>
    <string name="wd_small">جدولي · عداد الصلاة</string>
    <string name="wd_small_desc">عداد تنازلي صغير للصلاة الجاية</string>
    <string name="wd_habits">جدولي · عادات النهاردة</string>
    <string name="wd_habits_desc">كام عادة خلّصت النهاردة</string>
    <string name="wd_hijri">جدولي · التاريخ الهجري</string>
    <string name="wd_hijri_desc">التاريخ الهجري مع الصلاة الجاية</string>
</resources>
'''

def receiver(name, label, info_name):
    return f'''
        <receiver android:name=".{name}" android:exported="true" android:label="@string/{label}">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
            </intent-filter>
            <meta-data android:name="android.appwidget.provider" android:resource="@xml/{info_name}" />
        </receiver>'''

def apply(app, pkg, man):
    jd = f"{app}/java/{pkg.replace('.', '/')}"
    rs = f"{app}/res"
    def java(name, src):
        w(f"{jd}/{name}.java", esc(src.replace("__PKG__", pkg)))
    java("WidgetUtil", UTIL)
    java("WidgetBridgePlugin", PLUGIN)
    java("WidgetRefreshReceiver", RECEIVER)
    for n in ("PrayerBigWidget", "PrayerSmallWidget", "HabitsWidget", "HijriWidget"):
        java(n, PROVIDER.replace("__NAME__", n))
    w(f"{rs}/layout/widget_big.xml", LAYOUT_BIG)
    w(f"{rs}/layout/widget_small.xml", LAYOUT_SMALL)
    w(f"{rs}/layout/widget_habits.xml", LAYOUT_HABITS)
    w(f"{rs}/layout/widget_hijri.xml", LAYOUT_HIJRI)
    w(f"{rs}/drawable/wd_round18.xml", shape("#FFFFFF", 18))
    w(f"{rs}/drawable/wd_round14.xml", shape("#FFFFFF", 14))
    w(f"{rs}/xml/widget_big_info.xml", info(250, 140, "widget_big", "wd_big_desc"))
    w(f"{rs}/xml/widget_small_info.xml", info(110, 70, "widget_small", "wd_small_desc"))
    w(f"{rs}/xml/widget_habits_info.xml", info(110, 110, "widget_habits", "wd_habits_desc"))
    w(f"{rs}/xml/widget_hijri_info.xml", info(250, 70, "widget_hijri", "wd_hijri_desc"))
    w(f"{rs}/values/widget_strings.xml", STRINGS)

    comps = (receiver("PrayerBigWidget", "wd_big", "widget_big_info")
             + receiver("PrayerSmallWidget", "wd_small", "widget_small_info")
             + receiver("HabitsWidget", "wd_habits", "widget_habits_info")
             + receiver("HijriWidget", "wd_hijri", "widget_hijri_info")
             + '''
        <receiver android:name=".WidgetRefreshReceiver" android:exported="false">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
                <action android:name="android.intent.action.TIME_SET" />
                <action android:name="android.intent.action.TIMEZONE_CHANGED" />
                <action android:name="android.intent.action.DATE_CHANGED" />
            </intent-filter>
        </receiver>''')
    if ".PrayerBigWidget" not in man:
        man = man.replace("</application>", comps + "\n    </application>", 1)
    if "RECEIVE_BOOT_COMPLETED" not in man:
        man = man.replace("</manifest>",
            '    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />\n</manifest>', 1)
    print("widgets patched OK")
    return man
