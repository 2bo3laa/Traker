#!/usr/bin/env python3
"""Work-log punch notification for جدولي (like the Work Log app).
A persistent notification shows a punch-in button, and after punching in it shows a live timer and a punch-out button.
Taps work even when the app is closed: events are stored natively and the web app pulls them when it opens."""
import os
from patch_widgets import esc, w

NOTIFIER = r'''package __PKG__;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;

final class WorkLogNotifier {
    static final String PREFS = "worklog";
    static final String CH = "worklog";
    static final String ACT_IN = "__PKG__.WL_IN";
    static final String ACT_OUT = "__PKG__.WL_OUT";
    static final int NID = 7732;

    static SharedPreferences sp(Context c) { return c.getSharedPreferences(PREFS, 0); }

    static void refresh(Context c) {
        SharedPreferences p = sp(c);
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        if (!p.getBoolean("enabled", false)) { nm.cancel(NID); return; }
        boolean open = p.getBoolean("open", false);
        long since = p.getLong("since", 0);
        String title = p.getString("title", "Work");
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(CH, "Work Log", NotificationManager.IMPORTANCE_LOW);
            ch.setShowBadge(false);
            nm.createNotificationChannel(ch);
        }
        Intent a = new Intent(c, WorkLogReceiver.class);
        a.setAction(open ? ACT_OUT : ACT_IN);
        PendingIntent actionPi = PendingIntent.getBroadcast(c, open ? 2 : 1, a, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        PendingIntent openPi = null;
        Intent li = c.getPackageManager().getLaunchIntentForPackage(c.getPackageName());
        if (li != null) openPi = PendingIntent.getActivity(c, 3, li, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(c, CH) : new Notification.Builder(c);
        b.setSmallIcon(android.R.drawable.ic_menu_recent_history)
         .setContentTitle(open ? title + " \u2022 " + p.getString("running", "") : title)
         .setContentText(open ? p.getString("runningHint", "") : p.getString("idle", ""))
         .setOngoing(true)
         .setOnlyAlertOnce(true)
         .setCategory(Notification.CATEGORY_STATUS)
         .addAction(open ? android.R.drawable.ic_media_pause : android.R.drawable.ic_media_play,
                    open ? p.getString("outLbl", "Out") : p.getString("inLbl", "In"), actionPi);
        if (open && since > 0) b.setUsesChronometer(true).setWhen(since).setShowWhen(true);
        if (openPi != null) b.setContentIntent(openPi);
        nm.notify(NID, b.build());
    }
}
'''

RECEIVER = r'''package __PKG__;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONObject;

public class WorkLogReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent i) {
        SharedPreferences p = WorkLogNotifier.sp(c);
        String a = i.getAction();
        boolean open = p.getBoolean("open", false);
        long now = System.currentTimeMillis();
        String type = null;
        if (WorkLogNotifier.ACT_IN.equals(a) && !open) type = "in";
        else if (WorkLogNotifier.ACT_OUT.equals(a) && open) type = "out";
        if (type == null) { WorkLogNotifier.refresh(c); return; }
        try {
            JSONArray ev = new JSONArray(p.getString("events", "[]"));
            ev.put(new JSONObject().put("t", type).put("at", now));
            p.edit().putString("events", ev.toString())
                .putBoolean("open", "in".equals(type))
                .putLong("since", "in".equals(type) ? now : 0).apply();
        } catch (Exception ignored) {}
        WorkLogNotifier.refresh(c);
    }
}
'''

BOOT = r'''package __PKG__;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class WorkLogBootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent i) {
        try { WorkLogNotifier.refresh(c); } catch (Exception ignored) {}
    }
}
'''

PLUGIN = r'''package __PKG__;

import android.content.SharedPreferences;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import org.json.JSONArray;

@CapacitorPlugin(name = "WorkLog")
public class WorkLogPlugin extends Plugin {
    @PluginMethod
    public void sync(PluginCall call) {
        try {
            SharedPreferences p = WorkLogNotifier.sp(getContext());
            JSObject d = call.getData();
            boolean pending = new JSONArray(p.getString("events", "[]")).length() > 0;
            SharedPreferences.Editor e = p.edit();
            e.putBoolean("enabled", d.optBoolean("enabled", false));
            e.putString("title", d.optString("title", "Work"));
            e.putString("idle", d.optString("idle", ""));
            e.putString("running", d.optString("running", ""));
            e.putString("runningHint", d.optString("runningHint", ""));
            e.putString("inLbl", d.optString("inLbl", "In"));
            e.putString("outLbl", d.optString("outLbl", "Out"));
            if (!pending) {   // never overwrite a punch made from the notification that the app has not read yet
                e.putBoolean("open", d.optBoolean("open", false));
                e.putLong("since", d.optLong("since", 0));
            }
            e.apply();
            WorkLogNotifier.refresh(getContext());
            call.resolve();
        } catch (Exception ex) {
            call.reject(String.valueOf(ex.getMessage()));
        }
    }

    @PluginMethod
    public void pull(PluginCall call) {
        try {
            SharedPreferences p = WorkLogNotifier.sp(getContext());
            String ev = p.getString("events", "[]");
            p.edit().putString("events", "[]").apply();
            JSObject r = new JSObject();
            r.put("events", new com.getcapacitor.JSArray(ev));
            call.resolve(r);
        } catch (Exception ex) {
            call.reject(String.valueOf(ex.getMessage()));
        }
    }
}
'''

COMPONENTS = '''
        <receiver android:name=".WorkLogReceiver" android:exported="false" />
        <receiver android:name=".WorkLogBootReceiver" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
                <action android:name="android.intent.action.MY_PACKAGE_REPLACED" />
            </intent-filter>
        </receiver>'''

def apply(app, pkg, man):
    jd = f"{app}/java/{pkg.replace('.', '/')}"
    for name, src in (("WorkLogNotifier", NOTIFIER), ("WorkLogReceiver", RECEIVER),
                      ("WorkLogBootReceiver", BOOT), ("WorkLogPlugin", PLUGIN)):
        w(f"{jd}/{name}.java", esc(src.replace("__PKG__", pkg)))
    if ".WorkLogReceiver" not in man:
        man = man.replace("</application>", COMPONENTS + "\n    </application>", 1)
    print("work-log notification OK")
    return man
