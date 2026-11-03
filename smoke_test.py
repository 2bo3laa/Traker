#!/usr/bin/env python3
"""End-to-end smoke test in a real (headless) browser. Runs in Arabic and English, on two phone widths.
Fails on any page error or broken flow. Usage: python smoke_test.py"""
import asyncio, pathlib, sys
from playwright.async_api import async_playwright

URL = (pathlib.Path(__file__).resolve().parent / "index.html").as_uri()
failures = []

def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    if not cond:
        failures.append(name)

async def run(browser, locale, width):
    print(f"\n== locale={locale} width={width}")
    ctx = await browser.new_context(viewport={"width": width, "height": 780}, locale=locale)
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    ev = pg.evaluate
    await pg.goto(URL)
    await pg.wait_for_timeout(700)

    # --- onboarding: name is required
    check("onboarding opens on a fresh install", await ev("document.getElementById('modal').classList.contains('on')"))
    await pg.click('[data-ob="next"]')
    check("empty name does not pass", await ev("!!document.getElementById('obn')"))
    await pg.fill("#obn", "Ahmed")
    await pg.click('[data-ob="next"]')
    await pg.click('[data-ob="done"]')
    await pg.wait_for_timeout(200)
    check("name saved", await ev("S.name") == "Ahmed")
    check("onboarding closed", not await ev("document.getElementById('modal').classList.contains('on')"))

    # --- prayers: add five, remove Asr, only Asr offered, comes back in place
    await pg.click("#fab"); await pg.click('[data-c="prayer"]'); await pg.click("[data-add]")
    names = lambda: ev("S.habits.map(h=>h.name).join('|')")
    check("five prayers added", len(await ev("S.habits")) == 5)
    await ev("S.habits=S.habits.filter(h=>h.name!=='العصر');save();render()")
    await pg.click("#fab"); await pg.click('[data-c="prayer"]')
    check("only the missing prayer is offered", await ev("document.querySelectorAll('#sheet [data-p]').length") == 1)
    await pg.click("[data-add]"); await pg.wait_for_timeout(100)
    check("Asr back between Dhuhr and Maghrib", (await names()) == "الفجر|الظهر|العصر|المغرب|العشاء", await names())
    await pg.click("#fab")
    await pg.click('[data-c="prayer"]')
    check("full prayer category cannot be added twice", await ev("document.querySelectorAll('#sheet [data-p]').length") == 0)
    await ev("closeW()")

    # --- work log: punch in / out / history
    await pg.click("#fab"); await pg.click('[data-c="work"]'); await pg.click('[data-wm="log"]')
    await pg.fill("#wls0", "26"); await pg.click("[data-add]"); await pg.wait_for_timeout(100)
    check("work-log habit created", await ev("S.habits.some(h=>h.log)") and await ev("S.wlStart") == 26)
    await pg.click('[data-wl="in"]')
    check("punch in opens a session", await ev("!!wlFindOpen()"))
    await ev("S.wl[Object.keys(S.wl)[0]][0].i-=2*3600e3;save()")
    await pg.click('[data-wl="out"]')
    total = await ev("wlDayMs(iso(today0()))")
    check("two hours counted", abs(total - 2 * 3600e3) < 120e3, str(total))
    await pg.click('[data-wl="hist"]'); await pg.wait_for_timeout(100)
    check("history sheet shows the month total", "2:0" in await ev("document.getElementById('sheet').innerText"))
    await ev("closeW()")

    # --- weekly paper tab
    await pg.click('#bar [data-pg="paper"]')
    await pg.fill("#wpnew", "Run"); await pg.click('[data-wp="add"]'); await pg.click('[data-wp="t:0"]')
    check("weekly step added and ticked", await ev("Object.values(S.wp.weeks)[0][0].d") == 1)
    await pg.click('#bar [data-pg="today"]')

    # --- workout goal + linked paper steps + automatic ticking
    await pg.click("#fab"); await pg.click('[data-c="gym"]'); await pg.click("[data-add]")
    await ev("S.habits.filter(h=>/^جيم/.test(h.name)).forEach(h=>h.days=[0,1,2,3,4,5,6]);save();render()")   # keep the test independent of the weekday
    await pg.click('#bar [data-pg="paper"]')
    await pg.click('[data-wp="lk:gym"]'); await pg.fill("#wpnew", "Workout"); await pg.click('[data-wp="add"]')
    await pg.click('[data-wp="lk:pr"]'); await pg.select_option("#wpx", "0"); await pg.fill("#wpw", "50")
    await pg.fill("#wpnew", "Break bench"); await pg.click('[data-wp="add"]')
    check("two linked steps created", await ev("Object.values(S.wp.weeks)[0].filter(x=>x.lk).length") == 2)
    await pg.click('#bar [data-pg="gym"]')
    await pg.click('[data-x="goal:m"]'); await pg.click('[data-x="gdays:4"]')
    check("goal + 4 days selects Upper/Lower", await ev("gy().s") == "ul")
    await pg.click('[data-x="ex:0"]'); await pg.fill("#gw", "55"); await pg.fill("#gr", "8"); await pg.click('[data-x="ga"]')
    check("gym habit ticked by the workout", await ev("S.habits.filter(h=>/^جيم/.test(h.name)).every(h=>S.done[iso(today0())+'|'+h.id])"))
    check("linked paper steps ticked automatically", await ev("Object.values(S.wp.weeks)[0].filter(x=>x.lk&&x.d&&x.auto).length") == 2)
    await ev("closeW()")
    await pg.click('#bar [data-pg="today"]')

    # --- header menu, settings, other tabs
    await pg.click("#edit")
    await pg.click("#emedit")
    check("edit mode via the three-dots menu", await ev("editing") is True)
    await pg.click("#edit")
    for tab in ("table", "paper", "gym", "more", "today"):
        await pg.click(f'#bar [data-pg="{tab}"]')
    for sub in ("stats", "deen", "pray"):
        await pg.click('#bar [data-pg="more"]'); await pg.click(f'#main [data-pg="{sub}"]')
        check(f"more > {sub} opens and keeps 'More' highlighted", await ev("document.querySelector('#bar button.on').dataset.pg") == "more")
    await pg.click('#bar [data-pg="today"]')

    # --- nutrition planner
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="food"]')
    await pg.click('[data-nu="goal:lose"]'); await pg.click('[data-nu="bud:low"]'); await pg.click('[data-nu="fp:liver"]'); await pg.click('[data-nu="fp:liver"]')
    await pg.fill('[data-nu-in="age"]', "28"); await pg.fill('[data-nu-in="h"]', "175"); await pg.fill('[data-nu-in="w"]', "85"); await pg.fill('[data-nu-in="tw"]', "75")
    await pg.click('[data-nu="make"]')
    kcal = await ev("nuCalc(S.nu).t")
    check("calorie target is sensible for a 85kg man losing weight", 1800 <= kcal <= 2500, str(kcal))
    check("plan shows 3 meals each with alternatives", await ev("document.querySelectorAll('#main [data-nu^=\"eat:\"]').length") == 3
          and await ev("document.querySelectorAll('#main [data-nu^=\"alt:\"]').length") >= 6)
    check("liver disliked -> never offered", await ev("Object.values(nuPlan(S.nu,nuCalc(S.nu))).every(x=>x.opts.every(o=>!/كبدة/.test(o.name)))"))
    check("low budget keeps meals cheap", await ev("Object.values(nuPlan(S.nu,nuCalc(S.nu))).every(x=>x.opts[0].cost<=2)"))
    check("each meal lands near its calorie share", await ev("(()=>{const c=nuCalc(S.nu),p=nuPlan(S.nu,c);const t=Object.values(p).reduce((a,x)=>a+x.opts[0].kcal,0);return Math.abs(t-c.t)/c.t<0.12})()"))
    await pg.click('[data-nu="shuffle"]'); await pg.click('[data-nu="habit"]')
    for sl in ("b", "l", "d"):
        await pg.click(f'[data-nu="eat:{sl}"]')
    check("eating every meal ticks the food habit", await ev("S.habits.filter(h=>h.name==='الأكل الصحي 🥗').every(h=>S.done[iso(new Date())+'|'+h.id])") and await ev("S.habits.some(h=>h.name==='الأكل الصحي 🥗')"))
    await pg.click('[data-nu="edit"]'); await pg.click('[data-nu="health"]'); await pg.click('[data-nu="make"]')
    check("health condition blocks the plan", "دكتور" in await ev("document.getElementById('main').innerText"))
    await ev("S.nu.health=0;S.nu.age=15;save();renderFood()")
    check("minors are blocked", "18" in await ev("document.getElementById('main').innerText"))
    await ev("S.nu.age=28;save()")
    await pg.click('#bar [data-pg="today"]')

    # --- Today: worship first, then workout, then the rest; next prayer on top
    secs = await ev("[...document.querySelectorAll('#main .sec')].map(x=>x.textContent)")
    order = [i for i, k in enumerate(("العبادات", "التمرين", "باقي يومك")) if any(k in x for x in secs)]
    check("Today lists worship, workout, rest in that order", len(order) == 3 and
          [next(j for j, x in enumerate(secs) if k in x) for k in ("العبادات", "التمرين", "باقي يومك")] == sorted(
          [next(j for j, x in enumerate(secs) if k in x) for k in ("العبادات", "التمرين", "باقي يومك")]), str(secs))
    check("next prayer card is the first thing in the list", await ev("document.querySelector('#main .tcard')&&document.querySelector('#main .tcard').dataset.pg==='pray'"))

    # --- ready-made habits and counter habits
    await pg.click("#fab"); await pg.click('[data-c="tpl"]')
    names = await ev("TPL.map(x=>x.n)")
    wi = next(i for i, n in enumerate(names) if "شرب المياه" in n)
    await pg.click('[data-tp="c:h"]'); await pg.click(f'[data-tp="s:{wi}"]'); await pg.click('[data-tp="c:g"]'); await pg.click('[data-tp="c:w"]')
    ti = next(i for i, n in enumerate(names) if "تسبيح" in n)
    await pg.click(f'[data-tp="s:{ti}"]'); await pg.click('[data-tp="add"]')
    check("templates add several habits at once", await ev("S.habits.filter(h=>h.goal).length") == 2)
    check("selected template from another tab is kept too", await ev("S.habits.some(h=>/تسبيح/.test(h.name))"))
    await pg.click("#fab"); await pg.click('[data-c="tpl"]')
    check("already-added templates are disabled", await ev("document.querySelectorAll('#sheet [data-tp^=\"s:\"][disabled]').length") == 0 and await ev("[...document.querySelectorAll('#sheet .chip[disabled]')].length") >= 1)
    await ev("closeW()")
    cnt = await ev("S.habits.filter(h=>h.goal).length")
    check("both counter habits created", cnt == 2, str(cnt))
    wid = await ev("S.habits.find(h=>/شرب المياه/.test(h.name)).id")
    for _ in range(8):
        await pg.click(f'[data-cn^="+:{wid}"]')
    check("8 glasses completes the water habit", await ev(f"S.done[iso(today0())+'|{wid}']") == 1)
    await pg.click(f'[data-cn^="-:{wid}"]')
    check("removing a glass un-completes it", not await ev(f"S.done[iso(today0())+'|{wid}']"))

    # --- tasks: dated, prioritised, overdue stays visible
    await pg.click("#fab"); await pg.click('[data-c="task"]')
    await pg.fill("#tkt", "Pay the internet bill"); await pg.click('[data-tk="p:1"]'); await pg.click('[data-tk="add"]')
    check("task created for today", await ev("S.tk.length") == 1 and await ev("S.tk[0].due===tkNow()&&S.tk[0].pr===1"))
    await ev("S.tk.push({id:'old1',t:'Old task',due:iso(addDays(today0(),-3)),pr:2,done:0});save();render()")
    secs = await ev("[...document.querySelectorAll('#main .sec')].map(x=>x.textContent)")
    check("Today has a tasks section", any("مهامك" in x for x in secs), str(secs))
    check("overdue task is still shown and marked late", "متأخرة" in await ev("document.getElementById('main').innerText"))
    await pg.click('[data-tk="t:old1"]')
    check("ticking a task completes it", await ev("S.tk.find(x=>x.id==='old1').done>0"))
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="tasks"]')
    check("tasks page lists the open task", "Pay the internet bill" in await ev("document.getElementById('main').innerText"))
    await pg.click('[data-tk="new"]'); await pg.click('[data-tk="d:none"]'); await pg.fill("#tkt", "Someday task"); await pg.click('[data-tk="add"]')
    check("undated task goes to its own group", "من غير تاريخ" in await ev("document.getElementById('main').innerText"))
    await pg.click('[data-tk="x:old1"]')
    check("task can be deleted", await ev("!S.tk.some(x=>x.id==='old1')"))
    await pg.click('#bar [data-pg="today"]')

    # --- focus timer
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="focus"]')
    await pg.click('[data-fc="d:15"]'); await pg.click('[data-fc="start"]')
    check("focus session starts", await ev("S.fc.end>Date.now()") and await ev("S.fc.dur") == 15)
    await ev("S.fc.end=Date.now()-1000;save()"); await pg.wait_for_timeout(900)
    check("finished session is logged", await ev("(S.fl[iso(today0())]||{}).min") == 15)

    # --- money: expenses, budget, subscriptions
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="money"]')
    await pg.click('[data-mn="new:ex"]'); await pg.fill("#mna", "150"); await pg.click('[data-mn="c:مواصلات"]'); await pg.click('[data-mn="add:ex"]')
    await pg.click('[data-mn="new:bud"]'); await pg.fill("#mna", "1000"); await pg.click('[data-mn="add:bud"]')
    await pg.click('[data-mn="new:sub"]'); await pg.fill("#mnn", "Netflix"); await pg.fill("#mna", "200"); await pg.fill("#mnd", "10"); await pg.click('[data-mn="add:sub"]')
    check("expense, budget and subscription saved", await ev("S.mn.ex.length")==1 and await ev("S.mn.bud")==1000 and await ev("S.mn.sub.length")==1)
    check("money page shows the month total", "150" in await ev("document.getElementById('main').innerText") or "١٥٠" in await ev("document.getElementById('main').innerText"))
    await pg.click('[data-mn^="x:"]')
    check("expense can be removed", await ev("S.mn.ex.length")==0)
    await ev("S.mn.ex.push({id:'z',a:75,c:'أكل',n:'',d:iso(today0()),t:Date.now()});save()")
    await pg.click('#bar [data-pg="today"]')

    # --- comeback: quit-habit tracker, urge tool, relapse flow, never-miss-twice banner
    pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
    await pg.click("#fab"); await pg.click('[data-c="quit"]'); await pg.click('[data-qt="t:0"]'); await pg.click('[data-qt="save"]')
    check("quit habit created", await ev("S.qt.length") == 1)
    check("Today shows the comeback section", "رحلة الإقلاع" in await ev("document.getElementById('main').innerText"))
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="quit"]')
    await pg.click('[data-qt^="urge:"]'); await pg.click('[data-qt="start"]')
    check("urge timer runs for ten minutes", 590000 < await ev("W.ue-Date.now()") <= 600000)
    await pg.click('[data-qt="won"]')
    check("resisted urge is counted", await ev("S.qt[0].res") == 1)
    await ev("S.qt[0].since=Date.now()-5*864e5;save();render()")
    await pg.click('[data-qt^="rel:"]'); await pg.click('[data-qt="g:ملل"]'); await pg.click('[data-qt="relsave"]')
    q0 = await ev("S.qt[0]")
    check("relapse is logged and the streak restarts", len(q0["rel"]) == 1 and q0["rel"][0]["tag"] == "ملل" and (Date.now() if False else True))
    check("longest streak is kept after a relapse", await ev("S.qt[0].best") >= 4.9 * 864e5)
    check("streak restarted from zero days", await ev("qtDays(S.qt[0])") == 0)
    await ev("S.qt[0].since=Date.now()-2*864e5;save()")
    await pg.click('[data-qt^="rel:"]'); await pg.click('[data-qt="g:ملل"]'); await pg.click('[data-qt="relsave"]')
    check("after two relapses the app shows a pattern insight", "انتكاساتك" in await ev("document.getElementById('main').innerText"))
    await ev("""(()=>{const t=today0(),h={id:'rb1',start:iso(addDays(t,-10)),name:'Test habit',sub:'',days:[0,1,2,3,4,5,6]};S.habits.push(h);
      for(let i=2;i<=5;i++)S.done[iso(addDays(t,-i))+'|rb1']=1;delete S.qbd;save()})()""")
    await pg.click('#bar [data-pg="today"]')
    check("never-miss-twice banner appears after a broken streak", "امبارح فاتتك" in await ev("document.getElementById('main').innerText"))
    await pg.click('[data-qt="bn"]')
    check("banner can be dismissed for the day", "امبارح فاتتك" not in await ev("document.getElementById('main').innerText"))
    await ev("S.habits=S.habits.filter(h=>h.id!=='rb1');save();render()")

    # --- offline assistant
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="assist"]')
    await pg.click('[data-as="q:0"]')
    check("the advice chip works", "مش فاهم" not in await ev("document.getElementById('aschat').innerText"))
    await pg.click('[data-as="q:1"]')
    await pg.fill("#asin", "ساعات شغلي الشهر ده"); await pg.click('[data-as="send"]')
    txt = await ev("document.getElementById('aschat').innerText")
    check("assistant answers about prayers", "صلّيت" in txt, txt[:120])
    check("assistant answers about work hours", "ساعة" in txt, txt[:200])
    await pg.fill("#asin", "عندي كام مهمة؟"); await pg.click('[data-as="send"]')
    check("assistant answers about tasks", "مهمة مفتوحة" in await ev("document.getElementById('aschat').innerText"))
    await pg.fill("#asin", "صرفت كام الشهر ده؟"); await pg.click('[data-as="send"]')
    check("assistant answers about spending", "صرفت" in await ev("document.getElementById('aschat').innerText"))
    await pg.fill("#asin", "انتكست"); await pg.click('[data-as="send"]')
    check("assistant answers supportively about relapse", "الانتكاسة" in await ev("document.getElementById('aschat').innerText"))
    await pg.fill("#asin", "ايه ده؟؟ xyz"); await pg.click('[data-as="send"]')
    check("assistant admits when it does not understand", "مش فاهم" in await ev("document.getElementById('aschat').innerText"))
    await pg.click('#bar [data-pg="today"]')

    # --- adhan sound settings
    await ev("S.pn={on:true,at:1,pre:1,post:1,p:{},s:{}};save()")
    await pg.click("#thm")
    await pg.click('[data-pn="m:الفجر:bell"]')
    check("bell mode keeps the prayer on but not the adhan", await ev("S.pn.s['الفجر']===0&&S.pn.p['الفجر']!==0"))
    await pg.click('[data-pn="m:الفجر:off"]')
    check("off mode silences the prayer", await ev("S.pn.p['الفجر']===0"))
    await pg.click('[data-pn="m:الفجر:adhan"]')
    check("adhan mode turns it back on", await ev("S.pn.p['الفجر']===1&&S.pn.s['الفجر']===1"))
    await pg.click('[data-pn="loop"]')
    check("repeat-until-stopped option saved", await ev("S.pn.loop===1"))
    await pg.click('[data-pn="keys"]')
    check("volume-button stop can be switched off", await ev("S.pn.keys===0"))
    await ev("closeW()")
    await pg.click("#thm")
    check("settings sheet opens", await ev("document.getElementById('modal').classList.contains('on')"))
    await ev("closeW()")

    # --- data survives a reload
    await pg.reload(); await pg.wait_for_timeout(500)
    check("data persists after reload", await ev("S.habits.length") == 10 and await ev("S.name") == "Ahmed")
    check("no onboarding after reload", not await ev("document.getElementById('modal').classList.contains('on')"))

    check("no page errors", not errs, "; ".join(errs[:3]))
    await ctx.close()

