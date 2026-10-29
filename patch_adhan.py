#!/usr/bin/env python3
"""Native adhan player for جدولي. Called from patch-android.py (CI).
An exact alarm starts a foreground service that plays the adhan (res/raw) until it ends,
or until the user taps "إيقاف" in the notification or presses a volume button.
apply(app, pkg, manifest_text) writes the java files and returns the new manifest."""
import os
from patch_widgets import esc, w

LOOP = "false"   # "true" = repeat the adhan until the user stops it

SCHEDULER = r'''package __PKG__;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import org.json.JSONArray;
import org.json.JSONObject;

final class AdhanScheduler {
    static final String PREFS = "adhan_alarms";
    static final String KEY = "items";
    static final String FIRE = "__PKG__.ADHAN_FIRE";
    static final String STOP = "__PKG__.ADHAN_STOP";

    static PendingIntent fireIntent(Context c, JSONObject o) throws Exception {
        int id = o.getInt("id");
        Intent i = new Intent(c, AdhanReceiver.class);
        i.setAction(FIRE);
        i.setData(Uri.parse("adhan://alarm/" + id));
        i.putExtra("fajr", o.optBoolean("fajr", false));
        i.putExtra("title", o.optString("title", ""));
        i.putExtra("body", o.optString("body", ""));
        return PendingIntent.getBroadcast(c, id, i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    static JSONArray stored(Context c) {
        try { return new JSONArray(c.getSharedPreferences(PREFS, 0).getString(KEY, "[]")); }
        catch (Exception e) { return new JSONArray(); }
    }

    static void cancelStored(Context c) {
        AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
        JSONArray a = stored(c);
        for (int k = 0; k < a.length(); k++) {
            try { am.cancel(fireIntent(c, a.getJSONObject(k))); } catch (Exception ignored) {}
        }
    }

    static void setAll(Context c, JSONArray items) {
        AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
        long now = System.currentTimeMillis();
        PendingIntent show = null;
        Intent li = c.getPackageManager().getLaunchIntentForPackage(c.getPackageName());
        if (li != null) show = PendingIntent.getActivity(c, 0, li, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        for (int k = 0; k < items.length(); k++) {
            try {
                JSONObject o = items.getJSONObject(k);
                long at = o.getLong("at");
                if (at <= now) continue;
                PendingIntent pi = fireIntent(c, o);
                try {
                    if (show != null) am.setAlarmClock(new AlarmManager.AlarmClockInfo(at, show), pi);
                    else am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi);
                } catch (SecurityException se) {
                    am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi);
                }
            } catch (Exception ignored) {}
        }
    }

    static void replaceAll(Context c, JSONArray items) {
        cancelStored(c);
        c.getSharedPreferences(PREFS, 0).edit().putString(KEY, items.toString()).apply();
        setAll(c, items);
    }
}
'''

PLUGIN = r'''package __PKG__;

import android.content.Intent;
import androidx.core.content.ContextCompat;
import com.getcapacitor.JSArray;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import org.json.JSONArray;

@CapacitorPlugin(name = "Adhan")
public class AdhanPlugin extends Plugin {
    @PluginMethod
    public void schedule(PluginCall call) {
        try {
            JSArray items = call.getArray("items");
            AdhanScheduler.replaceAll(getContext(), items == null ? new JSONArray() : new JSONArray(items.toString()));
            call.resolve();
        } catch (Exception e) {
            call.reject(String.valueOf(e.getMessage()));
        }
    }

    @PluginMethod
    public void cancelAll(PluginCall call) {
        AdhanScheduler.replaceAll(getContext(), new JSONArray());
        call.resolve();
    }

    @PluginMethod
    public void test(PluginCall call) {
        try {
            Intent s = new Intent(getContext(), AdhanService.class);
            s.putExtra("fajr", Boolean.TRUE.equals(call.getBoolean("fajr", false)));
            s.putExtra("title", call.getString("title", ""));
            s.putExtra("body", call.getString("body", ""));
            ContextCompat.startForegroundService(getContext(), s);
            call.resolve();
        } catch (Exception e) {
            call.reject(String.valueOf(e.getMessage()));
        }
    }

    @PluginMethod
    public void stop(PluginCall call) {
        getContext().stopService(new Intent(getContext(), AdhanService.class));
        call.resolve();
    }
}
'''

