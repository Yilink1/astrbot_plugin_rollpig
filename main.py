import asyncio
import datetime
import json
import random
import tempfile
from pathlib import Path

import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.core import AstrBotConfig
from astrbot.core.message.components import At

# 修复导入冲突：PIL的Image重命名为PILImage
from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont


class RollPigPlugin(Star):
    CANVAS_WIDTH = 800  # 画布宽度
    CANVAS_HEIGHT = 800  # 画布高度
    AVATAR_SIZE = 280  # 头像大小
    SPACING_AVATAR_NAME = 20  # 头像与名称间距
    SPACING_NAME_DESC = 25  # 名称与描述间距
    SPACING_DESC_ANALYSIS = 30  # 描述与解析间距
    DESC_FONT_SIZE = 32  # 描述字体大小
    ANALYSIS_FONT_SIZE = 28  # 解析字体大小
    ANALYSIS_LINE_HEIGHT_FACTOR = 1.6  # 解析行高因子
    ANALYSIS_WIDTH_RATIO = 0.85  # 解析宽度比例
    NAME_FONT_SIZE = 66  # 名称字体大小

    # 猪圈图鉴相关常量
    PEN_COLS = 18  # 图鉴每行格子数
    PEN_CELL_SIZE = 120  # 图鉴单元格大小（正方形）
    PEN_CELL_GAP = 6  # 单元格间距
    PEN_CELL_ICON_SIZE = 76  # 单元格内头像大小
    PEN_MARGIN = 40  # 画布边距
    PEN_HEADER_HEIGHT = 140  # 顶部标题区域高度

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 配置项
        self.admins_id: list[str] = context.get_config().get("admins_id", [])
        self.at_view_pig: bool = self.config.get("at_view_pig", False)
        self.roll_pig_need_at: bool = self.config.get("roll_pig_need_at", False)
        self.pigpen_need_at: bool = self.config.get("pigpen_need_at", False)

        # 初始化路径
        self.plugin_dir = Path(__file__).parent
        self.plugin_data_dir = StarTools.get_data_dir("astrbot_plugin_rollpig")
        self.res_dir = self.plugin_dir / "resource"
        self.font_dir = self.res_dir / "font"  # 插件内字体目录（跨平台优先）
        self.piginfo_path = self.res_dir / "pig.json"
        self.image_dir = self.res_dir / "image"

        # 创建必要目录（自动创建font文件夹）
        self.plugin_data_dir.mkdir(parents=True, exist_ok=True)
        self.font_dir.mkdir(parents=True, exist_ok=True)

        # 初始化数据
        self.pig_list = self.load_json(self.piginfo_path, [])
        if not self.pig_list:
            logger.error("小猪信息为空或不存在，请检查资源文件！")
        self.today_path = self.plugin_data_dir / "rollpig_today.json"

        # 猪圈图鉴：每个用户一份收集记录
        self.pigpen_dir = self.plugin_data_dir / "pigpen"
        self.pigpen_dir.mkdir(parents=True, exist_ok=True)
        self.pig_id_order = [p.get("id", "") for p in self.pig_list]
        self.pig_by_id = {p.get("id", ""): p for p in self.pig_list}

        # 初始化字体（优先插件内自定义字体，跨平台兼容）
        self.font_regular = self._init_regular_font()  # 常规字体（描述/解析）
        self.font_bold = self._init_bold_font()  # 加粗字体（名称）

    def _load_font(
        self, font_candidates: list[str | Path], size: int, purpose: str
    ) -> ImageFont.FreeTypeFont | None:
        """
        通用字体加载器，按候选顺序加载可用字体\n
        :param font_candidates: 字体路径候选列表
        :param size: 字体大小
        :param purpose: 字体用途描述
        :return: 加载的字体对象，失败则返回默认字体
        """
        for font_path in font_candidates:
            if Path(font_path).exists():
                try:
                    return ImageFont.truetype(str(font_path), size)
                except Exception as e:
                    logger.warning(f"加载{purpose}字体{font_path}失败：{e}")
                    continue
        logger.warning(f"未找到{purpose}字体，使用默认字体")
        return ImageFont.load_default()

    def _init_regular_font(self) -> ImageFont.FreeTypeFont | None:
        """初始化常规字体（可爱字体，用于描述/解析）"""
        font_paths = [
            self.font_dir / "可爱字体.ttf",
            self.font_dir / "SourceHanSansCN-Regular.otf",
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/PingFang.ttc",
        ]
        return self._load_font(font_paths, self.DESC_FONT_SIZE, "常规")

    def _init_bold_font(self) -> ImageFont.FreeTypeFont | None:
        """初始化加粗字体（荆南麦圆体，用于名称）"""
        font_paths = [
            self.font_dir / "荆南麦圆体.otf",
            self.font_dir / "SourceHanSansCN-Bold.otf",
            "C:/Windows/Fonts/msyhbd.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/PingFang.ttc",
        ]
        return self._load_font(font_paths, self.NAME_FONT_SIZE, "加粗")

    def _get_text_size(
        self, text: str, font: ImageFont.FreeTypeFont
    ) -> tuple[int, int]:
        """
        兼容PIL不同版本的文字尺寸计算\n
        :param text: 文字内容
        :param font: 字体对象
        :return: 文字宽高元组
        """
        draw = ImageDraw.Draw(PILImage.new("RGB", (1, 1)))
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            return (bbox[2] - bbox[0], bbox[3] - bbox[1])
        except:
            return draw.textsize(text, font=font)

    def _draw_bold_text(
        self,
        draw: ImageDraw.ImageDraw,
        pos: tuple,
        text: str,
        font: ImageFont.FreeTypeFont,
        fill: tuple,
    ):
        """
        模拟文字加粗（兜底方案）\n
        :param draw: ImageDraw对象
        :param pos: 文字位置
        :param text: 文字内容
        :param font: 字体对象
        :param fill: 文字颜色
        """
        x, y = pos
        offsets = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        for ox, oy in offsets:
            draw.text((x + ox, y + oy), text, fill=fill, font=font)
        draw.text((x, y), text, fill=fill, font=font)

    def load_json(self, path: Path, default):
        """
        加载JSON文件\n
        :param path: 文件路径
        :param default: 默认值（文件不存在或解析失败时使用）
        :return: 解析后的数据对象
        """
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return default
        try:
            return json.loads(path.read_text("utf-8"))
        except json.JSONDecodeError:
            logger.error(f"JSON文件解析失败，重置为默认值：{path}")
            path.write_text(
                json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return default

    def save_json(self, path: Path, data):
        """
        保存JSON数据\n
        :param path: 文件路径
        :param data: 数据对象
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get_pigpen_path(self, user_id: str) -> Path:
        """
        获取指定用户的猪圈图鉴数据文件路径\n
        :param user_id: 用户ID
        :return: 数据文件路径
        """
        return self.pigpen_dir / f"{user_id}.json"

    def load_pigpen(self, user_id: str) -> dict:
        """
        加载用户的猪圈图鉴数据\n
        :param user_id: 用户ID
        :return: 图鉴数据字典，结构为 {"records": {pig_id: {"level": int}}}
        """
        path = self.get_pigpen_path(user_id)
        return self.load_json(path, {"records": {}})

    def save_pigpen(self, user_id: str, data: dict):
        """
        保存用户的猪圈图鉴数据\n
        :param user_id: 用户ID
        :param data: 图鉴数据字典
        """
        self.save_json(self.get_pigpen_path(user_id), data)

    def record_pig_capture(self, user_id: str, pig_data: dict) -> dict:
        """
        记录一次抽取结果到用户的猪圈图鉴：新猪则收录（等级1），已收录则等级+1\n
        :param user_id: 用户ID
        :param pig_data: 本次抽取到的小猪数据
        :return: 更新后的图鉴数据
        """
        pig_id = pig_data.get("id", "")
        pigpen = self.load_pigpen(user_id)
        records = pigpen.setdefault("records", {})
        if pig_id in records:
            records[pig_id]["level"] = records[pig_id].get("level", 1) + 1
        else:
            records[pig_id] = {"level": 1}
        self.save_pigpen(user_id, pigpen)
        return pigpen

    def get_pigpen_stats(self, pigpen: dict) -> dict:
        """
        计算图鉴统计信息：收集数、收集率、本命猪\n
        :param pigpen: 图鉴数据字典
        :return: 统计信息字典
        """
        records = pigpen.get("records", {})
        total = len(self.pig_id_order)
        collected = len(records)
        rate = (collected / total * 100) if total else 0.0

        favorite_id = None
        favorite_level = 0
        for pig_id, info in records.items():
            level = info.get("level", 1)
            if level > favorite_level:
                favorite_level = level
                favorite_id = pig_id

        return {
            "total": total,
            "collected": collected,
            "rate": rate,
            "favorite_id": favorite_id,
            "favorite_level": favorite_level,
        }

    def find_image_file(self, pig_id: str) -> Path | None:
        """
        查找对应ID的图片文件\n
        :param pig_id: 小猪ID
        :return: 图片文件路径，未找到返回None
        """
        exts = ["png", "jpg", "jpeg", "webp", "gif"]
        for ext in exts:
            file = self.image_dir / f"{pig_id}.{ext}"
            if file.exists():
                logger.debug(f"找到的小猪图片文件：{file.absolute()}")
                return file
        logger.warning(f"未找到小猪ID {pig_id} 对应的图片文件")
        return None

    def render_pig_image(self, pig_data: dict) -> Path | None:
        """
        整体居中渲染（垂直+水平双居中）\n
        :param pig_data: 小猪数据字典
        :return: 生成的图片临时文件路径，失败返回None
        """
        pig_id = pig_data.get("id", "")
        pig_name = pig_data.get("name", "未知小猪")
        pig_desc = pig_data.get("description", "无描述")
        pig_analysis = pig_data.get("analysis", "无解析")

        # 1. 画布基础配置
        canvas_width = self.CANVAS_WIDTH
        canvas_height = self.CANVAS_HEIGHT
        canvas = PILImage.new("RGB", (canvas_width, canvas_height), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        # 2. 预加载所有元素并计算尺寸（用于总高度计算）
        # 2.1 头像尺寸【核心修改：放大到280x280】
        avatar_w, avatar_h = self.AVATAR_SIZE, self.AVATAR_SIZE
        avatar = None
        avatar_path = self.find_image_file(pig_id)
        if avatar_path:
            try:
                avatar = PILImage.open(avatar_path)
                avatar.thumbnail((avatar_w, avatar_h))
                # 居中裁剪（保证正方形，适配新尺寸：280/2=140）
                if avatar.size != (avatar_w, avatar_h):
                    center_x = avatar.width // 2
                    center_y = avatar.height // 2
                    half = self.AVATAR_SIZE // 2
                    crop_box = (
                        center_x - half,
                        center_y - half,
                        center_x + half,
                        center_y + half,
                    )
                    avatar = avatar.crop(crop_box)
            except Exception as e:
                logger.error(f"加载小猪图片失败：{str(e)}")
                avatar = None

        # 2.2 名称尺寸
        name_font = self.font_bold
        name_w, name_h = self._get_text_size(pig_name, name_font)

        # 2.3 描述尺寸
        desc_font = self.font_regular.font_variant(
            size=self.DESC_FONT_SIZE
        )  # 匹配示例的描述字号
        desc_w, desc_h = self._get_text_size(pig_desc, desc_font)

        # 2.4 解析尺寸（自动换行后）
        analysis_font = self.font_regular.font_variant(size=self.ANALYSIS_FONT_SIZE)
        line_height = int(
            self.ANALYSIS_FONT_SIZE * self.ANALYSIS_LINE_HEIGHT_FACTOR
        )  # 匹配示例的行间距
        max_analysis_width = int(
            canvas_width * self.ANALYSIS_WIDTH_RATIO
        )  # 更宽的解析区域
        # 解析文字换行
        analysis_lines = []
        current_line = ""
        for char in pig_analysis:
            current_line += char
            line_w, _ = self._get_text_size(current_line, analysis_font)
            if line_w > max_analysis_width:
                analysis_lines.append(current_line[:-1])
                current_line = char
        if current_line:
            analysis_lines.append(current_line)
        # 计算解析总高度
        analysis_total_h = len(analysis_lines) * line_height

        # 3. 计算整体内容总高度（所有元素+间距）
        spacing_avatar_name = (
            self.SPACING_AVATAR_NAME
        )  # 头像放大后，间距从30调小到20，避免布局拥挤
        spacing_name_desc = self.SPACING_NAME_DESC  # 名称到描述的间距保持
        spacing_desc_analysis = self.SPACING_DESC_ANALYSIS  # 描述到解析的间距保持
        total_content_h = (
            avatar_h
            + spacing_avatar_name
            + name_h
            + spacing_name_desc
            + desc_h
            + spacing_desc_analysis
            + analysis_total_h
        )

        # 4. 计算垂直居中的起始Y坐标（核心：让整个内容块在画布中垂直居中）
        start_y = (canvas_height - total_content_h) // 2

        # 5. 绘制所有元素（基于起始Y坐标，保证整体居中）
        # 5.1 绘制头像（水平+垂直居中）
        avatar_x = (canvas_width - avatar_w) // 2
        avatar_y = start_y
        if avatar:
            canvas.paste(
                avatar,
                (avatar_x, avatar_y),
                mask=avatar if avatar.mode == "RGBA" else None,
            )
        else:
            # 头像加载失败时的提示（适配新尺寸）
            error_font = self.font_regular.font_variant(size=24)
            error_text = "图片加载失败"
            error_w, error_h = self._get_text_size(error_text, error_font)
            error_x = (canvas_width - error_w) // 2
            draw.text(
                (error_x, avatar_y + 120),  # 从90调到120，适配280高度的头像居中
                error_text,
                fill=(255, 0, 0),
                font=error_font,
            )

        # 5.2 绘制名称（水平居中）
        name_y = avatar_y + avatar_h + spacing_avatar_name
        name_x = (canvas_width - name_w) // 2
        self._draw_bold_text(draw, (name_x, name_y), pig_name, name_font, (0, 0, 0))

        # 5.3 绘制描述（水平居中）
        desc_y = name_y + name_h + spacing_name_desc
        desc_x = (canvas_width - desc_w) // 2
        draw.text((desc_x, desc_y), pig_desc, fill=(85, 85, 85), font=desc_font)

        # 5.4 绘制解析（逐行水平居中）
        analysis_y = desc_y + desc_h + spacing_desc_analysis
        for line in analysis_lines:
            line_w, line_h = self._get_text_size(line, analysis_font)
            line_x = (canvas_width - line_w) // 2
            draw.text((line_x, analysis_y), line, fill=(51, 51, 51), font=analysis_font)
            analysis_y += line_height

        # 6. 保存临时文件
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                canvas.save(tmp_path, format="PNG", quality=95)
            logger.debug(f"合成图片成功，临时文件路径：{tmp_path.absolute()}")
            if not tmp_path.exists():
                logger.error(f"临时文件创建失败：{tmp_path}")
                return None
            return tmp_path
        except Exception as e:
            logger.error(f"合成图片失败：{str(e)}")
            return None

    def render_pigpen_image(self, pigpen: dict) -> Path | None:
        """
        渲染用户的猪圈图鉴：网格展示已解锁/未解锁的小猪\n
        :param pigpen: 图鉴数据字典
        :return: 生成的图片临时文件路径，失败返回None
        """
        records = pigpen.get("records", {})
        stats = self.get_pigpen_stats(pigpen)
        total = stats["total"]

        cols = self.PEN_COLS
        rows = (total + cols - 1) // cols if total else 1
        cell = self.PEN_CELL_SIZE
        gap = self.PEN_CELL_GAP
        margin = self.PEN_MARGIN
        header_h = self.PEN_HEADER_HEIGHT

        grid_w = cols * cell + (cols - 1) * gap
        grid_h = rows * cell + (rows - 1) * gap
        canvas_w = grid_w + margin * 2
        canvas_h = header_h + grid_h + margin * 2

        canvas = PILImage.new("RGB", (canvas_w, canvas_h), (232, 240, 253))
        draw = ImageDraw.Draw(canvas)

        title_font = self.font_bold.font_variant(size=44)
        stat_font = self.font_regular.font_variant(size=26)
        cell_name_font = self.font_regular.font_variant(size=16)
        lock_font = self.font_regular.font_variant(size=16)

        # 标题
        draw.text((margin, 24), "猪猪图鉴", fill=(60, 40, 40), font=title_font)

        # 右上角统计信息
        stat_text = f"已收集 {stats['collected']} / {total} | {stats['rate']:.2f}%"
        stat_w, _ = self._get_text_size(stat_text, stat_font)
        draw.text(
            (canvas_w - margin - stat_w, 40),
            stat_text,
            fill=(60, 60, 60),
            font=stat_font,
        )

        # 网格
        grid_top = header_h
        for idx, pig_id in enumerate(self.pig_id_order):
            row, col = divmod(idx, cols)
            x = margin + col * (cell + gap)
            y = grid_top + row * (cell + gap)

            info = records.get(pig_id)
            unlocked = info is not None

            if unlocked:
                draw.rounded_rectangle(
                    [x, y, x + cell, y + cell],
                    radius=10,
                    fill=(255, 255, 255),
                    outline=(200, 210, 230),
                    width=1,
                )
                icon_path = self.find_image_file(pig_id)
                icon_size = self.PEN_CELL_ICON_SIZE
                if icon_path:
                    try:
                        icon = PILImage.open(icon_path).convert("RGBA")
                        icon.thumbnail((icon_size, icon_size))
                        icon_x = x + (cell - icon.width) // 2
                        icon_y = y + 8
                        canvas.paste(icon, (icon_x, icon_y), mask=icon)
                    except Exception as e:
                        logger.warning(f"图鉴渲染加载图片失败 {pig_id}：{e}")

                pig_info = self.pig_by_id.get(pig_id, {})
                pig_name = pig_info.get("name", pig_id)
                level = info.get("level", 1)

                # 等级角标
                lv_text = f"Lv.{level}"
                lv_w, lv_h = self._get_text_size(lv_text, lock_font)
                draw.rounded_rectangle(
                    [x + cell - lv_w - 12, y + 4, x + cell - 2, y + lv_h + 8],
                    radius=6,
                    fill=(120, 190, 90),
                )
                draw.text(
                    (x + cell - lv_w - 8, y + 5),
                    lv_text,
                    fill=(255, 255, 255),
                    font=lock_font,
                )

                # 名称（超长则截断）
                name_display = pig_name
                name_w, _ = self._get_text_size(name_display, cell_name_font)
                while name_w > cell - 8 and len(name_display) > 1:
                    name_display = name_display[:-1]
                    name_w, _ = self._get_text_size(
                        name_display + "…", cell_name_font
                    )
                if name_display != pig_name:
                    name_display += "…"
                name_x = x + (cell - name_w) // 2
                draw.text(
                    (name_x, y + cell - 24),
                    name_display,
                    fill=(70, 70, 70),
                    font=cell_name_font,
                )
            else:
                draw.rounded_rectangle(
                    [x, y, x + cell, y + cell],
                    radius=10,
                    fill=(238, 238, 240),
                    outline=(215, 215, 218),
                    width=1,
                )
                lock_text = "🔒"
                lw, lh = self._get_text_size(lock_text, cell_name_font)
                draw.text(
                    (x + (cell - lw) // 2, y + cell // 2 - 26),
                    lock_text,
                    fill=(170, 170, 175),
                    font=cell_name_font,
                )
                tip_text = "未解锁"
                tw, _ = self._get_text_size(tip_text, cell_name_font)
                draw.text(
                    (x + (cell - tw) // 2, y + cell - 24),
                    tip_text,
                    fill=(160, 160, 165),
                    font=cell_name_font,
                )

        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                canvas.save(tmp_path, format="PNG", quality=95)
            if not tmp_path.exists():
                logger.error(f"图鉴临时文件创建失败：{tmp_path}")
                return None
            return tmp_path
        except Exception as e:
            logger.error(f"合成图鉴图片失败：{str(e)}")
            return None

    def get_at_ids(self, event: AstrMessageEvent) -> list[str]:
        """
        获取QQ被at用户的id列表
        :param event: Aiocqhttp消息事件对象
        :return: 被at用户的id列表（排除自己）
        """
        return [
            str(seg.qq)
            for seg in event.get_messages()
            if (isinstance(seg, At) and str(seg.qq) != event.get_self_id())  # 排除自己
        ]

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """统一消息入口：按配置中的自定义触发词分发到对应功能"""
        raw_text = event.message_str.strip()
        if not raw_text:
            return

        # 去掉艾特消息中可能残留的空白后，取第一段作为指令主体
        command_text = raw_text.split()[0] if raw_text.split() else raw_text

        roll_pig_commands = self.config.get(
            "roll_pig_commands", ["今日小猪", "抽小猪", "我的小猪", "rollpig"]
        )
        pigpen_commands = self.config.get(
            "pigpen_commands", ["我的猪圈", "猪圈图鉴", "猪猪图鉴", "pigpen"]
        )

        if command_text in roll_pig_commands:
            if self.roll_pig_need_at and not event.is_at_or_wake_command:
                return
            await self.roll_pig(event)
            event.stop_event()
            return

        if command_text in pigpen_commands:
            if self.pigpen_need_at and not event.is_at_or_wake_command:
                return
            await self.view_pigpen(event)
            event.stop_event()
            return

    async def roll_pig(self, event: AstrMessageEvent):
        """抽取今日小猪"""
        today_str = datetime.date.today().isoformat()
        user_id = event.get_sender_id()
        if self.at_view_pig:
            parts = event.message_str.strip().split()
            at_ids = self.get_at_ids(event)
            if len(at_ids) > 1:
                await event.send(event.plain_result("一次只能抽取一个小猪哦！"))
                return
            if len(parts) >= 2:
                if at_ids[0] not in self.admins_id:
                    user_id = at_ids[0]
                else:
                    await event.send(event.plain_result("你这只小猪，不许对主人不敬！"))
                    return
        today_cache = self.load_json(self.today_path, {"date": "", "records": {}})
        if today_cache.get("date") != today_str:
            today_cache = {"date": today_str, "records": {}}
        user_records = today_cache["records"]

        if user_id in user_records:
            pig = user_records[user_id]
            await self.send_rendered_pig(event, pig, user_id)
            return

        if not self.pig_list:
            await event.send(event.plain_result("小猪信息加载失败，请检查后台报错！"))
            return

        pig = random.choice(self.pig_list)
        user_records[user_id] = pig
        self.save_json(self.today_path, today_cache)

        # 首次抽取才计入猪圈图鉴（新猪收录，老猪等级+1）
        self.record_pig_capture(user_id, pig)

        await self.send_rendered_pig(event, pig, user_id)

    async def view_pigpen(self, event: AstrMessageEvent):
        """查看我的猪圈收集图鉴"""
        user_id = event.get_sender_id()
        if self.at_view_pig:
            at_ids = self.get_at_ids(event)
            if len(at_ids) > 1:
                await event.send(event.plain_result("一次只能查看一个人的猪圈哦！"))
                return
            if at_ids:
                user_id = at_ids[0]

        if not self.pig_list:
            await event.send(event.plain_result("小猪信息加载失败，请检查后台报错！"))
            return

        pigpen = self.load_pigpen(user_id)
        stats = self.get_pigpen_stats(pigpen)

        if stats["favorite_id"]:
            favorite_pig = self.pig_by_id.get(stats["favorite_id"], {})
            favorite_name = favorite_pig.get("name", stats["favorite_id"])
            favorite_line = (
                f"🐷 本命猪：【{favorite_name}】Lv.{stats['favorite_level']}"
                f"（抓到过{stats['favorite_level']}次）"
            )
        else:
            favorite_line = "🐷 本命猪：暂无，快去抽一只今日小猪吧～"

        summary_text = (
            f"【猪圈图鉴】\n"
            f"📦 已收集：{stats['collected']} / {stats['total']}\n"
            f"⭐ 收集率：{stats['rate']:.2f}%\n"
            f"{favorite_line}"
        )

        img_path = await asyncio.to_thread(self.render_pigpen_image, pigpen)
        msg_chain = [Comp.Plain(summary_text)]
        if img_path and img_path.exists():
            try:
                await event.send(event.plain_result(summary_text))
                await event.send(event.image_result(str(img_path.absolute())))
                return
            except Exception as e:
                logger.error(f"发送猪圈图鉴失败：{str(e)}")
            finally:
                try:
                    img_path.unlink(missing_ok=True)
                except Exception as cleanup_err:
                    logger.warning(f"清理图鉴临时图片失败：{cleanup_err}")

        await event.send(event.chain_result(msg_chain))

    async def send_rendered_pig(
        self, event: AstrMessageEvent, pig_data: dict, user_id: str
    ):
        """合成并发送小猪图片"""
        # 使用线程池异步执行CPU密集型任务
        img_path = await asyncio.to_thread(self.render_pig_image, pig_data)
        if img_path and img_path.exists():
            try:
                chain = [Comp.Plain(". 这是你的今日小猪：")]
                group_id = event.get_group_id()
                if group_id:
                    chain.insert(0, Comp.At(qq=user_id))
                await event.send(event.chain_result(chain))
                await event.send(event.image_result(str(img_path.absolute())))
                logger.info("合成图片发送成功")
                return
            except Exception as e:
                logger.error(f"发送合成图片失败：{str(e)}")
            finally:
                try:
                    img_path.unlink(missing_ok=True)
                except Exception as cleanup_err:
                    logger.warning(f"清理临时图片失败：{cleanup_err}")

        await self.send_fallback_msg(event, pig_data)

    async def send_fallback_msg(self, event: AstrMessageEvent, pig_data: dict):
        """降级发送：原始图片 + 纯文本"""
        pig_name = pig_data.get("name", "未知小猪")
        pig_desc = pig_data.get("description", "无描述")
        pig_analysis = pig_data.get("analysis", "无解析")
        pig_id = pig_data.get("id", "")

        text_msg = (
            f"【今日小猪】\n名称：{pig_name}\n描述：{pig_desc}\n解析：{pig_analysis}"
        )
        msg_chain = []

        avatar_path = self.find_image_file(pig_id)
        if avatar_path and avatar_path.exists():
            try:
                msg_chain.append(Comp.Image.fromFileSystem(str(avatar_path.absolute())))
            except Exception as e:
                logger.error(f"发送原始图片失败：{str(e)}")
                text_msg += "\n\n（图片发送失败，仅展示文字信息）"

        msg_chain.append(Comp.Plain(text_msg))
        await event.send(event.chain_result(msg_chain))

    async def terminate(self):
        """插件卸载清理"""
        logger.info("今日小猪插件已卸载")
