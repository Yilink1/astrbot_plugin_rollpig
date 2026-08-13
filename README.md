<div align="center">

![astrbot_plugin_rollpig](https://raw.githubusercontent.com/MegSopern/astrbot_plugin_rollpig/main/logo.png)

# astrbot_plugin_rollpig
_✨ [astrbot](https://github.com/AstrBotDevs/AstrBot) 今日小猪 ✨_ 

[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-3.4%2B-orange.svg)](https://github.com/Soulter/AstrBot)
[![GitHub](https://img.shields.io/badge/作者-MegSopern-pink)](https://github.com/MegSopern)
![动态访问量](https://count.kjchmc.cn/get/@astrbot_plugin_rollpig?theme=gelbooru)

</div>

## 🌟 项目介绍
每日用户可随机抽取专属“今日小猪”，并生成配图展示名称、描述和性格。无需繁琐配置，支持自定义猪猪库和素材。自动缓存结果，每日刷新，避免重复。适合群聊互动或签到，增添聊天趣味。
## 📦 安装：

```bash
# 克隆仓库到插件目录
cd /AstrBot/data/plugins
git clone https://github.com/MegSopern/astrbot_plugin_rollpig

# 控制台重启AstrBot
```

## 🐷 使用 🐷

**今日小猪** - 抽取今天属于你的小猪类型 🐖

- 每个用户每天只能抽取一次 🐽  
- 重复抽取不会改变结果 🐷  
- 每天 0 点自动重置 🐖

**我的猪圈** - 查看已收集小猪的图鉴 📦

- 展示已收集数量、收集率、本命猪（等级最高/抓到次数最多的猪）
- 每抓到一只没收集过的新猪即收录，重复抓到同一只则等级+1
- 图鉴以网格展示，已解锁的猪显示头像+名称+等级，未解锁的显示锁头占位

---

## ⚙️ 插件设置

在 AstrBot 管理面板的插件配置页可自定义以下选项：

| 配置项 | 说明 |
| --- | --- |
| `roll_pig_commands` | 抽取今日小猪的触发词列表，可自由增删（默认：今日小猪 / 抽小猪 / 我的小猪 / rollpig） |
| `roll_pig_need_at` | 是否需要艾特机器人才能触发抽取（默认关闭，群聊直接发指令即可） |
| `pigpen_commands` | 查看猪圈图鉴的触发词列表，可自由增删（默认：我的猪圈 / 猪圈图鉴 / 猪猪图鉴 / pigpen） |
| `pigpen_need_at` | 是否需要艾特机器人才能查看图鉴（默认关闭） |
| `at_view_pig` | 是否允许艾特他人查看/代查对方的今日小猪或猪圈图鉴 |

触发词采用完全匹配（消息内容需与列表中某一项完全相同），若清空某个功能的触发词列表，则该功能不会被任何消息触发。

---

## 🐖 新增小猪 🐖

插件资源路径：

```
astrbot_plugin_rollpig/resource
```

- **pig.json** 小猪信息，例如：

```json
[
    {
        "id": "pig",
        "name": "猪",
        "description": "普通小猪",
        "analysis": "你性格温和，喜欢简单的生活，容易满足。在别人眼中可能有些慵懒，但你知道如何享受生活的美好。"
    }
]
```

- **image/** 小猪图片  
    - 图片命名需和信息中的 `id` 一致  
    - 支持图片类型：`["png", "jpg", "jpeg", "webp", "gif"]`

---

### 🐽 目录结构示例 🐽

```
astrbot_plugin_rollpig/
├─ main.py               # 插件主逻辑（AstrBot插件核心）
└─ resource/
    ├─ pig.json          # 小猪信息数据
    └─ image/
        └─ pig.png       # 小猪图片（与id对应）
```

---

## 🐖 注意事项 🐖

- 新增小猪时只需在 `pig.json` 添加对象，并将对应图片放到 `image/` 文件夹即可 🐷  
- 图片自动按 id 匹配，无需在 JSON 中写图片后缀 🐖  

## 🎖️ 致谢
- 本插件基于[nonebot-plugin-rollpig](https://github.com/Bearlele/nonebot-plugin-rollpig)的核心逻辑进行改造。
- 欢迎前往原仓库为作者的辛苦付出点亮 ⭐ Star 支持！

## 📜 许可证

本项目采用 [MIT 许可证](LICENSE) 开源，详情请查阅许可证文件

![Star History Chart](https://api.star-history.com/svg?repos=MegSopern/astrbot_plugin_rollpig&type)
