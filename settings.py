"""配置：yaml + 环境变量 → Settings 对象。

加载顺序（后者覆盖前者）：
    dataclass 默认值 → config/settings.yaml → config/account.yaml → 环境变量

铁律：默认值只在 dataclass 字段上写这一遍，别处不许再抄。
未知配置键直接 ConfigError —— 防止拼错键名后静默失效。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from urllib.parse import urlparse

import yaml

from errors import ConfigError

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config" / "settings.yaml"
ACCOUNT_FILE = ROOT / "config" / "account.yaml"


@dataclass
class BrowserCfg:
    name: str = "edge"            # edge | chrome
    headless: bool = False        # True = 不弹窗口（登录要扫码/手动时别开）
    width: int = 1280
    height: int = 800
    page_load_timeout: int = 30   # 页面加载超时（秒）
    profile_dir: str = "state/browser-profile"  # 登录态保存在这，二次启动免登录


@dataclass
class LoginCfg:
    mode: str = "manual"          # manual = 自己在弹出的浏览器里登录（稳）；auto = 自动填表
    url: str = "https://passport.zhihuishu.com/login"
    wait_timeout: int = 180       # manual 模式等你登录的最长秒数


@dataclass
class TargetCfg:
    base_url: str = "https://www.zhihuishu.com"
    course_url: str = ""          # ★必填：你的课程学习页链接（浏览器里打开课程后复制地址栏）
    allowed_hosts: tuple = ("zhihuishu.com",)  # 安全闸门：只许访问这些域名的页面


@dataclass
class WaitsCfg:
    find_timeout: float = 10.0    # 找一个元素的最长等待（秒）
    poll: float = 0.5             # 状态机轮询间隔（秒）
    max_idle: float = 10.0


@dataclass
class Account:
    username: str = ""
    password: str = ""


@dataclass
class Settings:
    browser: BrowserCfg = field(default_factory=BrowserCfg)
    login: LoginCfg = field(default_factory=LoginCfg)
    target: TargetCfg = field(default_factory=TargetCfg)
    waits: WaitsCfg = field(default_factory=WaitsCfg)
    account: Account = field(default_factory=Account)

    def resolve(self, rel: str) -> Path:
        """把配置里的相对路径解析成项目内绝对路径。"""
        return (ROOT / rel).resolve()


# ---------------------------------------------------------------- 读取与校验

def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name} 解析失败：{exc}") from exc
    return data or {}


def _apply(section: dict, obj: object, path: str) -> None:
    """把 yaml 里的一段覆盖到 dataclass 上；出现不认识的键就报错。"""
    known = {f.name for f in fields(obj)}
    for key, value in section.items():
        if key not in known:
            raise ConfigError(f"未知配置项 {path}.{key} —— 拼写错误？查 理解.md 的配置表")
        setattr(obj, key, value)


def assert_safe(url: str, allowed_hosts: tuple) -> None:
    """安全闸门：url 的域名必须在白名单里，否则拒绝（防配置写错后脚本去陌生网站乱点）。"""
    host = urlparse(url).hostname or ""
    if not any(host == h or host.endswith("." + h) for h in allowed_hosts):
        raise ConfigError(f"目标不在允许的域名内：{url}（allowed_hosts={allowed_hosts}）")


def _validate(cfg: Settings) -> None:
    if cfg.browser.name not in ("edge", "chrome"):
        raise ConfigError(f"browser.name 只支持 edge/chrome，当前：{cfg.browser.name!r}")
    if cfg.login.mode not in ("manual", "auto"):
        raise ConfigError(f"login.mode 只支持 manual/auto，当前：{cfg.login.mode!r}")
    for name in ("base_url",):
        assert_safe(getattr(cfg.target, name), cfg.target.allowed_hosts)
    assert_safe(cfg.login.url, cfg.target.allowed_hosts)
    if cfg.target.course_url:
        assert_safe(cfg.target.course_url, cfg.target.allowed_hosts)
    if cfg.login.mode == "auto" and not (cfg.account.username and cfg.account.password):
        raise ConfigError("login.mode=auto 需要 config/account.yaml 或环境变量里有账号密码")


def load_settings(config_path: Path | str | None = DEFAULT_CONFIG) -> Settings:
    cfg = Settings()
    data = _read_yaml(Path(config_path or DEFAULT_CONFIG))
    for section_name, section_obj in (
        ("browser", cfg.browser), ("login", cfg.login),
        ("target", cfg.target), ("waits", cfg.waits),
    ):
        if section_name in data:
            _apply(data[section_name], section_obj, section_name)

    # 账号：account.yaml 打底，环境变量最高（避免密码躺在文件里）
    account = _read_yaml(ACCOUNT_FILE)
    cfg.account.username = account.get("username") or cfg.account.username
    cfg.account.password = account.get("password") or cfg.account.password
    cfg.account.username = os.environ.get("ZHS_USERNAME") or cfg.account.username
    cfg.account.password = os.environ.get("ZHS_PASSWORD") or cfg.account.password

    _validate(cfg)
    return cfg