RECEIVER = r'''package __PKG__;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import androidx.core.content.ContextCompat;

public class AdhanReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent i) {
        String a = i.getAction();
        if (AdhanScheduler.STOP.equals(a)) {
            c.stopService(new Intent(c, AdhanService.class));
        } else if (AdhanScheduler.FIRE.equals(a)) {
            Intent s = new Intent(c, AdhanService.class);
            if (i.getExtras() != null) s.putExtras(i.getExtras());
            try { ContextCompat.startForegroundService(c, s); } catch (Exception ignored) {}
        }
    }
}
'''

BOOT = r'''package __PKG__;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class AdhanBootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent i) {
        try { AdhanScheduler.setAll(c, AdhanScheduler.stored(c)); } catch (Exception ignored) {}
    }
}
'''

SERVICE = r'''package __PKG__;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.ServiceInfo;
import android.content.res.AssetFileDescriptor;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.media.session.MediaSession;
import android.media.session.PlaybackState;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.os.SystemClock;
import androidx.core.content.ContextCompat;
import android.media.VolumeProvider;

public class AdhanService extends Service {
    static final String CH = "adhan_live";
    static final int NID = 7731;
    static final boolean LOOP = __LOOP__;

    private MediaPlayer mp;
    private MediaSession ms;
    private BroadcastReceiver volRx;
    private AudioFocusRequest focusReq;
    private long startedAt;

    @Override
    public IBinder onBind(Intent i) { return null; }

    @Override
    public int onStartCommand(Intent in, int flags, int startId) {
        release();
        boolean fajr = in != null && in.getBooleanExtra("fajr", false);
        String title = in != null ? in.getStringExtra("title") : null;
        String body = in != null ? in.getStringExtra("body") : null;
        if (title == null || title.length() == 0) title = "\u062d\u0627\u0646 \u0627\u0644\u0622\u0646 \u0645\u0648\u0639\u062f \u0627\u0644\u0635\u0644\u0627\u0629";
        if (body == null) body = "";
        try {
            Notification n = buildNotification(title, body);
            if (Build.VERSION.SDK_INT >= 29) startForeground(NID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK);
            else startForeground(NID, n);
        } catch (Exception e) {
            stopSelf();
            return START_NOT_STICKY;
        }
        if (!play(fajr)) { stopSelf(); return START_NOT_STICKY; }
        listenForVolumeKeys();
        return START_NOT_STICKY;
    }

    private Notification buildNotification(String title, String body) {
        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(CH, "Adhan playing", NotificationManager.IMPORTANCE_HIGH);
            ch.setSound(null, null);
            ch.enableVibration(false);
            nm.createNotificationChannel(ch);
        }
        Intent stop = new Intent(this, AdhanReceiver.class);
        stop.setAction(AdhanScheduler.STOP);
        PendingIntent stopPi = PendingIntent.getBroadcast(this, 1, stop, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        PendingIntent openPi = null;
        Intent li = getPackageManager().getLaunchIntentForPackage(getPackageName());
        if (li != null) openPi = PendingIntent.getActivity(this, 2, li, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(this, CH) : new Notification.Builder(this);
        b.setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
         .setContentTitle(title)
         .setContentText(body)
         .setOngoing(true)
         .setCategory(Notification.CATEGORY_ALARM)
         .addAction(android.R.drawable.ic_media_pause, "\u0625\u064a\u0642\u0627\u0641", stopPi);
        if (openPi != null) b.setContentIntent(openPi);
        if (Build.VERSION.SDK_INT >= 31) b.setForegroundServiceBehavior(Notification.FOREGROUND_SERVICE_IMMEDIATE);
        return b.build();
    }

    private boolean play(boolean fajr) {
        try {
            int res = getResources().getIdentifier(fajr ? "adhan_fajr" : "adhan", "raw", getPackageName());
            if (res == 0) return false;
            AudioAttributes aa = new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ALARM)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build();
            if (Build.VERSION.SDK_INT >= 26) {
                AudioManager am = (AudioManager) getSystemService(Context.AUDIO_SERVICE);
                focusReq = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE)
                    .setAudioAttributes(aa).build();
                am.requestAudioFocus(focusReq);
            }
            mp = new MediaPlayer();
            mp.setAudioAttributes(aa);
            mp.setWakeMode(this, PowerManager.PARTIAL_WAKE_LOCK);
            AssetFileDescriptor afd = getResources().openRawResourceFd(res);
            mp.setDataSource(afd.getFileDescriptor(), afd.getStartOffset(), afd.getLength());
            afd.close();
            mp.setLooping(LOOP);
            mp.setOnCompletionListener(m -> stopSelf());
            mp.setOnErrorListener((m, what, extra) -> { stopSelf(); return true; });
            mp.prepare();
            mp.start();
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    private void listenForVolumeKeys() {
        startedAt = SystemClock.elapsedRealtime();
        try {
            ms = new MediaSession(this, "adhan");
            ms.setPlaybackState(new PlaybackState.Builder()
                .setState(PlaybackState.STATE_PLAYING, 0, 1f).build());
            ms.setPlaybackToRemote(new VolumeProvider(VolumeProvider.VOLUME_CONTROL_RELATIVE, 100, 50) {
                @Override public void onAdjustVolume(int direction) { if (direction != 0) stopSelf(); }
                @Override public void onSetVolumeTo(int volume) { stopSelf(); }
            });
            ms.setActive(true);
        } catch (Exception ignored) {}
        try {
            volRx = new BroadcastReceiver() {
                @Override public void onReceive(Context c, Intent i) {
                    if (SystemClock.elapsedRealtime() - startedAt < 1500) return;
                    if (i.getIntExtra("android.media.EXTRA_VOLUME_STREAM_TYPE", -1) == AudioManager.STREAM_ALARM) stopSelf();
                }
            };
            ContextCompat.registerReceiver(this, volRx, new IntentFilter("android.media.VOLUME_CHANGED_ACTION"), ContextCompat.RECEIVER_EXPORTED);
        } catch (Exception e) { volRx = null; }
    }

    private void release() {
        try { if (mp != null) { mp.stop(); } } catch (Exception ignored) {}
        try { if (mp != null) { mp.release(); } } catch (Exception ignored) {}
        mp = null;
        try { if (ms != null) { ms.setActive(false); ms.release(); } } catch (Exception ignored) {}
        ms = null;
        try { if (volRx != null) unregisterReceiver(volRx); } catch (Exception ignored) {}
        volRx = null;
        try {
            if (focusReq != null && Build.VERSION.SDK_INT >= 26) {
                ((AudioManager) getSystemService(Context.AUDIO_SERVICE)).abandonAudioFocusRequest(focusReq);
            }
        } catch (Exception ignored) {}
        focusReq = null;
    }

    @Override
    public void onDestroy() {
        release();
        try { stopForeground(true); } catch (Exception ignored) {}
        super.onDestroy();
    }
}
'''

