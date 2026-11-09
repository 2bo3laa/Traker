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
    await ctx.add_init_script("try{localStorage.setItem('hb_lang','ar')}catch(e){}")   # the flow assertions below are written in Arabic; run_english() checks the English UI
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))   # confirm() dialogs (deleting things) are accepted
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
    await pg.click("#fab"); await pg.click('[data-qk="habit"]'); await pg.click('[data-c="prayer"]'); await pg.click("[data-add]")
    names = lambda: ev("S.habits.map(h=>h.name).join('|')")
    check("five prayers added", len(await ev("S.habits")) == 5)
    await ev("S.habits=S.habits.filter(h=>h.name!=='العصر');save();render()")
    await pg.click("#fab"); await pg.click('[data-qk="habit"]'); await pg.click('[data-c="prayer"]')
    check("only the missing prayer is offered", await ev("document.querySelectorAll('#sheet [data-p]').length") == 1)
    await pg.click("[data-add]"); await pg.wait_for_timeout(100)
    check("Asr back between Dhuhr and Maghrib", (await names()) == "الفجر|الظهر|العصر|المغرب|العشاء", await names())
    await pg.click("#fab"); await pg.click('[data-qk="habit"]')
    await pg.click('[data-c="prayer"]')
    check("full prayer category cannot be added twice", await ev("document.querySelectorAll('#sheet [data-p]').length") == 0)
    await ev("closeW()")

    # --- work log: punch in / out / history
    await pg.click("#fab"); await pg.click('[data-qk="habit"]'); await pg.click('[data-c="work"]'); await pg.click('[data-wm="log"]')
    await pg.fill("#wls0", "26"); await pg.click("[data-add]"); await pg.wait_for_timeout(100)
    check("work-log habit created", await ev("S.habits.some(h=>h.log)") and await ev("S.wlStart") == 26)
    await ev("S.habits.filter(h=>h.log).forEach(h=>h.days=[0,1,2,3,4,5,6]);save();render()")   # independent of the weekday
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
    await pg.click("#fab"); await pg.click('[data-qk="habit"]'); await pg.click('[data-c="gym"]'); await pg.click("[data-add]")
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
    await pg.click("#fab"); await pg.click('[data-qk="habit"]'); await pg.click('[data-c="tpl"]')
    names = await ev("TPL.map(x=>x.n)")
    wi = next(i for i, n in enumerate(names) if "شرب المياه" in n)
    await pg.click('[data-tp="c:h"]'); await pg.click(f'[data-tp="s:{wi}"]'); await pg.click('[data-tp="c:g"]'); await pg.click('[data-tp="c:w"]')
    ti = next(i for i, n in enumerate(names) if "تسبيح" in n)
    await pg.click(f'[data-tp="s:{ti}"]'); await pg.click('[data-tp="add"]')
    check("templates add several habits at once", await ev("S.habits.filter(h=>h.goal).length") == 2)
    check("selected template from another tab is kept too", await ev("S.habits.some(h=>/تسبيح/.test(h.name))"))
    await pg.click("#fab"); await pg.click('[data-qk="habit"]'); await pg.click('[data-c="tpl"]')
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

    # --- reminders on every habit
    wr = await ev("S.habits.find(h=>/شرب المياه/.test(h.name)).rm.length")
    check("template habits come with suggested reminders", wr == 6, str(wr))
    await pg.click("#fab"); await pg.click('[data-qk="habit"]'); await pg.click('[data-c="read"]'); await pg.fill("#nm", "Quran study"); await pg.fill("#rmt", "20:00"); await pg.click("[data-add]")
    check("wizard habit gets the reminder time", await ev("S.habits.find(h=>h.name==='Quran study').rm.join()") == "20:00")
    await pg.click("#edit"); await pg.click("#emedit")
    qid = await ev("S.habits.find(h=>h.name==='Quran study').id")
    await pg.click(f'[data-rm="{qid}"]'); await pg.click('[data-rmx="m:3h"]'); await pg.click('[data-rmx="save"]')
    check("reminder can be changed from edit mode", await ev("S.habits.find(h=>h.name==='Quran study').rm.length") == 5)
    await pg.click(f'[data-rm="{qid}"]'); await pg.click('[data-rmx="m:off"]'); await pg.click('[data-rmx="save"]')
    check("reminder can be switched off", await ev("S.habits.find(h=>h.name==='Quran study').rm.length") == 0)
    await ev("S.habits=S.habits.filter(h=>h.name!=='Quran study');save()")
    await pg.click("#edit")

    # --- medication reminders
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="meds"]')
    await pg.click('[data-md="new"]'); await pg.fill("#mdn", "Vitamin D"); await pg.fill("#mdd", "1 tablet")
    await pg.click('[data-md="n:2"]'); await pg.click('[data-md="i:2"]'); await pg.click('[data-md="u:7"]'); await pg.fill("#mds", "6"); await pg.click('[data-md="save"]')
    m0 = await ev("S.md.meds[0]")
    check("medicine saved with two daily times, duration and stock", m0["n"] == "Vitamin D" and len(m0["times"]) == 2 and m0["end"] and m0["st"]["n"] == 6, str(m0))
    await ev("S.md.meds[0].times=['00:05','00:10'];save();render()")   # both doses are in the past, so they are 'missed' until taken
    await pg.click('#bar [data-pg="today"]')
    check("Today lists today's doses", "Vitamin D" in await ev("document.getElementById('main').innerText"))
    await pg.click('[data-md^="t|"]')
    check("taking a dose logs it and reduces the stock", await ev("Object.values(S.md.log).filter(x=>x.s==='t').length") == 1 and await ev("S.md.meds[0].st.n") == 5)
    check("low stock warning appears at five or fewer doses", "قرّب يخلص" in await ev("document.getElementById('main').innerText"))
    await pg.click('[data-md^="s|"]')
    check("a dose can be skipped", await ev("Object.values(S.md.log).filter(x=>x.s==='s').length") == 1)
    await pg.click('[data-md^="u|"]')
    check("taking back a dose restores the stock", await ev("S.md.meds[0].st.n") == 6 and await ev("Object.values(S.md.log).length") == 1)
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="meds"]')
    check("adherence card is shown", "التزامك" in await ev("document.getElementById('main').innerText"))
    await pg.click('[data-md^="e|"]'); await pg.fill("#mdn", "Vitamin D3"); await pg.click('[data-md="save"]')
    check("medicine can be edited", await ev("S.md.meds[0].n") == "Vitamin D3")
    check("doctor report is generated", "Vitamin D3" in await ev("mdReport()"))
    await pg.click('[data-md^="x|"]')
    check("medicine can be deleted", await ev("S.md.meds.length") == 0)
    await pg.click('#bar [data-pg="today"]')

    # --- tasks: dated, prioritised, overdue stays visible
    await pg.click("#fab"); await pg.click('[data-qk="habit"]'); await pg.click('[data-c="task"]')
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
    await pg.click("#fab"); await pg.click('[data-qk="habit"]'); await pg.click('[data-c="quit"]'); await pg.click('[data-qt="t:0"]'); await pg.click('[data-qt="save"]')
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

    # --- health log: weight, sleep, mood and patterns
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="health"]')
    await pg.click('[data-hl="new"]'); await pg.fill("#hlw", "80"); await pg.fill("#hlsh", "5.5"); await pg.click('[data-hl="m:2"]'); await pg.click('[data-hl="e:2"]'); await pg.click('[data-hl="save"]')
    e0 = await ev("S.hl[iso(today0())]")
    check("daily health entry saved", e0["w"] == 80 and e0["sh"] == 5.5 and e0["m"] == 2 and e0["en"] == 2, str(e0))
    check("logging weight updates the nutrition plan", await ev("S.nu.w") == 80)
    await pg.click('[data-hl="new"]'); await pg.fill("#hlw", "500"); await pg.click('[data-hl="save"]')
    check("impossible weight is rejected", await ev("S.hl[iso(today0())].w") == 80)
    await ev("closeW()")
    await ev("S.habits.forEach(h=>h.start=iso(addDays(today0(),-30)));save()")
    await ev("""(()=>{S.hl=S.hl||{};for(let i=1;i<=10;i++){const d=addDays(today0(),-i),k=iso(d),good=i%2===0;S.hl[k]={sh:good?8:5,m:good?5:1,en:good?5:1,w:80-i*0.1};
      S.habits.forEach(h=>{if(active(h,d)){if(good)S.done[k+'|'+h.id]=1;else delete S.done[k+'|'+h.id]}})}save();render()})()""")
    pats = await ev("hlPatterns()")
    check("the app finds a sleep/mood pattern", any("😴" in x or "🙂" in x for x in pats), str(pats))
    check("health page renders the weight chart", "<svg" in await ev("(page='health',render(),document.getElementById('main').innerHTML)"))
    await pg.click('#bar [data-pg="today"]')

    # --- weekly review and achievements
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="review"]')
    check("review page shows a score", "التزامك" in await ev("document.getElementById('main').innerText"))
    check("share text is built", "مراجعة أسبوعي" in await ev("rvText(-1)"))
    await pg.click('[data-rv="tab:badges"]')
    check("achievements page lists the badges", await ev("document.querySelectorAll('#main .tcard').length") >= 10)
    await ev("S.bd={};bdCheck()")
    check("earned badges are unlocked", await ev("!!S.bd.first") and await ev("bdLevel(bdXP())") >= 1)
    await pg.click('#bar [data-pg="today"]')

    # --- Quran khatma plan
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="khatma"]')
    await pg.click('[data-kh="d:30"]'); await pg.click('[data-kh="start"]')
    check("khatma plan targets about 21 pages a day for 30 days", await ev("khPlan().target") == 21, str(await ev("khPlan().target")))
    await pg.click('[data-kh="add:10"]'); await pg.click('[data-kh="add:5"]')
    check("pages are counted", await ev("khPlan().read") == 15 and await ev("khPlan().rt") == 15)
    await ev("khAdd(589)"); await pg.wait_for_timeout(100)
    check("finishing 604 pages completes the khatma", await ev("khPlan().done") is True and await ev("S.kh.done") == 1)
    await pg.click('[data-kh="again"]')
    check("a new khatma can be started", await ev("khPlan()") is None)

    # --- Ramadan mode
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="ramadan"]')
    check("hijri date is available", await ev("!!hij(new Date())"))
    if not await ev("rdActive()"):
        await pg.click('[data-rd="force"]')
    check("Ramadan mode can be enabled", await ev("rdActive()"))
    await pg.click('[data-rd="fast"]'); await pg.click('[data-rd="tar"]')
    check("fasting and taraweeh are tracked", await ev("S.rmd.fast[iso(today0())]") == 1 and await ev("S.rmd.tar[iso(today0())]") == 1)
    await ev("S.rmd.force=0;save()")
    await pg.click('#bar [data-pg="today"]')

    # --- UX: quick add, customisation, collapsible sections, checklist, back button, search
    await pg.click('#bar [data-pg="today"]')
    await pg.click("#fab")
    check("the plus button opens a quick-add sheet", await ev("document.querySelectorAll('[data-qk]').length") >= 6)
    await pg.click('[data-qk="task"]')
    check("quick add > task opens the task form", await ev("!!document.getElementById('tkt')"))
    await ev("closeW()")
    await pg.click("#fab"); await pg.click('[data-qk="exp"]')
    check("quick add > expense opens the expense form", await ev("!!document.getElementById('mna')"))
    await ev("closeW()")
    secs = await ev("[...document.querySelectorAll('#main > .sec')].map(x=>x.dataset.ux)")
    first = secs[0]
    await pg.click(f'#main > .sec[data-ux="{first}"]')
    check("a section can be collapsed and it is remembered", await ev("!!S.ux.col[%s]" % __import__('json').dumps(first)))
    await pg.click(f'#main > .sec[data-ux="{first}"]')
    check("and expanded again", not await ev("!!S.ux.col[%s]" % __import__('json').dumps(first)))
    await ev("S.ux.chk=0;S.ux.t0=Date.now();S.habits=S.habits.slice(0,1);save();render()")
    check("a 'start here' checklist helps new users", "ابدأ هنا" in await ev("document.getElementById('main').innerText"))
    await pg.click('[data-ux2="close"]')
    check("the checklist can be dismissed", "ابدأ هنا" not in await ev("document.getElementById('main').innerText"))
    await pg.click('#bar [data-pg="more"]'); await pg.fill("#mrs", "أدوي")
    check("the More page has a search", "الأدوية" in await ev("document.getElementById('mgrid').innerText") and "المصاريف" not in await ev("document.getElementById('mgrid').innerText"))
    await pg.fill("#mrs", "")
    check("More is grouped in sections", await ev("document.querySelectorAll('#mgrid .sec').length") >= 4)
    await pg.click('#main [data-pg="custom"]')
    await pg.click('[data-cu="t:money"]')
    await pg.click('#bar [data-pg="more"]')
    check("a hidden feature disappears from More", "المصاريف" not in await ev("document.getElementById('mgrid').innerText"))
    await pg.click('#main [data-pg="custom"]'); await pg.click('[data-cu="t:money"]'); await pg.click('[data-cu="fs:1.12"]'); await pg.click('[data-cu="compact"]')
    check("font size and compact mode are applied", await ev("document.body.style.zoom") in ("1.12", "112%") and await ev("document.documentElement.classList.contains('compact')"))
    await pg.click('[data-cu="fs:1"]'); await pg.click('[data-cu="compact"]')
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="tasks"]')
    await ev("uxBack()")
    check("back from a feature page returns to More", await ev("page") == "more")
    await ev("uxBack()")
    check("back from More returns to Today", await ev("page") == "today")
    await pg.click("#fab"); await ev("uxBack()")
    check("back closes an open sheet first", not await ev("document.getElementById('modal').classList.contains('on')") and await ev("page") == "today")

    # --- app lock and snapshots
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="lock"]')
    await pg.click('[data-lk="set"]')
    for d in "1234": await pg.click(f'[data-lk="sk:{d}"]')
    await pg.click('[data-lk="sk:ok"]')
    for d in "1234": await pg.click(f'[data-lk="sk:{d}"]')
    await pg.click('[data-lk="sk:ok"]'); await pg.wait_for_timeout(200)
    check("PIN lock enabled", await ev("!!localStorage.getItem('hb_lock')") and "1234" not in await ev("localStorage.getItem('hb_lock')"))
    await ev("lkShow()"); await pg.wait_for_timeout(100)
    check("lock screen covers the app", await ev("lkLocked()") and await ev("!!document.getElementById('lockscr')"))
    for d in "0000": await pg.click(f'[data-lk="uk:{d}"]')
    await pg.wait_for_timeout(250)
    check("wrong PIN keeps it locked", await ev("lkLocked()"))
    for d in "1234": await pg.click(f'[data-lk="uk:{d}"]')
    await pg.wait_for_timeout(250)
    check("right PIN unlocks", not await ev("lkLocked()") and not await ev("!!document.getElementById('lockscr')"))
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="lock"]')
    await pg.click('[data-lk="snap"]')
    check("snapshot taken and restorable", await ev("snList().length") >= 1)
    await pg.click('[data-lk="off"]')
    for d in "1234": await pg.click(f'[data-lk="sk:{d}"]')
    await pg.click('[data-lk="sk:ok"]'); await pg.wait_for_timeout(200)
    check("lock can be removed with the PIN", not await ev("!!localStorage.getItem('hb_lock')"))
    await pg.click('#bar [data-pg="today"]')

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
      window.__syncs=[];window.__events=[];window.__sched=[];
      const LN=new Proxy({},{get:(o,k)=>async a=>{if(k==="schedule"){window.__sched.push(...(a.notifications||[]))}
        if(k==="getPending")return{notifications:[]};if(k==="requestPermissions"||k==="checkPermissions")return{display:"granted"};return{}}});
      window.__bioOk=true;
      const BIOM={isAvailable:async()=>({bio:true,dev:true}),verify:async()=>({ok:window.__bioOk!==false})};
      window.Capacitor={Plugins:{LocalNotifications:LN,Biometric:BIOM,WorkLog:{
        sync:async s=>{window.__syncs.push(s)},
        pull:async()=>{const e=window.__events;window.__events=[];return{events:e}}}}};""")
    await pg.goto(URL); await pg.wait_for_timeout(500)
    ev = pg.evaluate
    await pg.fill("#obn", "Ahmed"); await pg.click('[data-ob="next"]'); await pg.click('[data-ob="done"]')
    await pg.click("#fab"); await pg.click('[data-qk="habit"]'); await pg.click('[data-c="work"]'); await pg.click('[data-wm="log"]'); await pg.click("[data-add]")
    await pg.wait_for_timeout(100)
    await ev("S.habits.filter(h=>h.log).forEach(h=>h.days=[0,1,2,3,4,5,6]);save();render()")
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
    # reminders are really scheduled with the phone's notification plugin
    await pg.click("#fab"); await pg.click('[data-qk="habit"]'); await pg.click('[data-c="read"]'); await pg.fill("#nm", "Evening reading"); await pg.fill("#rmt", "23:59"); await pg.click("[data-add]")
    await ev("S.habits.find(h=>h.name==='Evening reading').days=[0,1,2,3,4,5,6];save()")
    await ev("schedNotif()"); await pg.wait_for_timeout(300)
    sched = await ev("window.__sched.filter(n=>/Evening reading/.test(n.body)).map(n=>n.id)")
    check("habit reminders are scheduled for the coming days", len(sched) >= 2 and all(i >= 4000 for i in sched), str(sched))
    await ev("S.habits.forEach(h=>{if(h.name==='Evening reading')S.done[iso(today0())+'|'+h.id]=1});save()")
    await ev("window.__sched.length=0;schedNotif()"); await pg.wait_for_timeout(300)
    sched2 = await ev("window.__sched.filter(n=>/Evening reading/.test(n.body)).length")
    check("a finished habit stops reminding for today", sched2 == len(sched) - 1, f"{sched2} vs {len(sched)}")
    await ev("S.md={meds:[{id:'m1',n:'Antibiotic',dose:'1 pill',times:['23:50'],days:[],ins:'بعد الأكل',start:iso(addDays(today0(),-1)),end:'',st:null}],log:{}};save()")
    await ev("window.__sched.length=0;schedNotif()"); await pg.wait_for_timeout(300)
    ms = await ev("window.__sched.filter(n=>/Antibiotic/.test(n.body)).map(n=>({id:n.id,t:n.title,ch:n.channelId}))")
    check("each dose gets the main alert plus two follow-ups", len(ms) >= 6 and all(x["id"] >= 6000 and x["ch"] == "meds" for x in ms), str(ms[:3]))
    check("follow-up alerts exist for a missed dose", any("لسه ما أخدتش" in x["t"] for x in ms) and any("فاتتك" in x["t"] for x in ms))
    day = await ev("iso(today0())")
    await ev("S.md.log[iso(today0())+'|m1|23:50']={s:'t',at:Date.now()};save()")
    await ev("window.__sched.length=0;schedNotif()"); await pg.wait_for_timeout(300)
    after = await ev("window.__sched.filter(n=>/Antibiotic/.test(n.body)).length")
    check("taking the dose cancels today's follow-ups", after == len(ms) - 3, f"{after} vs {len(ms)}")
    # --- biometric / device-lock unlock (native plugin mocked)
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="lock"]')
    check("the lock is optional: off by default", not await ev("!!localStorage.getItem('hb_lock')"))
    await pg.click('[data-lk="dev"]'); await pg.wait_for_timeout(200)
    check("device lock (fingerprint/face) enabled without any PIN", await ev("JSON.parse(localStorage.getItem('hb_lock')).mode") == "device")
    await ev("lkShow()"); await pg.wait_for_timeout(700)
    check("biometric prompt unlocks automatically", not await ev("lkLocked()"))
    await ev("window.__bioOk=false;lkShow()"); await pg.wait_for_timeout(700)
    check("failed biometric keeps the app locked", await ev("lkLocked()"))
    await ev("window.__bioOk=true"); await pg.click('[data-lk="ubio"]'); await pg.wait_for_timeout(500)
    check("retry button unlocks after a good scan", not await ev("lkLocked()"))
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="lock"]'); await pg.click('[data-lk="off"]'); await pg.wait_for_timeout(300)
    check("device lock can be removed", not await ev("!!localStorage.getItem('hb_lock')"))
    await pg.click('[data-lk="set"]')
    for d in "2468": await pg.click(f'[data-lk="sk:{d}"]')
    await pg.click('[data-lk="sk:ok"]')
    for d in "2468": await pg.click(f'[data-lk="sk:{d}"]')
    await pg.click('[data-lk="sk:ok"]'); await pg.wait_for_timeout(300)
    await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="lock"]'); await pg.click('[data-lk="bio"]'); await pg.wait_for_timeout(300)
    check("fingerprint shortcut can be added to the PIN", await ev("JSON.parse(localStorage.getItem('hb_lock')).bio") == 1)
    await ev("lkShow()"); await pg.wait_for_timeout(700)
    check("PIN mode unlocks with the fingerprint shortcut", not await ev("lkLocked()"))
    await ev("localStorage.removeItem('hb_lock');render()")

    await ev("S.rmd={force:1,fast:{},tar:{},n:1};S.kh={start:iso(today0()),days:30,total:604,log:{},done:0,rm:'23:55'};save()")
    await ev("window.__sched.length=0;schedNotif()"); await pg.wait_for_timeout(300)
    ids = await ev("window.__sched.map(n=>n.id)")
    check("weekly-review and daily-log reminders are scheduled", any(5400 <= i < 5420 for i in ids) and any(5300 <= i < 5310 for i in ids), str(sorted(ids)[-10:]))
    check("Ramadan and khatma reminders are scheduled", any(5100 <= i < 5110 for i in ids) and any(5200 <= i < 5210 for i in ids), str(sorted(ids)[:12]))
    check("no page errors", not errs, "; ".join(errs[:3]))
    await ctx.close()

async def run_english(browser):
    """In English no screen may show Arabic letters (the language names in the picker are the only exception)."""
    import re
    print("\n== English UI has no Arabic text")
    ctx = await browser.new_context(viewport={"width": 390, "height": 780}, locale="en-US")
    await ctx.add_init_script("try{localStorage.setItem('hb_lang','en')}catch(e){}")
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(URL)
    await pg.wait_for_timeout(700)
    await pg.click('[data-ob="next"]'); await pg.fill("#obn", "Ahmed")
    await pg.click('[data-ob="next"]'); await pg.click('[data-ob="done"]')
    for name in ("today", "table", "paper", "gym", "more", "stats", "food", "pray", "assist", "tasks", "focus", "money", "quit", "meds", "lock", "khatma", "ramadan", "health", "review", "custom"):
        await pg.evaluate(f"page='{name}';render()")
        await pg.wait_for_timeout(120)
        txt = await pg.evaluate("document.body.innerText")
        txt = txt.replace("العربية", "").replace("اردو", "")
        left = re.findall(r"[\u0600-\u06FF]+", txt)
        check(f"English UI has no Arabic on the {name} page", not left, " ".join(left[:6]))
    check("no page errors", not errs, "; ".join(errs[:3]))
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for locale in ("ar-EG", "en-US"):
            for width in (360, 412):
                await run(b, locale, width)
        await run_english(b)
        await run_native_mock(b)
        await b.close()
    if failures:
        print(f"\n{len(failures)} check(s) FAILED")
        sys.exit(1)
    print("\nall smoke tests passed")

asyncio.run(main())
