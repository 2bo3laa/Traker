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

    # --- header menu, settings, other tabs
    await pg.click("#edit")
    await pg.click("#emedit")
    check("edit mode via the three-dots menu", await ev("editing") is True)
    await pg.click("#edit")
    for tab in ("table", "stats", "deen", "gym", "pray", "today"):
        await pg.click(f'#bar [data-pg="{tab}"]')
    await pg.click("#thm")
    check("settings sheet opens", await ev("document.getElementById('modal').classList.contains('on')"))
    await ev("closeW()")

    # --- data survives a reload
    await pg.reload(); await pg.wait_for_timeout(500)
    check("data persists after reload", await ev("S.habits.length") == 6 and await ev("S.name") == "Ahmed")
    check("no onboarding after reload", not await ev("document.getElementById('modal').classList.contains('on')"))

    check("no page errors", not errs, "; ".join(errs[:3]))
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for locale in ("ar-EG", "en-US"):
            for width in (360, 412):
                await run(b, locale, width)
        await b.close()
    if failures:
        print(f"\n{len(failures)} check(s) FAILED")
        sys.exit(1)
    print("\nall smoke tests passed")

asyncio.run(main())