async def run_native_mock(browser):
    """Fake the native WorkLog plugin: a punch-in and punch-out made from the notification must land in the history."""
    print("\n== native work-log bridge (mocked)")
    ctx = await browser.new_context(viewport={"width": 390, "height": 780}, locale="ar-EG")
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.add_init_script("""
      window.__syncs=[];window.__events=[];
      window.Capacitor={Plugins:{WorkLog:{
        sync:async s=>{window.__syncs.push(s)},
        pull:async()=>{const e=window.__events;window.__events=[];return{events:e}}}}};""")
    await pg.goto(URL); await pg.wait_for_timeout(500)
    ev = pg.evaluate
    await pg.fill("#obn", "Ahmed"); await pg.click('[data-ob="next"]'); await pg.click('[data-ob="done"]')
    await pg.click("#fab"); await pg.click('[data-c="work"]'); await pg.click('[data-wm="log"]'); await pg.click("[data-add]")
    await pg.wait_for_timeout(100)
    last = await ev("window.__syncs[window.__syncs.length-1]")
    check("notification enabled once a work-log habit exists", bool(last) and last.get("enabled") is True and last.get("open") is False)
    await pg.click('[data-wl="in"]'); await pg.wait_for_timeout(100)
    last = await ev("window.__syncs[window.__syncs.length-1]")
    check("punch in in the app updates the notification", last.get("open") is True and last.get("since", 0) > 0)
    await pg.click('[data-wl="out"]')
    now = await ev("Date.now()")
    await ev(f"window.__events=[{{t:'in',at:{now-3*3600000}}},{{t:'out',at:{now-1*3600000}}}]")
    await ev("wlPull()"); await pg.wait_for_timeout(200)
    total = await ev("Object.keys(S.wl).reduce((a,k)=>a+wlDayMs(k),0)")
    check("punches made from the notification are merged (2h)", total >= 2 * 3600e3 - 60e3, str(total))
    check("no page errors", not errs, "; ".join(errs[:3]))
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for locale in ("ar-EG", "en-US"):
            for width in (360, 412):
                await run(b, locale, width)
        await run_native_mock(b)
        await b.close()
    if failures:
        print(f"\n{len(failures)} check(s) FAILED")
        sys.exit(1)
    print("\nall smoke tests passed")

asyncio.run(main())
