طريقة 1: من غير ما تنزّل أي برنامج (GitHub)
1) اعمل حساب على github.com واعمل Repository جديد.
2) ارفع كل محتويات المجلد ده (مهم: مجلد .github يترفع كمان).
3) افتح تاب Actions وشغّل Build APK (Run workflow)، واستنى 5-10 دقايق.
4) افتح آخر تشغيل ونزّل الملف من Artifacts: habit-tracker-apk (جواه app-debug.apk).
5) انقل الـAPK للموبايل وافتحه. هيطلب تفعيل "التثبيت من مصادر غير معروفة".

طريقة 2: على جهازك (Android Studio)
1) نزّل Node.js و Android Studio.
2) في مجلد المشروع: npm install ثم npx cap add android ثم npx capacitor-assets generate --android ثم npx cap sync android
3) npx cap open android ثم من Android Studio: Build > Build APK(s).

لتعديل التطبيق: عدّل www/index.html وأعد البناء.

اللوجو: ملفات مجلد assets (icon-only و icon-foreground و icon-background و splash). لتغيير اللوجو استبدل الصور بنفس الأسماء والمقاسات (1024 للأيقونة، 2732 للسبلاش).


اللغات والترجمة:
- التطبيق بيدعم 8 لغات: العربية، English، Français، Español، Türkçe، Deutsch، Bahasa Indonesia، اردو (من الإعدادات > اللغة). كل النصوص موجودة في أول index.html داخل كتلة LANGUAGES & TRANSLATIONS.
- لإضافة لغة: ضيفها في LANGS وضيف كتلة PACK.xx بنفس مفاتيح النص العربي. أي نص ناقص بيظهر بالإنجليزي.
- المصحف والأذكار بيفضلوا بالعربي (دي نصوص التلاوة نفسها).

التنبيهات (الأندرويد فقط): من الإعدادات > تنبيهات الصلاة وتنبيه التمرين. محتاج إذن الإشعارات والتنبيهات الدقيقة.

--- Adhan sound / backup ---
* Adhan alert sound: Settings > Prayer alerts lets the user pick "Normal notification sound" or "Muezzin's voice".
  For the muezzin voice, put a short adhan file named adhan.mp3 next to index.html in the repo root (it is copied
  into the APK automatically). Without it the phone falls back to its default sound.
* Backup: "Save a backup file" opens the Android share sheet (Drive / Files / WhatsApp). "Restore from a file" picks that .json back.
