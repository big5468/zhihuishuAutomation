"""页面对象 + 刷课状态机（项目的心脏）。

分工：
- LoginPage / CoursePage = "页面上有什么、怎么操作"，选择器全部住在这里
- run_course() = "整件事的流程"：一个 while 循环四个分支，是全项目最重要的 30 行

⚠ 选择器说明：下面带 [待校对] 标记的是对真实智慧树页面的"最佳猜测"，
未经真机验证。第一次真跑如果报"等待元素超时"，按 理解.md 的《选择器
校对指南》用 F12 对着真实页面把选择器改对即可 —— 逻辑不用动。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from time import sleep
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from sqlalchemy.testing.config import ident

from errors import AutomationError, UiTimeout

if TYPE_CHECKING:  # 只在类型检查时导入，运行时 pages 不依赖 ui/selenium
    from ui import Ui

logger = logging.getLogger(__name__)


class LoginPage:
    """登录页。manual 模式是主通道：不碰任何表单元素，只看 URL。

    登录页的域名可能有两个（login.zhihuishu.com 新 / passport 旧），
    判断"登录成功" = 当前页域名离开了这些登录域 —— 零 DOM 依赖。
    """

    # 登录页专属域名：URL 还停在这些域上 = 还没登录成功
    LOGIN_HOSTS = ("login.zhihuishu.com", "passport.zhihuishu.com")

    USER = "input#username"    # [待校对] auto 模式的账号输入框
    PASS = "input#password"    # [待校对] auto 模式的密码输入框
    SUBMIT = "#loginBtn"       # [待校对] auto 模式的登录按钮

    @classmethod
    def open(cls, ui: "Ui", login_url: str) -> None:
        ui.open(login_url)

    @classmethod
    def auto_login(cls, ui: "Ui", username: str, password: str) -> None:
        """自动填表登录（表单结构变了就失效，届时改上面的选择器）。"""
        logger.info("自动填表登录：%s", username)
        ui.type(cls.USER, username)
        ui.type(cls.PASS, password)
        ui.click(cls.SUBMIT)

    @classmethod
    def wait_manual(cls, ui: "Ui", timeout: float) -> str:
        """manual 模式：开好登录页后等你亲手登录（含扫码）。

        判断"登录成功"的信号 = 当前页的域名离开了登录域（LOGIN_HOSTS）——
        完全不依赖页面 DOM，这是旧项目验证过最抗改版的通道。
        """
        logger.info("请在弹出的浏览器里完成登录（%d 秒内）……", int(timeout))
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            host = urlparse(ui.url()).hostname or ""
            if host and host not in cls.LOGIN_HOSTS:
                logger.info("登录成功，当前页：%s", ui.url())
                return ui.url()
            time.sleep(1.0)
        raise UiTimeout(f"等了 {timeout:.0f}s 还没登录成功（URL 仍停留在登录页）")


class CoursePage:
    """课程学习页：视频播放、弹题、防作弊检测。"""

    POPUP_TEXT = " AI助教小智给你出题啦！学习过程中有问题，随时"  # 弹窗文字
    POPUP_CLOSE = "关闭"

    VIDEO = "video"                          # <video> 标签，几乎不会变
    # POPUP_OPTION = ".examPanel input[type=radio], .examPanel input[type=checkbox]"
    # POPUP_SUBMIT = ".examPanel .submit"      # 弹题提交按钮
    POPUP_OPTION = ".icon.topic-option"
    NEXT_EP = ".nextButton"                  # 下一集
    VERIFY = ".verify-mask, .ydm-main"       # [待校对] 防作弊/验证弹层
    FINISHED = ".videoFinish, .playFinish"   # 全部播完的标识
    #POPUP_CLOSE = ".dialog-footer .bth" # [待校对] 关闭弹窗面板

    # ---------- 单个动作（每个只做一件事，状态机负责编排） ----------

    @classmethod
    def has_verify(cls, ui: "Ui") -> bool:
        return ui.exists(cls.VERIFY)

    @classmethod
    def has_popup(cls, ui: "Ui") -> bool:
        return ui.js(
            "var hit = [...document.querySelectorAll('div,span')]"
            f".some(e => e.textContent.includes('{cls.POPUP_TEXT}'));"
            "return hit ? 'yes' : null;"
        ) is not None

    @classmethod
    def answer_popup(cls, ui: "Ui") -> None:
        """弹题作答：选第一个选项然后提交。答错一般只记一次，重点是别卡住播放。"""
        logger.info("检测到弹题 → 选择答案")
        try:
            ui.wait(cls.POPUP_OPTION,timeout=10)
            ui.click(cls.POPUP_OPTION)
            logger.info("点击完成")
        except UiTimeout:
            logger.info("答题点击未完成")




    @classmethod
    def is_paused(cls, ui: "Ui") -> bool:
        """通过 JS 读 video.paused 属性（js 会自动进 iframe 找）。找不到视频返回 False。"""
        return bool(ui.js("var v=document.querySelector('video'); return v ? v.paused : null"))

    @classmethod
    def resume(cls, ui: "Ui") -> None:
        """用 JS 调 play() 恢复播放"""
        if ui.js("var v=document.querySelector('video'); if(v){v.play(); return 'ok'} return null"):
            logger.info("视频是暂停的 → 已恢复播放")

    @classmethod
    def is_ended(cls,ui:"Ui") -> bool:
        """用 JS 调用ended看看是否播放完成"""
        return ui.js(
            "var v = document.querySelector('video'); return (v && v.ended) ? 'ended' : null;"
        ) is not None


    @classmethod
    def play_next(cls, ui: "Ui") -> None:
        logger.info("本集播完 → 切下一集")
        try:
            ui.wait(cls.NEXT_EP,10)
            ui.click(cls.NEXT_EP)
        except Exception:
            logger.debug("普通点击不可点")

    @classmethod
    def close_popup(cls, ui: "Ui") -> bool:
        # ① JS 负责找（可见过滤这套 JS 擅长的），找到就贴标签
        marked = ui.js(
            "var btn = [...document.querySelectorAll('.el-dialog__footer .btn')]"
            ".filter(e => e.offsetWidth > 0 || e.offsetHeight > 0).pop();"
            "if (!btn) return null;"
            "btn.setAttribute('data-zhs-click', '1');"
            "return 'marked';"
        )
        if marked is None:
            logger.info("没有可见的结果窗需要关闭")
            return False
        # ② selenium 负责点（真人式点击 + 被拦截会报错）
        try:
            ui.click('[data-zhs-click="1"]')
            logger.info("弹窗已关闭")
            return True
        finally:
            # ③ 无论点没点成，撕标签（标签是临时的，不能留在页面上）
            ui.js("var b = document.querySelector('[data-zhs-click]');"
                  "if (b) b.removeAttribute('data-zhs-click');")

    @classmethod
    def finished(cls, ui: "Ui") -> bool:
        return ui.exists(cls.FINISHED)


def run_course(ui: "Ui", poll: float = 0.5, max_idle: float = 600.0) -> None:
    """刷课状态机：每 poll 秒看一眼页面，四分支各司其职。

    ① 防作弊/验证  → 截图留证，立即停（自动化处理验证 = 高风险，交给人）
    ② 弹题         → 作答，继续
    ③ 视频暂停了   → JS 恢复，继续
    ④ 播完了       → 结束
    兜底：max_idle 秒内既没弹题也没播完也没暂停可恢复 → 判定卡死，报错退出。
    """
    from settings import ROOT  # 局部导入，避免页面层顶层依赖配置

    logger.info("开始刷课（每 %.1f 秒轮询一次）", poll)
    idle = 0.0
    ticks = 0
    while True:
        # ① 防作弊
        if CoursePage.has_verify(ui):
            shot = ROOT / "logs" / f"verify-{datetime.now():%Y%m%d-%H%M%S}.png"
            ui.screenshot(str(shot))
            raise AutomationError("检测到验证/防作弊弹层，需要人工处理（截图见 logs/）")

        # ② 弹题
        if CoursePage.has_popup(ui):
            CoursePage.answer_popup(ui)
            sleep(5)
            CoursePage.close_popup(ui)
            idle = 0.0

        if CoursePage.is_ended(ui):
            ui.hover("video")
            sleep(0.5)
            CoursePage.play_next(ui)
            idle = 0.0

        # ③ 暂停恢复
        if CoursePage.is_paused(ui):
            CoursePage.resume(ui)
            idle = 0.0

        # ④ 播完
        if CoursePage.finished(ui):
            logger.info("检测到播完标识，本课程结束 ✔")
            return

        time.sleep(poll)
        idle += poll
        ticks += 1
        if ticks % 120 == 0:  # 大约每分钟报一次平安
            logger.info("进行中……（%ds 无事件）当前页：%s", int(idle), ui.url())
        if idle >= max_idle:
            raise AutomationError(
                f"{max_idle:.0f} 秒无任何进展（没弹题/没暂停/没播完），判定卡死。"
                "多半是选择器过期，看 logs/ 排错指南校对 pages.py"
            )
