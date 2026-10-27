"""唯一入口。用法（在本目录下运行）：

    python main.py check          # 只检查配置，不开浏览器
    python main.py run            # 登录 + 刷课
    python main.py run --config config/settings.yaml

依赖：pip install selenium pyyaml
"""

from __future__ import annotations

import argparse
import logging
import sys

from errors import AutomationError, ConfigError, UiTimeout
from logging_setup import setup_logging
from settings import Settings, load_settings

logger = logging.getLogger("main")


def cmd_check(cfg: Settings) -> int:
    """不开浏览器，把配置全过一遍：URL 白名单、登录模式、账号、课程链接。"""
    if not cfg.target.course_url:
        raise ConfigError(
            "target.course_url 还是空的 —— 打开浏览器进课程学习页，把地址栏复制到 config/settings.yaml"
        )
    print("✔ 配置可读")
    print(f"  浏览器     {cfg.browser.name}（headless={cfg.browser.headless}）")
    print(f"  登录模式   {cfg.login.mode}" + ("（用 account.yaml 的账号密码）" if cfg.login.mode == "auto" else "（自己手动登录）"))
    print(f"  课程页     {cfg.target.course_url}")
    print(f"  域名白名单 {cfg.target.allowed_hosts} —— 安全闸门已核对")
    return 0


def cmd_run(cfg: Settings) -> int:
    log_file = setup_logging()
    logger.info("日志文件：%s", log_file)
    cmd_check(cfg)  # 开浏览器前先自查一遍，错误尽早暴露

    # 到这一步才 import 浏览器相关，check 模式完全不需要 selenium
    from browser import open_driver
    from pages import LoginPage, run_course
    from ui import SeleniumUi

    with open_driver(cfg) as driver:
        ui = SeleniumUi(driver, cfg.waits.find_timeout, cfg.waits.poll)

        # ---- 第 1 步：登录 ----
        LoginPage.open(ui, cfg.login.url)
        if cfg.login.mode == "auto":
            LoginPage.auto_login(ui, cfg.account.username, cfg.account.password)
        LoginPage.wait_manual(ui, cfg.login.wait_timeout)  # auto 模式也用它等跳转，双保险

        # ---- 第 2 步：进课程页，起状态机 ----
        logger.info("打开课程页：%s", cfg.target.course_url)
        ui.open(cfg.target.course_url)
        run_course(ui, poll=cfg.waits.poll,max_idle=cfg.waits.max_idle)

    logger.info("全部完成 ✔")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="智慧树网课脚本（精简版）")
    parser.add_argument("command", choices=["run", "check"], help="run=登录+刷课；check=只验配置")
    parser.add_argument("--config", default=None, help="配置文件路径，默认 config/settings.yaml")
    args = parser.parse_args(argv)

    try:
        cfg = load_settings(args.config)
        return cmd_run(cfg) if args.command == "run" else cmd_check(cfg)
    except ConfigError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return 2
    except UiTimeout as exc:
        logger.error("超时：%s", exc)
        return 1
    except AutomationError as exc:
        logger.error("自动化中止：%s", exc)
        return 1
    except KeyboardInterrupt:
        print("\n用户中断（Ctrl+C）")
        return 130


if __name__ == "__main__":
    sys.exit(main())
