# 微信公众号最新文章爬取工具

[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

一个轻量、稳定的微信公众号最新文章爬取工具，支持自动登录（扫码后自动提取Token/Cookie）、批量爬取、完整正文提取，解决了Chrome进程占用、接口调整等常见问题。

## ✨ 核心特性

- 🚀 **自动登录**：扫码后自动提取Token/Cookie，无需手动复制
- 📝 **完整正文**：爬取文章完整正文内容，而非仅摘要
- 💾 **缓存复用**：登录信息缓存3天，无需重复扫码
- 📂 **分类存储**：按公众号名称分类保存Markdown格式文章
- 🚨 **详细日志**：全流程日志记录，便于问题定位
- 🧹 **自动过滤**：过滤失效链接和空内容文章

## 📋 环境要求

- Python 3.7+
- Chrome浏览器（用于登录，无需手动配置Driver）
- 网络环境可正常访问微信公众平台

## 🛠️ 安装步骤

### 1. 克隆/下载项目

将本项目文件保存到本地，确保包含以下核心文件：
wechat_article_crawler/
├── wechat_crawler.py # 主程序脚本
├── requirements.txt # 依赖清单
├── gzh.txt # 公众号 fakeid 列表（需手动创建）
├── 公众号名字.txt # 公众号名称列表（需手动创建）
└── README.md # 使用说明

### 2. 安装依赖

打开终端/命令提示符，进入项目目录，执行以下命令安装依赖：

```bash
# 基础安装（推荐）
pip install -r requirements.txt

# 国内用户建议使用豆瓣源加速
pip install -r requirements.txt -i https://pypi.douban.com/simple/

# 若系统同时安装Python2/3，使用pip3
pip3 install -r requirements.txt -i https://pypi.douban.com/simple/
3. 验证依赖安装
bash
运行
# 验证核心依赖（无报错即成功）
python -c "import requests, selenium, bs4; print('依赖安装成功')"
⚙️ 配置说明
1. 准备公众号列表文件
创建两个文本文件，放在脚本同目录下：
(1) gzh.txt - 公众号 fakeid 列表
每行一个公众号的 fakeid，示例：
plaintext
Mzg4NTsdsfEwNA==
MjM5sdsddsaSSA==
(2) 公众号名字 - 公众号名称列表
每行一个公众号名称，需与gzh.txt行数一一对应，示例：
plaintext
解决方案
大模型科普
❗ 重要：两个文件的行数必须一致，否则会报错
2. 配置参数（可选）
脚本内可调整的核心配置（在wechat_crawler.py顶部）：
python
运行
LOGIN_CACHE_FILE = "wx_login_cache.json"  # 登录缓存文件
CACHE_EXPIRE_HOURS = 72                   # 缓存有效期（3天）
MIN_FILE_SIZE = 3 * 1024                  # 最小文件大小（3KB）
SAVE_DIR = "公众号文章"                   # 文章保存目录
RETRY_COUNT = 3                           # 请求重试次数
RETRY_DELAY = 5                           # 重试延迟（秒）
🚀 使用教程
1. 首次运行（需要扫码登录）
bash
运行
# 运行脚本
python wechat_crawler.py

# 若提示Python不是内部命令，使用完整路径或配置环境变量
首次运行流程：
脚本自动启动 Chrome 浏览器，打开微信公众平台登录页
在浏览器中使用微信扫码登录公众号后台
登录成功后，脚本自动提取 Token/Cookie 并保存到缓存
浏览器自动关闭，开始批量爬取文章
爬取完成后，文章保存在公众号文章目录下
2. 后续运行（无需登录）
缓存有效期内（3 天）再次运行脚本，会直接使用缓存的登录信息，无需启动浏览器和扫码：
bash
运行
python wechat_crawler.py
3. 查看结果
文章保存：按公众号名称分类保存在公众号文章目录下，格式为 Markdown
日志文件：
wx_crawl.log：全流程详细日志（含登录、爬取、错误信息）
wx_article_log.log：爬取结果统计日志
缓存文件：wx_login_cache.json（登录信息缓存，请勿手动修改）
📁 输出示例
文章文件示例（Markdown）
markdown
# 春节结束了，得去见客户了，除了聊假期，还能和客户聊点儿什么？

**公众号**：解决方案
**发布时间**：2026-02-28 10:00:00
**原文链接**：https://mp.weixin.qq.com/s/xxxxxx

## 摘要
春节后首次见客户，还可以从这几个角度切入...

## 完整正文
春节假期已经结束，...
（完整的文章正文内容）


❌ 常见问题解决
问题 1：Chrome 启动失败 / 目录占用
原因：系统残留 Chrome 进程或临时目录占用
解决：
关闭所有 Chrome 窗口
打开任务管理器，结束所有chrome.exe进程
删除脚本目录下的wx_login_cache.json（如需重新登录）
问题 2：无法提取文章正文
原因：微信反爬限制或文章链接失效
解决：
检查文章链接是否可正常访问
调整脚本中的User-Agent为微信内置浏览器标识
在crawl_article_content函数中添加time.sleep(2)增加请求延迟
问题 3：登录后 Token 提取失败
原因：微信登录页 URL 格式调整
解决：
删除wx_login_cache.json重新登录
确保 Chrome 浏览器为最新版本
登录时等待页面完全加载后再扫码
问题 4：依赖安装失败
解决方案：
bash
运行
# 升级pip
pip install --upgrade pip

# 逐个安装依赖
pip install requests>=2.31.0
pip install selenium>=4.15.0
pip install beautifulsoup4>=4.12.2
📄 许可证
本项目采用 MIT 许可证 - 详见 LICENSE 文件
📞 免责声明
本工具仅用于学习和研究目的，请勿用于商业用途
使用本工具需遵守微信公众平台的使用规范，请勿爬取敏感信息
爬取频率请适度，避免给微信服务器造成压力

因使用本工具产生的任何法律责任，由使用者自行承担
