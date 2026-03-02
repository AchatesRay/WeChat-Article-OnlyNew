#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import json
import time
import os
import re
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup

# ===================== 日志配置 =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("wx_crawl.log", encoding="utf-8", mode="a")
    ]
)
logger = logging.getLogger(__name__)

# ===================== 核心配置 =====================
LOGIN_CACHE_FILE = "wx_login_cache.json"
CACHE_EXPIRE_HOURS = 72
RETRY_COUNT = 3
RETRY_DELAY = 5
MIN_FILE_SIZE = 3 * 1024
BASE_SAVE_DIR = "公众号文章"
GZH_FAKEID_FILE = "公众号fakeid.txt"
GZH_NAME_FILE = "公众号名字.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF XWEB/11941",
    "Referer": "https://mp.weixin.qq.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Upgrade-Insecure-Requests": "1"
}

# ===================== 登录 =====================
def save_login_cache(token, cookies):
    try:
        cache_data = {
            "token": token,
            "cookies": cookies,
            "timestamp": time.time()
        }
        with open(LOGIN_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ 登录信息已缓存到 {LOGIN_CACHE_FILE}")
    except Exception as e:
        logger.error(f"❌ 缓存保存失败: {str(e)}")

def load_login_cache():
    try:
        if not os.path.exists(LOGIN_CACHE_FILE):
            return None, None
        
        with open(LOGIN_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        
        if time.time() - cache["timestamp"] > CACHE_EXPIRE_HOURS * 3600:
            logger.warning("⚠️ 登录缓存已过期")
            os.remove(LOGIN_CACHE_FILE)
            return None, None
        
        if validate_login(cache["token"], cache["cookies"]):
            logger.info("✅ 使用缓存的登录信息")
            return cache["token"], cache["cookies"]
        else:
            logger.warning("⚠️ 缓存的登录信息失效")
            os.remove(LOGIN_CACHE_FILE)
            return None, None
    except Exception as e:
        logger.error(f"❌ 加载缓存失败: {str(e)}")
        return None, None

def validate_login(token, cookies):
    try:
        url = "https://mp.weixin.qq.com/cgi-bin/searchbiz"
        params = {
            "action": "search_biz",
            "token": token,
            "lang": "zh_CN",
            "f": "json",
            "ajax": "1",
            "query": "test",
            "begin": 0,
            "count": 1
        }
        resp = requests.get(url, headers=HEADERS, cookies=cookies, params=params, timeout=10, verify=False)
        resp.raise_for_status()
        result = resp.json()
        return result["base_resp"]["ret"] == 0
    except Exception as e:
        logger.error(f"❌ 验证Token失败: {str(e)}")
        return False

def auto_extract_token_cookie():
    logger.info("\n========== 自动登录流程 ==========")
    logger.info("📱 即将启动Chrome浏览器，请扫码登录微信公众平台")
    logger.info("⏳ 登录成功后会自动提取信息，无需手动复制！")
    
    chrome_options = Options()
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--start-maximized')
    
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.get("https://mp.weixin.qq.com/")
        logger.info("✅ Chrome已启动，请在浏览器中扫码登录（3分钟内有效）")
        
        wait = WebDriverWait(driver, 180)
        wait.until(lambda d: "token=" in d.current_url and "mp.weixin.qq.com" in d.current_url)
        
        logger.info("✅ 检测到登录成功，开始自动提取信息...")
        token = re.search(r'token=(\d+)', driver.current_url).group(1)
        cookies = {c['name']: c['value'] for c in driver.get_cookies()}
        
        logger.info(f"✅ 自动提取Token成功: {token[:6]}****")
        if validate_login(token, cookies):
            save_login_cache(token, cookies)
            return token, cookies
        else:
            logger.error("❌ 提取的Token/Cookie无效")
            return None, None
    except TimeoutException:
        logger.error("❌ 登录超时")
        return None, None
    except Exception as e:
        logger.error(f"❌ 自动提取信息失败: {str(e)}", exc_info=True)
        return None, None
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("✅ Chrome已关闭")
            except:
                pass

# ===================== 爬取文章 =====================
def load_gzh_list():
    try:
        with open(GZH_FAKEID_FILE, "r", encoding="utf-8") as f:
            fakeids = [line.strip() for line in f if line.strip()]
        with open(GZH_NAME_FILE, "r", encoding="utf-8") as f:
            names = [line.strip() for line in f if line.strip()]
        
        if len(fakeids) != len(names):
            raise ValueError(f"fakeid文件和名称文件行数不一致！")
        
        gzh_list = [{"fakeid": fid, "name": name} for fid, name in zip(fakeids, names)]
        logger.info(f"✅ 成功加载 {len(gzh_list)} 个公众号")
        return gzh_list
    except Exception as e:
        logger.error(f"❌ 加载公众号列表失败: {str(e)}")
        return []

def get_article_basic_info(token, cookies, fakeid):
    url = f"https://mp.weixin.qq.com/cgi-bin/appmsg?action=list_ex&begin=0&count=1&fakeid={fakeid}&type=9&token={token}&f=json&ajax=1"
    for retry in range(RETRY_COUNT):
        try:
            resp = requests.get(url, headers=HEADERS, cookies=cookies, timeout=10, verify=False)
            resp.raise_for_status()
            data = resp.json()
            if data["base_resp"]["ret"] != 0:
                logger.error(f"❌ 公众号{fakeid}请求失败: {data['base_resp']['err_msg']}")
                return None
            return data.get("app_msg_list", [None])[0]
        except Exception as e:
            logger.warning(f"⚠️ 公众号{fakeid}第{retry+1}次重试")
            time.sleep(RETRY_DELAY)
    return None

def crawl_article_content(article_url, cookies):
    for retry in range(RETRY_COUNT):
        try:
            resp = requests.get(article_url, headers=HEADERS, cookies=cookies, timeout=15, verify=False)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            content = soup.find("div", class_="rich_media_content") or soup.find("div", id="js_content")
            if not content:
                return None
            for tag in content.find_all(["script", "style", "iframe", "img"]):
                tag.decompose()
            text = content.get_text(strip=True, separator="\n\n")
            lines = [l.strip() for l in text.split("\n\n") if l.strip()]
            return "\n\n".join(lines)
        except Exception:
            time.sleep(RETRY_DELAY)
    return None

def get_latest_article(token, cookies, fakeid):
    info = get_article_basic_info(token, cookies, fakeid)
    if not info:
        return None
    info["full_content"] = crawl_article_content(info.get("link"), cookies) or info.get("digest", "无内容")
    return info

# ===================== 保存逻辑（已修改：无公众号文件夹）=====================
def save_article(article, gzh_name):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        # 只创建：公众号文章/2026-03-02
        save_dir = os.path.join(BASE_SAVE_DIR, today)
        os.makedirs(save_dir, exist_ok=True)

        # 处理文件名非法字符
        title = article.get("title", "无标题")
        invalid = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for ch in invalid:
            title = title.replace(ch, "")

        # 文件名：公众号名_日期_文章名.md
        filename = f"{gzh_name}_{today}_{title}.md"
        filepath = os.path.join(save_dir, filename)

        publish_time = datetime.fromtimestamp(article.get("update_time", time.time())).strftime("%Y-%m-%d %H:%M:%S")
        content = f"""# {article.get('title')}

**公众号**：{gzh_name}
**发布时间**：{publish_time}
**爬取时间**：{today}
**原文链接**：{article.get('link')}

## 摘要
{article.get('digest', '无摘要')}

## 正文
{article.get('full_content')}
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        size = os.path.getsize(filepath)
        if size < MIN_FILE_SIZE:
            logger.warning(f"⚠️ 文件偏小但已保存：{filepath}")
        else:
            logger.info(f"✅ 已保存：{filepath}")
        return True

    except Exception as e:
        logger.error(f"❌ 保存失败：{str(e)}")
        return False

def record_log(gzh_name, title, ok):
    try:
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {gzh_name} | {title} | {'成功' if ok else '失败'}\n"
        with open("wx_article_log.log", "a", encoding="utf-8") as f:
            f.write(line)
    except:
        pass

# ===================== 主程序 =====================
def main():
    requests.packages.urllib3.disable_warnings()
    logger.info("===== 微信公众号文章爬取工具（按日期平铺保存）=====")

    token, cookies = load_login_cache()
    if not token or not cookies:
        token, cookies = auto_extract_token_cookie()
    if not token or not cookies:
        logger.critical("❌ 登录失败，程序终止")
        return

    gzh_list = load_gzh_list()
    if not gzh_list:
        logger.warning("⚠️ 无公众号可爬取")
        return

    ok = 0
    fail = 0
    for gzh in gzh_list:
        name = gzh["name"]
        logger.info(f"\n--- 处理：{name} ---")
        art = get_latest_article(token, cookies, gzh["fakeid"])
        if not art:
            record_log(name, "无文章", False)
            fail +=1
            continue
        if "tempkey=" in art.get("link", ""):
            logger.warning("⚠️ 文章链接已失效")
            record_log(name, art["title"], False)
            fail +=1
            continue
        if save_article(art, name):
            ok +=1
            record_log(name, art["title"], True)
        else:
            fail +=1
            record_log(name, art["title"], False)

    logger.info("\n===== 爬取完成 =====")
    logger.info(f"✅ 成功：{ok} 篇   ❌ 失败：{fail} 篇")
    logger.info(f"📁 文件保存在：{os.path.join(BASE_SAVE_DIR, datetime.now().strftime('%Y-%m-%d'))}")

if __name__ == "__main__":
    main()
    input("\n按回车退出...")
