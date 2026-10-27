"""Ui 协议 + SeleniumUi 真实现。

业务代码（pages.py / main.py）只认识 Ui 这份"合同"——11 个动词，
不知道也不 import selenium。好处：换自动化工具只改本文件；
写测试时塞一个同样实现 11 个方法的 FakeUi，业务代码一行不改。

全项目只有本文件和 browser.py 允许 import selenium。
"""

from __future__ import annotations

import logging
import time
from typing import Protocol

from selenium.webdriver.common.by import By

from errors import UiTimeout

logger = logging.getLogger(__name__)


class Ui(Protocol):
    """合同：任何实现这 11 个方法的东西都是一个合法的 Ui。"""

    def open(self, url: str) -> None: ...
    def click(self, selector: str) -> None: ...
    def type(self, selector: str, text: str) -> None: ...
    def text(self, selector: str) -> str: ...
    def attr(self, selector: str, name: str) -> str | None: ...
    def exists(self, selector: str) -> bool: ...
    def wait(self, selector: str, timeout: float) -> None: ...
    def wait_gone(self, selector: str, timeout: float) -> None: ...
    def url(self) -> str: ...
    def js(self, script: str): ...
    def screenshot(self, path: str) -> None: ...
    def hover(self,selector: str) -> None: ...


class SeleniumUi:
    """真实现：把 11 个动词翻译成 selenium 调用。

    智慧树的播放器可能藏在 <iframe> 里，所以定位元素时会自动
    "主文档 → 逐个 iframe" 扫一遍，找到谁就切进谁再操作。
    （selenium 的规矩：切出 iframe 后，里面拿到的元素引用就作废了，
    所以每次操作都是"切进去 → 操作 → 切回主文档"一气呵成。）
    """

    def __init__(self, driver, find_timeout: float = 10.0, poll: float = 0.5):
        self.driver = driver
        self.find_timeout = find_timeout
        self.poll = poll

    # ------------------------------------------------------------ 内部工具

    def _contexts(self):
        """依次产出：主文档(None) + 每个一层 iframe。"""
        yield None
        for frame in self.driver.find_elements(By.TAG_NAME, "iframe"):
            yield frame

    def _switch_to_owner(self, selector: str) -> bool:
        """切到 selector 所在的文档（主文档或某 iframe），找到返回 True 并停在那。"""
        for ctx in self._contexts():
            self.driver.switch_to.frame(ctx) if ctx else self.driver.switch_to.default_content()
            if self.driver.find_elements(By.CSS_SELECTOR, selector):
                return True
        self.driver.switch_to.default_content()
        return False

    def _wait_owner(self, selector: str, timeout: float) -> None:
        """轮询直到 selector 出现（在哪个文档都行），超时抛 UiTimeout。"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._switch_to_owner(selector):
                return
            time.sleep(self.poll)
        raise UiTimeout(f"等待元素超时（{timeout}s）：{selector}")

    # ------------------------------------------------------------ 11 个动词

    def open(self, url: str) -> None:
        logger.debug("打开页面：%s", url)
        self.driver.get(url)

    def click(self, selector: str) -> None:
        self._wait_owner(selector, self.find_timeout)
        self.driver.find_element(By.CSS_SELECTOR, selector).click()
        self.driver.switch_to.default_content()

    def type(self, selector: str, text: str) -> None:
        self._wait_owner(selector, self.find_timeout)
        el = self.driver.find_element(By.CSS_SELECTOR, selector)
        el.clear()
        el.send_keys(text)
        self.driver.switch_to.default_content()

    def text(self, selector: str) -> str:
        self._wait_owner(selector, self.find_timeout)
        value = self.driver.find_element(By.CSS_SELECTOR, selector).text
        self.driver.switch_to.default_content()
        return value

    def attr(self, selector: str, name: str) -> str | None:
        self._wait_owner(selector, self.find_timeout)
        value = self.driver.find_element(By.CSS_SELECTOR, selector).get_attribute(name)
        self.driver.switch_to.default_content()
        return value

    def exists(self, selector: str) -> bool:
        found = self._switch_to_owner(selector)
        self.driver.switch_to.default_content()
        return found

    def wait(self, selector: str, timeout: float) -> None:
        self._wait_owner(selector, timeout)

    def wait_gone(self, selector: str, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.exists(selector):
                return
            time.sleep(self.poll)
        raise UiTimeout(f"等待元素消失超时（{timeout}s）：{selector}")

    def url(self) -> str:
        return self.driver.current_url

    def js(self, script: str):
        """在主文档和各 iframe 里逐个执行，返回第一个非 None 的结果。"""
        for ctx in self._contexts():
            try:
                self.driver.switch_to.frame(ctx) if ctx else self.driver.switch_to.default_content()
                result = self.driver.execute_script(script)
            except Exception:
                self.driver.switch_to.default_content()
                continue
            if result is not None:
                self.driver.switch_to.default_content()
                return result
        self.driver.switch_to.default_content()
        return None

    def screenshot(self, path: str) -> None:
        self.driver.save_screenshot(path)
        logger.info("已截图：%s", path)

    def hover(self, selector: str) -> None:  # 实现里加这个方法
        """鼠标悬停到元素中心（触发 :hover，让控制条等现身）。"""
        self._wait_owner(selector, self.find_timeout)
        from selenium.webdriver.common.action_chains import ActionChains
        el = self.driver.find_element(By.CSS_SELECTOR, selector)
        ActionChains(self.driver).move_to_element(el).perform()
        self.driver.switch_to.default_content()