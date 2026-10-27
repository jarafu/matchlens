"""Standalone browser QA against an isolated temporary instance, never owner data."""
import os
import sys
import tempfile
import subprocess
import time
from pathlib import Path
from datetime import datetime,timedelta,timezone
import httpx
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from app.db import connect
from app.models import Fixture
from app.web.auth import hash_password


def main():
    with tempfile.TemporaryDirectory(prefix='matchlens-ui-') as tmp:
        db_url=f'sqlite:///{tmp}/qa.db';factory=connect(db_url)
        with factory() as db:
            db.add(Fixture(id='qa-fixture',competition='PL',home='Sample Home FC',away='Sample Away FC',kickoff=(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat(),fetched_at=datetime.now(timezone.utc).isoformat(),status='SCHEDULED',source='synthetic-browser-test'))
            db.commit()
        env={**os.environ,'DATABASE_URL':db_url,'OWNER_PASSWORD_HASH':hash_password('isolated-ui-test-password'),'FOOTBALL_DATA_TOKEN':'','ALLOWED_HOSTS':'127.0.0.1,localhost','SECURE_COOKIES':'false'}
        proc=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8001','--no-proxy-headers'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:
                    if httpx.get('http://127.0.0.1:8001/healthz',timeout=1).status_code==200: break
                except httpx.HTTPError: pass
                time.sleep(.2)
            else: raise RuntimeError('QA server did not start')
            screenshot_dir=ROOT/'test-results';screenshot_dir.mkdir(exist_ok=True)
            with sync_playwright() as p:
                executable=os.getenv('CHROMIUM_EXECUTABLE')
                browser=p.chromium.launch(headless=True,executable_path=executable,args=['--no-sandbox'])
                for width in [360,390,1280]:
                    page=browser.new_page(viewport={'width':width,'height':900})
                    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto('http://127.0.0.1:8001/login')
                    page.get_by_label('Owner password',exact=True).fill('isolated-ui-test-password')
                    page.get_by_role('button',name='Open your dashboard').click()
                    page.get_by_role('button',name='Sample Home FC',exact=False).wait_for()
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),f'Overflow at {width}'
                    page.screenshot(path=str(screenshot_dir/f'dashboard-{width}.png'),full_page=True)
                    page.get_by_role('button',name='Sample Home FC',exact=False).click()
                    page.get_by_role('button',name='Analyse this match').click()
                    page.get_by_text('Not enough evidence to publish an estimate.',exact=True).wait_for()
                    assert page.locator('.prob-number').count()==0
                    page.get_by_role('button',name='Analyse today').click()
                    page.get_by_role('heading',name='No qualifying candidates.').wait_for()
                    page.get_by_role('button',name='Data & coverage').click()
                    page.get_by_role('heading',name='Connect your fixture source').wait_for()
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                    assert not errors,errors
                    page.screenshot(path=str(screenshot_dir/f'coverage-{width}.png'),full_page=True)
                    page.close()
                browser.close()
            print('Browser journeys passed at 360px, 390px and 1280px; no JS errors or horizontal overflow.')
        finally:
            proc.terminate();proc.wait(timeout=15)


if __name__=='__main__': main()
