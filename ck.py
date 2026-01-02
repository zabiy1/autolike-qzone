# -*- coding: utf-8 -*-
# ck.py
import os
import sys
import json
import time
import zipfile
import requests
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By  # 【新增】用于定位元素

# Windows 注册表访问
if sys.platform == "win32":
    import winreg

# ================= 配置区域 =================
MY_QQ = '10086' 
CONFIG_FILE = "config.json"
DRIVER_NAME = "chromedriver.exe"

# Google 官方 API
GOOGLE_API_URL = "https://googlechromelabs.github.io/chrome-for-testing/latest-versions-per-milestone-with-downloads.json"

# 【重要】手动代理配置
MANUAL_PROXY = None 
# ===========================================

def get_proxies():
    """构造代理字典"""
    if MANUAL_PROXY:
        print(f"[CK] 使用手动代理: {MANUAL_PROXY}")
        return {
            "http": MANUAL_PROXY,
            "https": MANUAL_PROXY
        }
    return None

def get_chrome_version():
    """从注册表获取 Windows Chrome 版本"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
        version, _ = winreg.QueryValueEx(key, "version")
        return version
    except:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
            path, _ = winreg.QueryValueEx(key, "")
            return None
        except:
            return None

def download_driver():
    """下载驱动 (支持手动代理)"""
    if os.path.exists(DRIVER_NAME):
        return True
        
    print("[CK] 正在检测本地 Chrome 版本...")
    ver = get_chrome_version()
    if not ver:
        print("[CK] 无法获取 Chrome 版本，请手动下载。")
        return False
        
    print(f"[CK] 本地 Chrome 版本: {ver}")
    major_ver = ver.split('.')[0]
    
    print(f"[CK] 正在连接 Google API 获取驱动...")
    
    proxies = get_proxies()
    
    try:
        res = requests.get(GOOGLE_API_URL, proxies=proxies, timeout=15)
        if res.status_code != 200:
            print(f"[CK] API 请求失败: {res.status_code}")
            return False
            
        data = res.json()
        milestones = data.get("milestones", {})
        
        if major_ver not in milestones:
            print(f"[CK] 未找到 {major_ver} 版本的精确匹配，尝试获取最新版兼容...")
            all_keys = sorted([int(k) for k in milestones.keys()])
            major_ver = str(all_keys[-1])
            print(f"[CK] 目标版本调整为: {major_ver}")
            
        driver_info = milestones[major_ver]["downloads"]["chromedriver"]
        
        download_url = ""
        for item in driver_info:
            if item["platform"] == "win64":
                download_url = item["url"]
                break
        
        if not download_url:
            print("[CK] 未找到 win64 驱动链接。")
            return False
            
        print(f"[CK] 下载链接: {download_url}")
        
        r = requests.get(download_url, proxies=proxies, stream=True, timeout=60)
        zip_name = "driver.zip"
        with open(zip_name, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk: f.write(chunk)
                
        print("[CK] 解压中...")
        with zipfile.ZipFile(zip_name, 'r') as z:
            exe_path = next((n for n in z.namelist() if "chromedriver.exe" in n), None)
            if not exe_path:
                print("[CK] 压缩包异常。")
                return False
            
            with z.open(exe_path) as source, open(DRIVER_NAME, "wb") as target:
                shutil.copyfileobj(source, target)
        
        os.remove(zip_name)
        print(f"[CK] 驱动安装完成: {DRIVER_NAME}")
        return True

    except Exception as e:
        print(f"[CK] 下载失败: {e}")
        print("[提示] 如果是连接错误，请在 ck.py 顶部填入 MANUAL_PROXY 代理地址")
        return False

def get_cookie(is_manual_mode=False):
    if not download_driver():
        sys.exit(1)
        
    print("[CK] 启动浏览器...")
    chrome_options = Options()
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    service = Service(executable_path=DRIVER_NAME)
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        login_url = "https://qzone.qq.com/"
        print(f"[CK] 打开登录页: {login_url}")
        driver.get(login_url)
        
        # =================【修改开始】交互逻辑 =================
        if is_manual_mode:
            print(">>> [模式] 检测到 'hm' 参数，请手动扫码或点击登录 <<<")
        else:
            print(">>> [模式] 自动登录 (2秒后尝试点击头像) <<<")
            time.sleep(2) # 等待页面加载
            
            try:
                # QQ登录框在 iframe 里，必须先切进去
                driver.switch_to.frame("login_frame")
                
                # 尝试定位头像按钮
                # ID 通常为 img_out_QQ号，如果找不到就找列表里的第一个
                try:
                    # 精确查找
                    avatar_btn = driver.find_element(By.ID, f"img_out_{MY_QQ}")
                    print(f"[CK] 找到账号 {MY_QQ}，正在点击...")
                    avatar_btn.click()
                except:
                    # 模糊查找（列表第一个）
                    print("[CK] 未找到精确账号，尝试点击列表第一个...")
                    driver.find_element(By.CSS_SELECTOR, "#qlogin_list a").click()
                
                # 切回主文档，以免影响后续 URL 检测
                driver.switch_to.default_content()
                
            except Exception as e:
                print(f"[CK] 自动点击失败: {e}")
                print("[CK] 可能原因：浏览器未登录过QQ、界面改版或加载过慢。")
                print(">>> 请手动完成登录 <<<")
                # 切回主文档防止卡死
                driver.switch_to.default_content()
        # =================【修改结束】=========================
        
        # 循环等待登录
        while True:
            try:
                # 检测 URL 变化
                if "user.qzone.qq.com" in driver.current_url and "passport" not in driver.current_url:
                    print("[CK] 登录成功！")
                    break
            except: pass
            time.sleep(1)
            
        target_url = f"https://user.qzone.qq.com/{MY_QQ}/infocenter?via=toolbar"
        print(f"[CK] 跳转至: {target_url}")
        driver.get(target_url)
        
        print("[CK] 等待 5 秒确保页面加载完整...")
        time.sleep(5)
        
        print("[CK] 提取数据...")
        cookies = driver.get_cookies()
        ua = driver.execute_script("return navigator.userAgent;")
        
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
            "qq": MY_QQ,
            "cookie_str": cookie_str,
            "user_agent": ua,
            "g_tk": g_tk,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        print(f"[CK] 配置保存成功。")
        
    except Exception as e:
        print(f"[CK] 运行时错误: {e}")
    finally:
        if 'driver' in locals():
            driver.quit()

if __name__ == "__main__":
    # 检测命令行参数
    is_hm = False
    if len(sys.argv) > 1 and sys.argv[1] == 'hm':
        is_hm = True
        

    get_cookie(is_manual_mode=is_hm)
