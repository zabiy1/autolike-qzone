# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ================= 配置区域 =================
CHECK_INTERVAL = 5  
CONFIG_FILE = "config.json"
LOG_FILE = "app.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

class QZoneRobot:
    def __init__(self, qq):
        self.my_qq = str(qq)
        self.session = requests.Session()
        self.config = {}

    def login_via_playwright(self):
        logging.info(f"==> 正在启动内置浏览器，请登录 QQ: {self.my_qq}")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            page.goto("https://qzone.qq.com/")
            
            try:
                page.wait_for_selector("iframe[name='login_frame']", timeout=10000)
                frame = page.frame(name="login_frame")
                if frame:
                    frame.click(f"#img_out_{self.my_qq}", timeout=5000)
            except:
                pass

            while True:
                if "user.qzone.qq.com" in page.url and "passport" not in page.url:
                    break
                time.sleep(1)
            
            time.sleep(5) 
            cookies = context.cookies()
            ua = page.evaluate("navigator.userAgent")
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            
            p_skey = next((c['value'] for c in cookies if c['name'] == 'p_skey'), "")
            h = 5381
            if p_skey:
                for c in p_skey:
                    h += (h << 5) + ord(c)
                g_tk = h & 2147483647
            else:
                g_tk = ""

            data = {
                "qq": self.my_qq,
                "cookie_str": cookie_str,
                "user_agent": ua,
                "g_tk": g_tk,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            browser.close()
            return True

    def check_cookie_valid(self):
        if not os.path.exists(CONFIG_FILE): return False
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            headers = {'User-Agent': self.config.get('user_agent', ''), 'Cookie': self.config.get('cookie_str', '')}
            res = requests.get(f"https://user.qzone.qq.com/{self.my_qq}/infocenter", headers=headers, allow_redirects=False, timeout=10)
            return res.status_code == 200
        except: return False

    def do_like(self, unikey, curkey, appid, typeid, abstime):
        url = 'https://user.qzone.qq.com/proxy/domain/w.qzone.qq.com/cgi-bin/likes/internal_dolike_app'
        g_tk = self.config.get('g_tk')
        headers = {
            'User-Agent': self.config.get('user_agent'),
            'Cookie': self.config.get('cookie_str'),
            'Referer': f'https://user.qzone.qq.com/{self.my_qq}/infocenter',
            'Origin': 'https://user.qzone.qq.com'
        }
        payload = {
            'qzreferrer': f'https://user.qzone.qq.com/{self.my_qq}/infocenter',
            'opuin': self.my_qq, 'unikey': unikey, 'curkey': curkey,
            'from': '1', 'appid': appid, 'typeid': typeid, 'abstime': abstime,
            'fid': unikey.split('/')[-1], 'active': '0', 'fupdate': '1', 'g_tk': g_tk
        }
        try:
            res = self.session.post(url + f'?g_tk={g_tk}', data=payload, headers=headers, timeout=10)
            return res.status_code == 200
        except: return False

    def run(self):
        print("\n" + "="*40 + "\n       空间妹点赞助手（riya自用版）\n" + "="*40 + "\n")
        while True:
            if not self.check_cookie_valid():
                if not self.login_via_playwright():
                    time.sleep(10); continue
            try:
                logging.info(f"[心跳] 正在巡检 {self.my_qq} 的好友动态...")
                headers = {'User-Agent': self.config.get('user_agent'), 'Cookie': self.config.get('cookie_str')}
                res = self.session.get(f'https://user.qzone.qq.com/{self.my_qq}/infocenter?via=toolbar', headers=headers, timeout=15)
                
                if "login" in res.url:
                    self.config = {}; continue

                soup = BeautifulSoup(res.text, 'html.parser')
                items = soup.find_all('li', class_='f-single')
                logging.info(f"[巡检] 本轮发现 {len(items)} 条动态")

                for item in items:
                    like_btn = item.find('a', class_='qz_like_btn_v3')
                    
                    # 严格判定是否未点赞
                    if like_btn and 'item-on' not in like_btn.get('class', []):
                        nick = item.find('a', class_=['nickname', 'f-name', 'qz_event_nick'])
                        nick_name = nick.get_text(strip=True) if nick else "未知好友"
                        
                        logging.info(f"  >>> 发现未赞动态: {nick_name}")
                        
                        # 执行点赞逻辑
                        if self.do_like(
                            like_btn.get('data-unikey'),
                            like_btn.get('data-curkey'),
                            like_btn.get('data-appid'),
                            like_btn.get('data-typeid'),
                            like_btn.get('data-abstime')
                        ):
                            logging.info(f"      [成功] 已点赞 -> {nick_name}")
                        else:
                            logging.error(f"      [失败] 点赞请求未成功 -> {nick_name}")
                        time.sleep(random.uniform(1.5, 3.5))
            except Exception as e:
                logging.error(f"[巡检异常] {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    qq_input = input("请输入你的QQ号：").strip()
    if qq_input:
        QZoneRobot(qq_input).run()
