"""浏览器工厂：按配置造 driver；with 语句保证任何异常下浏览器都会被关掉。

只被 main.py 调用一次。ui.py 负责"怎么操作浏览器"，本文件负责"怎么造出浏览器"。
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions

from settings import Settings

logger = logging.getLogger(__name__)


def build_driver(settings: Settings) -> webdriver.Edge | webdriver.Chrome:
    cfg = settings.browser
    options = EdgeOptions() if cfg.name == "edge" else ChromeOptions()

    if cfg.headless:
        options.add_argument("--headless=new")
    options.add_argument(f"--window-size={cfg.width},{cfg.height}")
    # 消音参数：关掉首次运行向导/默认浏览器提示/扩展，任何弹窗都是自动化的敌人
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")

    # 登录态存在项目内的 profile 目录：二次启动免登录；
    # 别放系统临时目录，受限环境下会"启动后立即断连"
    profile_dir = settings.resolve(cfg.profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)
    options.add_argument(f"--user-data-dir={profile_dir}")
    logger.debug("浏览器 profile：%s", profile_dir)

    logger.info("启动浏览器：%s（headless=%s）", cfg.name, cfg.headless)
    driver = webdriver.Edge(options=options) if cfg.name == "edge" else webdriver.Chrome(options=options)
    driver.set_page_load_timeout(cfg.page_load_timeout)
    return driver


@contextmanager
def open_driver(settings: Settings):
    """with open_driver(cfg) as driver: ... —— 无论正常结束还是崩，finally 都 quit()。"""
    driver = build_driver(settings)
    try:
        yield driver
    finally:
        try:
            driver.quit()
            logger.info("浏览器已关闭")
        except Exception as exc:  # 关不掉也别掩盖真正的错误，只记一笔
            logger.warning("关闭浏览器时出错（已忽略）：%s", exc)