PERMS = [
    "android.permission.FOREGROUND_SERVICE",
    "android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK",
    "android.permission.WAKE_LOCK",
    "android.permission.RECEIVE_BOOT_COMPLETED",
]

COMPONENTS = '''
        <service android:name=".AdhanService" android:exported="false"
            android:foregroundServiceType="mediaPlayback" />
        <receiver android:name=".AdhanReceiver" android:exported="false" />
        <receiver android:name=".AdhanBootReceiver" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
                <action android:name="android.intent.action.MY_PACKAGE_REPLACED" />
            </intent-filter>
        </receiver>'''

def apply(app, pkg, man):
    jd = f"{app}/java/{pkg.replace('.', '/')}"
    for name, src in (("AdhanScheduler", SCHEDULER), ("AdhanPlugin", PLUGIN), ("AdhanReceiver", RECEIVER),
                      ("AdhanBootReceiver", BOOT), ("AdhanService", SERVICE)):
        w(f"{jd}/{name}.java", esc(src.replace("__PKG__", pkg).replace("__LOOP__", LOOP)))
    for p in PERMS:
        if p not in man:
            man = man.replace("</manifest>", f'    <uses-permission android:name="{p}" />\n</manifest>', 1)
    if ".AdhanService" not in man:
        man = man.replace("</application>", COMPONENTS + "\n    </application>", 1)
    return man
