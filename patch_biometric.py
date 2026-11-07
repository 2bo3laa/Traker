#!/usr/bin/env python3
"""Fingerprint / face / device-lock unlock for جدولي (androidx.biometric BiometricPrompt).
Called from patch-android.py. apply(app, pkg, manifest_text) writes the plugin and returns the manifest."""
import os, re
from patch_widgets import esc, w

PLUGIN = r'''package __PKG__;

import android.app.KeyguardManager;
import android.content.Context;
import android.os.Build;
import androidx.biometric.BiometricManager;
import androidx.biometric.BiometricPrompt;
import androidx.core.content.ContextCompat;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.util.concurrent.Executor;

@CapacitorPlugin(name = "Biometric")
public class BiometricPlugin extends Plugin {
    private static final int BIO = BiometricManager.Authenticators.BIOMETRIC_WEAK;

    @PluginMethod
    public void isAvailable(PluginCall call) {
        JSObject r = new JSObject();
        try {
            BiometricManager bm = BiometricManager.from(getContext());
            boolean bio = bm.canAuthenticate(BIO) == BiometricManager.BIOMETRIC_SUCCESS;
            boolean dev;
            if (Build.VERSION.SDK_INT >= 30) {
                dev = bm.canAuthenticate(BIO | BiometricManager.Authenticators.DEVICE_CREDENTIAL) == BiometricManager.BIOMETRIC_SUCCESS;
            } else {
                KeyguardManager km = (KeyguardManager) getContext().getSystemService(Context.KEYGUARD_SERVICE);
                dev = bio || (km != null && km.isDeviceSecure());
            }
            r.put("bio", bio);
            r.put("dev", dev);
        } catch (Exception e) {
            r.put("bio", false);
            r.put("dev", false);
        }
        call.resolve(r);
    }

    @PluginMethod
    public void verify(final PluginCall call) {
        final boolean device = Boolean.TRUE.equals(call.getBoolean("device", false));
        final String title = call.getString("title", "");
        final String sub = call.getString("subtitle", "");
        final String neg = call.getString("cancel", "Cancel");
        getActivity().runOnUiThread(new Runnable() {
            @Override public void run() {
                try {
                    Executor ex = ContextCompat.getMainExecutor(getContext());
                    BiometricPrompt.PromptInfo.Builder b = new BiometricPrompt.PromptInfo.Builder().setTitle(title);
                    if (sub != null && sub.length() > 0) b.setSubtitle(sub);
                    if (device && Build.VERSION.SDK_INT >= 30) {
                        b.setAllowedAuthenticators(BIO | BiometricManager.Authenticators.DEVICE_CREDENTIAL);
                    } else if (device) {
                        b.setDeviceCredentialAllowed(true);
                    } else {
                        b.setAllowedAuthenticators(BIO);
                        b.setNegativeButtonText(neg);
                    }
                    BiometricPrompt bp = new BiometricPrompt(getActivity(), ex, new BiometricPrompt.AuthenticationCallback() {
                        @Override public void onAuthenticationSucceeded(BiometricPrompt.AuthenticationResult result) {
                            JSObject r = new JSObject(); r.put("ok", true); call.resolve(r);
                        }
                        @Override public void onAuthenticationError(int code, CharSequence msg) {
                            JSObject r = new JSObject(); r.put("ok", false); r.put("code", code); r.put("msg", String.valueOf(msg)); call.resolve(r);
                        }
                    });
                    bp.authenticate(b.build());
                } catch (Exception e) {
                    JSObject r = new JSObject(); r.put("ok", false); r.put("msg", String.valueOf(e.getMessage())); call.resolve(r);
                }
            }
        });
    }
}
'''

def apply(app, pkg, man):
    jd = f"{app}/java/{pkg.replace('.', '/')}"
    w(f"{jd}/BiometricPlugin.java", esc(PLUGIN.replace("__PKG__", pkg)))
    if "USE_BIOMETRIC" not in man:
        man = man.replace("</manifest>", '    <uses-permission android:name="android.permission.USE_BIOMETRIC" />\n</manifest>', 1)
    # androidx.biometric dependency
    gp = "android/app/build.gradle"
    if os.path.exists(gp):
        g = open(gp, encoding="utf-8").read()
        if "androidx.biometric" not in g:
            g = re.sub(r"dependencies\s*\{", 'dependencies {\n    implementation "androidx.biometric:biometric:1.1.0"', g, count=1)
            open(gp, "w", encoding="utf-8").write(g)
    print("biometric OK")
    return man
