# -*- coding: utf-8 -*-
# main.py
import os
import sys
import json
import time
import random
import logging
import requests
import subprocess
from bs4 import BeautifulSoup

# ================= 配置区域 =================
MY_QQ = '10086'        # 你的QQ号
CHECK_INTERVAL = 5         # 轮询间隔(秒)
CK_SCRIPT = "ck.py"         # 获取Cookie的脚本名
CONFIG_FILE = "config.json" # 配置文件名
# ===========================================

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[
        logging.FileHandler("app.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class QZoneMain:
    def __init__(self):
        self.session = requests.Session()
        self.config = {}
        
    def load_config(self):
        """加载配置文件"""
        if not os.path.exists(CONFIG_FILE):
            return False
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            # 校验QQ号是否匹配
            if str(self.config.get('qq')) != MY_QQ:
                logging.warning(f"配置文件中的QQ ({self.config.get('qq')}) 与当前设置 ({MY_QQ}) 不符")
                return False
            return True
        except Exception as e:
            logging.error(f"读取配置失败: {e}")
            return False

    def check_cookie_valid(self):
        """验证Cookie有效性"""
        if not self.config: return False
        
        headers = {
            'User-Agent': self.config.get('user_agent', ''),
            'Cookie': self.config.get('cookie_str', '')
        }
        
        # 尝试访问个人中心主页
        url = f"https://user.qzone.qq.com/{MY_QQ}/infocenter"
        try:
            # 禁止重定向，如果返回302说明Cookie失效了
            res = requests.get(url, headers=headers, allow_redirects=False, timeout=10)
            if res.status_code == 200:
                return True
            else:
                logging.warning(f"Cookie失效 (状态码: {res.status_code})")
                return False
        except Exception as e:
            logging.error(f"验证Cookie请求异常: {e}")
            return False

    def call_ck_script(self):
        """调用 ck.py 获取新Cookie"""
        if not os.path.exists(CK_SCRIPT):
            logging.error(f"找不到 {CK_SCRIPT}，无法自动获取Cookie！")
            return False
            
        logging.info("正在启动 ck.py 进行登录...")
        try:
            # 兼容 Windows/Linux python命令
            cmd = "python" if sys.platform == "win32" else "python3"
            subprocess.check_call([cmd, CK_SCRIPT])
            return True
        except subprocess.CalledProcessError:
            logging.error("ck.py 运行失败")
            return False

    def do_like(self, unikey, curkey, appid, typeid, abstime):
        """点赞请求"""
        url = 'https://user.qzone.qq.com/proxy/domain/w.qzone.qq.com/cgi-bin/likes/internal_dolike_app'
        g_tk = self.config.get('g_tk')
        
        headers = {
            'User-Agent': self.config.get('user_agent'),
            'Cookie': self.config.get('cookie_str'),
            'Referer': f'https://user.qzone.qq.com/{MY_QQ}/infocenter',
            'Origin': 'https://user.qzone.qq.com'
        }

        payload = {
            'qzreferrer': f'https://user.qzone.qq.com/{MY_QQ}/infocenter',
            'opuin': MY_QQ,
            'unikey': unikey,
            'curkey': curkey,
            'from': '1',
            'appid': appid,
            'typeid': typeid,
            'abstime': abstime,
            'fid': unikey.split('/')[-1],
            'active': '0',
            'fupdate': '1',
            'g_tk': g_tk
        }

        try:
            res = self.session.post(url + f'?g_tk={g_tk}', data=payload, headers=headers)
            return res.status_code == 200
        except:
            return False

    def run(self):
        logging.info(">>> 主程序启动 <<<")
        
        # 1. 初始化检查
        if not self.load_config() or not self.check_cookie_valid():
            logging.info("配置无效或缺失，准备调用登录脚本...")
            if self.call_ck_script():
                if not self.load_config():
                    logging.error("重新获取后配置仍无法读取，退出")
                    sys.exit(1)
            else:
                logging.error("自动登录失败，退出")
                sys.exit(1)
        
        logging.info("Cookie 验证通过，开始监听动态...")
        
        # 2. 主循环
        while True:
            try:
                # 如果运行过程中Cookie失效，自动重登
                if not self.check_cookie_valid():
                    logging.warning("运行中Cookie失效，重新获取...")
                    self.call_ck_script()
                    self.load_config()
                    continue

                target_url = f'https://user.qzone.qq.com/{MY_QQ}/infocenter?via=toolbar'
                headers = {
                    'User-Agent': self.config.get('user_agent'),
                    'Cookie': self.config.get('cookie_str')
                }
                
                res = self.session.get(target_url, headers=headers, allow_redirects=True)
                
                # 检查是否跳到了登录页
                if "login" in res.url:
                    logging.warning("监测到页面跳转至登录页，Cookie失效")
                    self.config = {} # 强制清空触发重抓
                    continue

                soup = BeautifulSoup(res.text, 'html.parser')
                items = soup.find_all('li', class_='f-single')
                
                if items:
                    for item in items:
                        like_btn = item.find('a', class_='qz_like_btn_v3')
                        # 判断是否未点赞 (没有 item-on 类)
                        if like_btn and 'item-on' not in like_btn.get('class', []):
                            nick = item.find('a', class_='nickname')
                            nick_name = nick.get_text(strip=True) if nick else "未知用户"
                            
                            logging.info(f"发现未赞动态: {nick_name}")
                            
                            # 执行点赞
                            success = self.do_like(
                                like_btn.get('data-unikey'),
                                like_btn.get('data-curkey'),
                                like_btn.get('data-appid'),
                                like_btn.get('data-typeid'),
                                like_btn.get('data-abstime')
                            )
                            
                            if success:
                                logging.info(f"点赞成功 -> {nick_name}")
                            else:
                                logging.error(f"点赞失败 -> {nick_name}")
                                
                            time.sleep(random.uniform(1, 3))
                            
            except Exception as e:
                logging.error(f"主循环异常: {e}")
                time.sleep(5)
            
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    app = QZoneMain()

    app.run()
