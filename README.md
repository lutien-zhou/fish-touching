# fish-touching 🐟

> 一个伪装成「日志监控」的终端摸鱼框架。界面看起来是一片滚动的构建日志，实际是在聊天。老板走过来，按一下 `Esc`，整屏立刻变成假日志。

```
15:33:27 [INFO ] worker  recv  在吗
15:33:29 [DEBUG] worker  push  在的
15:33:40 [INFO ] worker  recv  [图片#1] http://127.0.0.1:54xxx/i/1
```

聊天后端是**可插拔**的（provider）。目前内置**微博私信**，未来可扩展 Telegram、QQ、邮件等——核心的伪装界面 / 老板键 / 图片预览 / 输入编辑都是通用的，加新后端只需写一个 provider。

## 安装

需要 Python 3.8+。核心**零第三方依赖**。

```bash
git clone https://github.com/lutien-zhou/fish-touching.git
cd fish-touching

pip install qrcode        # 可选：让登录二维码直接显示在终端（否则会弹出二维码图片）
```

> 建议在一个**普通终端窗口**里跑（macOS 终端 / iTerm2 都行），窗口别太小（≥ 80×24）。

## 快速开始

```bash
cd fish-touching
python3 -m fishtouching
```

**首次运行**会引导你走三步：

1. **扫码登录** —— 屏幕出现二维码（或弹出二维码图片），用手机微博 App 扫一扫并确认。
   登录凭证会保存在 `~/.fish-touching/`，以后不用重复登录。
2. **选择聊天对象** —— 终端列出你的会话，输入序号回车。
3. **进入界面** —— 看起来是一片滚动日志，其实就是聊天窗口了。

之后再运行就直接进入上次的会话。

## 使用

进入界面后：

| 操作 | 说明 |
|------|------|
| 输入文字 + 回车 | 发送消息 |
| `/img <路径>` | 发送本地图片，如 `/img ~/Desktop/a.png` |
| `/v` | 发送剪贴板里的图片（macOS；先截图/复制图片再输入 `/v`） |
| `/o [N]` | 浏览器内联预览图片（`/o` = 最近一张，`/o 2` = 第 2 张） |
| `/switch` | 重新选择聊天对象 |
| `Esc` | **老板键**：整屏切成滚动假日志，再按一次切回 |
| `← / →` `Home` `End` | 输入行光标移动，可在中间插入/删除 |
| `Ctrl-C` | 退出 |

收到的消息显示为 `recv`，自己发的为 `push`，图片显示成 `[图片#N] http://127.0.0.1:.../i/N`，
**Cmd 点击**该链接即可在浏览器内联预览（不会下载）。

## 常见问题

- **二维码没显示，只弹出图片？** 装一下 `pip install qrcode` 就能直接在终端显示。
- **提示"没有会话"？** 说明该账号当前没有私信会话，先在微博 App/网页里跟某人聊一句再回来。
- **过了一阵提示凭证过期 / 拉不到消息？** 微博登录态有有效期。退出后重新 `python3 -m fishtouching`，
  检测到失效会自动重新拉起扫码登录。
- **图片点击后是下载而不是预览？** 正常情况下本工具自带的本地代理会让浏览器内联预览；
  若仍下载，确认你点的是 `http://127.0.0.1:...` 那个链接而非别处。
- **配置存哪？** 全部在 `~/.fish-touching/`，删掉该目录即可重置（需重新登录）。

## 架构

```
fishtouching/
├── app.py          核心 TUI 引擎：伪装界面 / 老板键 / 输入 / 命令 / 启动流程
├── provider.py     Provider 接口（抽象基类）—— core 只跟它打交道
├── registry.py     provider 注册表（@register 自动登记）
├── models.py       通用数据模型：Message / Conversation
├── disguise.py     伪装主题（可扩展：buildlog / 未来更多）
├── proxy.py        本地图片预览代理（仅监听 127.0.0.1）
├── config.py       配置/凭证存取（~/.fish-touching/，按 provider 隔离）
└── providers/
    └── weibo/      微博 provider（api / 扫码登录 / 接口实现）
```

数据流：`core 轮询 → provider.fetch() 返回 Message 列表 → core 去重/渲染`；
发送：`core → provider.send_text/send_image`；
图片预览：`浏览器 → 本地代理 → provider.resolve_image(ref)`。

## 扩展：新增一个聊天后端

写一个 `Provider` 子类并 `@register` 即可，core 会自动接管界面、老板键、图片预览等：

```python
from fishtouching.provider import Provider
from fishtouching.registry import register
from fishtouching.models import Message, Conversation

@register
class MyProvider(Provider):
    name = "myim"
    display_name = "My IM"
    can_send_image = False

    def is_authenticated(self): ...
    def login(self): ...                       # 交互式登录（进入 TUI 前）
    def list_conversations(self): ...          # -> [Conversation(...)]
    def set_conversation(self, conv_id): ...
    def fetch(self): ...                        # -> [Message(...)]，core 自动去重
    def send_text(self, text): ...
    # 可选：send_image / resolve_image
```

再在 `fishtouching/providers/__init__.py` 里 `import` 它。多个 provider 时启动会让你选。

伪装主题同理：继承 `disguise.Disguise`，用 `@register_theme("名字")` 注册。

## 平台支持

- **macOS**：全部功能
- **Linux**：基本可用；剪贴板发图 `/v` 与自动开浏览器依赖系统命令，可能需适配（欢迎 PR）
- **Windows**：未测试

## 免责声明

本项目仅供学习与个人使用。请遵守相关平台的用户协议与法律法规，风险自负。作者不对使用本工具产生的任何后果负责。摸鱼有度，工作要紧 🐟。

## License

MIT
