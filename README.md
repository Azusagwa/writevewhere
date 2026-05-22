# Writevewhere

Writevewhere 是一个基于 Python 和 PySide6 的轻量级屏幕标注工具。它会在桌面上显示一个悬浮控制球，并通过透明叠加层实现画笔、图形、箭头和橡皮擦等批注功能，适合演示、讲解、录屏或临时标记屏幕内容。

## 功能特性

- 悬浮球菜单：支持画笔、矩形、椭圆、箭头、橡皮擦、颜色、粗细、清空和退出。
- 点击穿透模式：关闭绘制后，鼠标事件可以继续传递到底层应用。
- 独立粗细设置：每个绘制模式可以单独配置线条粗细，互不影响。
- 设置持久化：粗细配置会保存到本机设置中，重新运行后自动恢复。
- Windows 原生支持：在 Windows 上使用扩展窗口样式实现更稳定的点击穿透和置顶行为。
- 自动避让屏幕边缘：悬浮球拖动时会限制在可见屏幕范围内。

## 运行方式

先安装依赖：

```powershell
py -m pip install -r requirements.txt
```

从源码运行：

```powershell
py app.py
```

也可以用模块方式启动：

```powershell
py -m writevewhere
```

也可以从exe文件快速运行

Writevewhere.exe

## 基本操作

- 点击悬浮球展开或收起二级菜单。
- 点击画笔、矩形、椭圆、箭头或橡皮擦切换对应模式。
- 再次点击当前模式按钮会回到穿透模式。
- 拖动悬浮球可以移动控制位置。
- 在绘制模式下，菜单空白区域会转发给绘制层，按钮和滑条仍优先响应 UI 操作。

## 测试

```powershell
py -m pytest tests -q
```

## 项目结构

- `app.py`：本地运行入口。
- `writevewhere/app.py`：应用启动逻辑。
- `writevewhere/windows/control_window.py`：悬浮控制窗口。
- `writevewhere/windows/overlay_window.py`：透明绘制叠加层。
- `writevewhere/core/strokes.py`：笔画模型、图形模型和命中测试。
- `writevewhere/system/`：点击穿透、窗口置顶等系统相关辅助逻辑。
- `tests/`：绘制行为、窗口事件路由和交互回归测试。

## 许可

本项目基于 ScreenPen 的代码基础改造而来，并继续遵循 GPL-3.0 许可证。原始许可证文件保留在仓库中。
