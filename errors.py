"""异常分类：三个空标签，唯一作用是让 except 能精确抓。

- ConfigError     配置错了 → 直接死，不重试（改 yaml 再跑）
- UiTimeout       等元素/等登录超时 → 可以重试或人工介入
- AutomationError 运行期兜底（验证码、长时间无进展等）
"""


class ConfigError(Exception):
    pass


class UiTimeout(Exception):
    pass


class AutomationError(Exception):
    pass
