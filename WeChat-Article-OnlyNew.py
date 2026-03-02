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
CACHE_EXPIRE_HOURS = 72  # 缓存3天
RETRY_COUNT = 3
RETRY_DELAY = 5
MIN_FILE_SIZE = 3 * 1024  # 3KB
SAVE_DIR = "公众号文章"
GZH_FAKEID_FILE = "gzh.txt"
GZH_NAME_FILE = "公众号名字.txt"

# 请求头（模拟微信内置浏览器）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF XWEB/11941",
    "Referer": "https://mp.weixin.qq.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Upgrade-Insecure-Requests": "1"
}

# ===================== 登录核心 =====================
def save_login_cache(token, cookies):
    """保存登录信息到本地"""
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
    """加载并验证缓存"""
    try:
        if not os.path.exists(LOGIN_CACHE_FILE):
            return None, None
        
        with open(LOGIN_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        
        # 检查过期
        if time.time() - cache["timestamp"] > CACHE_EXPIRE_HOURS * 3600:
            logger.warning("⚠️ 登录缓存已过期，需要重新登录")
            os.remove(LOGIN_CACHE_FILE)
            return None, None
        
        # 验证有效性
        if validate_login(cache["token"], cache["cookies"]):
            logger.info("✅ 使用缓存的登录信息")
            return cache["token"], cache["cookies"]
        else:
            logger.warning("⚠️ 缓存的登录信息失效，需要重新登录")
            os.remove(LOGIN_CACHE_FILE)
            return None, None
    except Exception as e:
        logger.error(f"❌ 加载缓存失败: {str(e)}")
        return None, None

def validate_login(token, cookies):
    """验证Token和Cookie是否有效"""
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
        resp = requests.get(
            url, 
            headers=HEADERS, 
            cookies=cookies, 
            params=params, 
            timeout=10,
            verify=False
        )
        resp.raise_for_status()
        result = resp.json()
        return result["base_resp"]["ret"] == 0
    except Exception as e:
        logger.error(f"❌ 验证Token失败: {str(e)}")
        return False

def auto_extract_token_cookie():
    """启动极简浏览器，扫码后自动提取Token和Cookie"""
    logger.info("\n========== 自动登录流程 ==========")
    logger.info("📱 即将启动Chrome浏览器，请扫码登录微信公众平台")
    logger.info("⏳ 登录成功后会自动提取信息，无需手动复制！")
    
    # 配置Chrome（极简模式，无自动化特征）
    chrome_options = Options()
    # 关键：禁用自动化检测 + 不创建临时目录（避免占用）
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    # 基础配置（避免卡顿）
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--start-maximized')
    
    # 启动Chrome（仅打开登录页，无其他操作）
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        # 移除webdriver特征
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # 打开微信公众平台登录页
        driver.get("https://mp.weixin.qq.com/")
        logger.info("✅ Chrome已启动，请在浏览器中扫码登录（3分钟内有效）")
        
        # 等待登录成功（URL包含token）
        wait = WebDriverWait(driver, 180)  # 3分钟超时
        wait.until(lambda d: "token=" in d.current_url and "mp.weixin.qq.com" in d.current_url)
        
        # 登录成功，提取Token和Cookie
        logger.info("✅ 检测到登录成功，开始自动提取信息...")
        # 提取Token
        token = re.search(r'token=(\d+)', driver.current_url).group(1)
        # 提取Cookie（转换为字典）
        cookies = {c['name']: c['value'] for c in driver.get_cookies()}
        
        logger.info(f"✅ 自动提取Token成功: {token[:6]}****")
        logger.info(f"✅ 自动提取Cookie成功（共{len(cookies)}个字段）")
        
        # 验证并保存
        if validate_login(token, cookies):
            save_login_cache(token, cookies)
            return token, cookies
        else:
            logger.error("❌ 提取的Token/Cookie无效，请重新登录")
            return None, None
    
    except TimeoutException:
        logger.error("❌ 登录超时（3分钟），请重新运行脚本")
        return None, None
    except Exception as e:
        logger.error(f"❌ 自动提取信息失败: {str(e)}", exc_info=True)
        return None, None
    finally:
        # 关闭浏览器（无论成败）
        if driver:
            try:
                driver.quit()
                logger.info("✅ Chrome已关闭")
            except:
                pass

# ===================== 文章爬取（新增完整正文爬取） =====================
def load_gzh_list():
    """加载公众号列表"""
    try:
        with open(GZH_FAKEID_FILE, "r", encoding="utf-8") as f:
            fakeids = [line.strip() for line in f if line.strip()]
        with open(GZH_NAME_FILE, "r", encoding="utf-8") as f:
            names = [line.strip() for line in f if line.strip()]
        
        if len(fakeids) != len(names):
            raise ValueError(f"fakeid文件({len(fakeids)}行)和名称文件({len(names)}行)行数不一致！")
        
        gzh_list = [{"fakeid": fid, "name": name} for fid, name in zip(fakeids, names)]
        logger.info(f"✅ 成功加载 {len(gzh_list)} 个公众号")
        return gzh_list
    except FileNotFoundError as e:
        logger.critical(f"❌ 未找到文件: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"❌ 加载公众号列表失败: {str(e)}")
        return []

def get_article_basic_info(token, cookies, fakeid):
    """获取文章基础信息（标题、链接、摘要等）"""
    url = f"https://mp.weixin.qq.com/cgi-bin/appmsg?action=list_ex&begin=0&count=1&fakeid={fakeid}&type=9&token={token}&f=json&ajax=1"
    
    for retry in range(RETRY_COUNT):
        try:
            resp = requests.get(
                url, 
                headers=HEADERS, 
                cookies=cookies, 
                timeout=10,
                verify=False
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data["base_resp"]["ret"] != 0:
                logger.error(f"❌ 公众号{fakeid}请求失败: {data['base_resp']['err_msg']}")
                return None
            
            if not data.get("app_msg_list"):
                logger.info(f"ℹ️ 公众号{fakeid}暂无文章")
                return None
            
            return data["app_msg_list"][0]
        except Exception as e:
            logger.warning(f"⚠️ 公众号{fakeid}第{retry+1}次重试: {str(e)}")
            time.sleep(RETRY_DELAY)
    
    logger.error(f"❌ 公众号{fakeid}请求失败（重试{RETRY_COUNT}次）")
    return None

def crawl_article_content(article_url, cookies):
    """爬取文章完整正文内容"""
    logger.debug(f"📡 爬取文章完整内容: {article_url}")
    
    for retry in range(RETRY_COUNT):
        try:
            # 请求文章详情页
            resp = requests.get(
                article_url,
                headers=HEADERS,
                cookies=cookies,
                timeout=15,
                verify=False
            )
            resp.raise_for_status()
            resp.encoding = "utf-8"
            
            # 解析HTML提取正文
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # 微信文章正文核心标签
            content_div = soup.find("div", class_="rich_media_content")
            if not content_div:
                content_div = soup.find("div", id="js_content")
            
            if content_div:
                # 清理无关标签（广告、二维码等）
                for ad_tag in content_div.find_all(["script", "style", "iframe", "img"]):
                    ad_tag.decompose()
                
                # 提取纯文本内容
                content_text = content_div.get_text(strip=True, separator="\n\n")
                # 过滤空行和多余空格
                content_lines = [line.strip() for line in content_text.split("\n\n") if line.strip()]
                full_content = "\n\n".join(content_lines)
                
                if full_content:
                    logger.info(f"✅ 成功提取文章完整正文（{len(full_content)}字符）")
                    return full_content
            
            logger.warning("⚠️ 未找到文章正文，使用摘要替代")
            return None
        except Exception as e:
            logger.warning(f"⚠️ 爬取正文第{retry+1}次重试: {str(e)}")
            time.sleep(RETRY_DELAY)
    
    logger.error("❌ 爬取文章正文失败，使用摘要替代")
    return None

def get_latest_article(token, cookies, fakeid):
    """获取单个公众号最新文章（含完整正文）"""
    # 1. 获取基础信息
    basic_info = get_article_basic_info(token, cookies, fakeid)
    if not basic_info:
        return None
    
    # 2. 爬取完整正文
    article_url = basic_info.get("link")
    full_content = crawl_article_content(article_url, cookies)
    
    # 3. 合并数据（优先用完整正文，无则用摘要）
    basic_info["full_content"] = full_content if full_content else basic_info.get("digest", "无内容")
    
    logger.debug(f"✅ 公众号{fakeid}获取到最新文章: {basic_info['title']}")
    return basic_info

def save_article(article, gzh_name):
    """保存文章为Markdown（包含完整正文）"""
    try:
        # 创建目录
        gzh_dir = os.path.join(SAVE_DIR, gzh_name)
        os.makedirs(gzh_dir, exist_ok=True)
        
        # 处理标题特殊字符
        title = article.get("title", "无标题")
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            title = title.replace(char, "_")
        file_path = os.path.join(gzh_dir, f"{title}.md")
        
        # 构造内容（使用完整正文）
        publish_time = datetime.fromtimestamp(article.get("update_time", article.get("create_time"))).strftime("%Y-%m-%d %H:%M:%S")
        md_content = f"""# {article.get('title', '无标题')}

**公众号**：{gzh_name}
**发布时间**：{publish_time}
**原文链接**：{article.get('link', '')}

## 摘要
{article.get('digest', '无摘要')}

## 完整正文
{article.get('full_content', '无内容')}
"""
        # 写入文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        # 检查文件大小（保留过滤，但降低阈值或给出提示）
        file_size = os.path.getsize(file_path)
        if file_size < MIN_FILE_SIZE:
            logger.warning(f"⚠️ 文件偏小但保留: {file_path}（{file_size}字节）- 可能是短文/爬取限制")
            # 不再删除，仅提示
            return True
        
        logger.info(f"✅ 文章保存成功: {file_path}（大小：{file_size}字节）")
        return True
    except Exception as e:
        logger.error(f"❌ 保存文章失败: {str(e)}")
        return False

def record_log(gzh_name, title, success):
    """记录爬取日志"""
    try:
        log_line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {gzh_name} | {title} | {'成功' if success else '失败'}\n"
        with open("wx_article_log.log", "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        logger.error(f"❌ 记录日志失败: {str(e)}")

# ===================== 主程序 =====================
def main():
    """主程序入口"""
    logger.info("===== 微信公众号最新文章爬取工具（完整正文版）=====")
    # 忽略SSL警告
    requests.packages.urllib3.disable_warnings()
    
    # 1. 登录（优先缓存，失效则自动提取）
    token, cookies = load_login_cache()
    if not token or not cookies:
        token, cookies = auto_extract_token_cookie()
    if not token or not cookies:
        logger.critical("❌ 登录失败，程序终止")
        return
    
    # 2. 加载公众号列表
    gzh_list = load_gzh_list()
    if not gzh_list:
        logger.warning("⚠️ 未加载到任何公众号，程序终止")
        return
    
    # 3. 批量爬取
    success_count = 0
    fail_count = 0
    logger.info(f"🚀 开始爬取 {len(gzh_list)} 个公众号的最新文章...")
    
    for gzh in gzh_list:
        fakeid = gzh["fakeid"]
        gzh_name = gzh["name"]
        logger.info(f"\n--- 处理公众号：{gzh_name}（fakeid：{fakeid}）---")
        
        # 获取最新文章（含完整正文）
        article = get_latest_article(token, cookies, fakeid)
        if not article:
            record_log(gzh_name, "无文章/获取失败", False)
            fail_count += 1
            continue
        
        # 过滤失效文章
        if "tempkey=" in article.get("link", ""):
            logger.warning(f"⚠️ 过滤失效文章: {article['title']}")
            record_log(gzh_name, article["title"], False)
            fail_count += 1
            continue
        
        # 保存文章
        if save_article(article, gzh_name):
            success_count += 1
            record_log(gzh_name, article["title"], True)
        else:
            fail_count += 1
            record_log(gzh_name, article["title"], False)
    
    # 统计结果
    logger.info("\n===== 爬取完成 ======")
    logger.info(f"📊 统计：成功 {success_count} 篇 | 失败 {fail_count} 篇")
    logger.info(f"📁 文章保存目录：{os.path.abspath(SAVE_DIR)}")
    logger.info(f"📄 日志文件：{os.path.abspath('wx_crawl.log')}")

if __name__ == "__main__":
    # 安装依赖提示（首次运行）
    # logger.info("提示：若缺少依赖，请执行 → pip install selenium requests beautifulsoup4")
    main()
    input("\n按回车键退出...")