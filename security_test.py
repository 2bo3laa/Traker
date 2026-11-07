#!/usr/bin/env python3
"""Security tests: HTML/script injection through every text field and through a malicious backup file,
and a check that the app never talks to a server except Google Fonts. Run: python security_test.py"""
import asyncio, pathlib, sys, json
from playwright.async_api import async_playwright

URL = (pathlib.Path(__file__).resolve().parent / "index.html").as_uri()
PAYLOAD = '"><img src=x onerror="window.__xss=(window.__xss||0)+1"><script>window.__xss=(window.__xss||0)+1</script>\'-alert(1)-\''
failures = []

def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    if not cond:
        failures.append(name)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 800}, locale="ar-EG")
        pg = await ctx.new_page()
        errs, reqs = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("request", lambda r: reqs.append(r.url))
        pg.on("dialog", lambda d: asyncio.ensure_future(d.dismiss()))
        ev = pg.evaluate
        await pg.goto(URL); await pg.wait_for_timeout(600)

        print("\n== injection through the UI")
        await pg.fill("#obn", PAYLOAD); await pg.click('[data-ob="next"]'); await pg.click('[data-ob="done"]')
        await pg.click("#fab"); await pg.click('[data-qk="habit"]'); await pg.click('[data-c="read"]'); await pg.fill("#nm", PAYLOAD); await pg.click("[data-add]")
        await pg.click("#fab"); await pg.click('[data-qk="habit"]'); await pg.click('[data-c="task"]'); await pg.fill("#tkt", PAYLOAD); await pg.click('[data-tk="add"]')
        await pg.click('#bar [data-pg="paper"]')
        for i in ("wpg_body", "wpg_study", "wpg_work"):
            await pg.fill(f"#{i}", PAYLOAD)
        await pg.fill("#wpd", PAYLOAD); await pg.fill("#wpnew", PAYLOAD); await pg.click('[data-wp="add"]')
        await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="money"]')
        await pg.click('[data-mn="new:ex"]'); await pg.fill("#mna", "10"); await pg.fill("#mnn", PAYLOAD); await pg.click('[data-mn="add:ex"]')
        await pg.click('[data-mn="new:sub"]'); await pg.fill("#mnn", PAYLOAD); await pg.fill("#mna", "5"); await pg.fill("#mnd", "3"); await pg.click('[data-mn="add:sub"]')
        await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="quit"]')
        await pg.click('[data-qt="add"]'); await pg.click('[data-qt="t:6"]'); await pg.fill("#qtn", PAYLOAD); await pg.click('[data-qt="save"]')
        await pg.click('[data-qt^="rel:"]'); await pg.fill("#qtnote", PAYLOAD); await pg.click('[data-qt="relsave"]')
        await pg.click('[data-qt^="plan:"]'); await pg.fill("#qtplan", PAYLOAD); await pg.click('[data-qt="plansave"]')
        await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="meds"]')
        await pg.click('[data-md="new"]'); await pg.fill("#mdn", PAYLOAD); await pg.fill("#mdd", PAYLOAD); await pg.fill("#mdnote", PAYLOAD); await pg.click('[data-md="save"]')
        await pg.click('#bar [data-pg="more"]'); await pg.click('#main [data-pg="assist"]')
        await pg.fill("#asin", PAYLOAD); await pg.click('[data-as="send"]')
        for tab in ("today", "table", "paper", "gym", "more"):
            await pg.click(f'#bar [data-pg="{tab}"]')
        for sub in ("stats", "tasks", "money", "quit", "meds", "assist", "food"):
            await pg.click('#bar [data-pg="more"]'); await pg.click(f'#main [data-pg="{sub}"]')
        await pg.click("#thm"); await pg.wait_for_timeout(200); await ev("closeW()")
        check("no injected script ran (UI inputs)", not await ev("window.__xss"), str(await ev("window.__xss")))
        check("no injected element in the page", await ev("document.querySelectorAll('img[src=\"x\"]').length") == 0)
        check("no page errors (UI inputs)", not errs, "; ".join(errs[:2]))

        print("\n== malicious backup file")
        evil = {"habits": [{"id": PAYLOAD, "name": PAYLOAD, "sub": PAYLOAD, "days": [0, 1, 2, 3, 4, 5, 6], "start": "2020-01-01"}],
                "done": {}, "name": PAYLOAD,
                "tk": [{"id": PAYLOAD, "t": PAYLOAD, "due": "2020-01-01", "pr": 1, "done": 0}],
                "qt": [{"id": PAYLOAD, "n": PAYLOAD, "e": PAYLOAD, "since": 0, "rel": [{"at": 1, "len": 1, "tag": PAYLOAD, "note": PAYLOAD}], "plan": PAYLOAD}],
                "mn": {"ex": [{"id": PAYLOAD, "a": 1, "c": PAYLOAD, "n": PAYLOAD, "d": "2026-11-01", "t": 1}], "sub": [{"id": PAYLOAD, "n": PAYLOAD, "a": 1, "day": 3}], "bud": 5},
                "md": {"meds": [{"id": PAYLOAD, "n": PAYLOAD, "dose": PAYLOAD, "ins": PAYLOAD, "note": PAYLOAD, "times": ["08:00"], "days": [], "start": "2020-01-01", "end": ""}], "log": {}},
                "wp": {"goals": {"body": PAYLOAD}, "dump": PAYLOAD, "weeks": {"2026-10-31": [{"t": PAYLOAD, "d": 0}]}}}
        await ev("(t)=>{try{restoreFrom(t)}catch(e){}}", json.dumps(evil))
        await ev("localStorage.setItem('hb1',JSON.stringify(Object.assign(JSON.parse(localStorage.getItem('hb1')||'{}'),%s)))" % json.dumps(evil))
        await pg.reload(); await pg.wait_for_timeout(600)
        for tab in ("today", "table", "paper", "gym", "more"):
            await pg.click(f'#bar [data-pg="{tab}"]')
        for sub in ("stats", "tasks", "money", "quit", "meds", "assist"):
            await pg.click('#bar [data-pg="more"]'); await pg.click(f'#main [data-pg="{sub}"]')
        await pg.click('#bar [data-pg="today"]')
        await pg.click("#edit"); await pg.click("#emedit")
        check("no injected script ran (malicious backup)", not await ev("window.__xss"), str(await ev("window.__xss")))
        check("no injected element (malicious backup)", await ev("document.querySelectorAll('img[src=\"x\"]').length") == 0)

        print("\n== network")
        bad = [u for u in reqs if not (u.startswith("file:") or u.startswith("data:") or "fonts.googleapis.com" in u or "fonts.gstatic.com" in u)]
        check("only Google Fonts is contacted", not bad, ", ".join(bad[:3]))
        await b.close()
    if failures:
        print(f"\n{len(failures)} security check(s) FAILED"); sys.exit(1)
    print("\nall security checks passed")

asyncio.run(main())
