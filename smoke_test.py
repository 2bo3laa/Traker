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
    await pg.click("#thm")
    check("settings sheet opens", await ev("document.getElementById('modal').classList.contains('on')"))
    await ev("closeW()")

    # --- data survives a reload
    await pg.reload(); await pg.wait_for_timeout(500)
    check("data persists after reload", await ev("S.habits.length") == 8 and await ev("S.name") == "Ahmed")
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
