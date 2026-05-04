import copy
import threading
import time
import tkinter as tk
from tkinter import font, filedialog, ttk
from PIL import Image, ImageTk
import re
from markdown_it import MarkdownIt
import inspect, pickle
import requests
from flask import Flask, request, Response
import base64
from io import BytesIO


# md解析 ==================================================================
def parse_markdown_bold(text: str) -> list[tuple[str, bool]]:
    """
    解析Markdown中**包裹的粗体内容，按顺序返回(文本, 是否为粗体)列表
    正确识别**的开始/结束标记，处理所有边界场景
    """
    # 核心正则：非贪婪匹配**包裹的内容，捕获组保留匹配结果
    pattern = r'(\*\*.*?\*\*)'
    # 分割文本，保留分隔符（粗体片段）
    parts = re.split(pattern, text)
    result = []

    for part in parts:
        # 跳过空字符串（可选，根据需求决定是否保留）
        if not part:
            continue
        # 判断是否是**包裹的粗体内容
        if part.startswith('**') and part.endswith('**'):
            # 去掉**，标记为粗体
            bold_content = part.strip('*')
            result.append((bold_content, True))
        else:
            # 普通文本
            result.append((part, False))

    return result

def parse_markdown(md_content):
    # 初始化解析器
    md = MarkdownIt()
    # 解析为语法令牌
    tokens = md.parse(md_content)

    # 自定义处理：将令牌转为结构化字典
    structure = []
    for token in tokens:
        # 标题
        if token.type == "heading_open":
            level = int(token.tag[1])
            content = tokens[tokens.index(token)+1].content
            structure.append({"type": "heading", "level": level, "content": content})
        # 普通段落
        elif token.type == "paragraph_open":
            content = tokens[tokens.index(token)+1].content
            structure.append({"type": "paragraph", "content": content})
        # 代码块
        elif token.type == "fence":
            structure.append({
                "type": "code_block",
                "language": token.info,
                "content": token.content.strip()
            })
        # 引用
        elif token.type == "blockquote_open":
            structure.append({"type": "quote", "content": "引用文本"})

    # 转为格式化 JSON
    # json_result = json.dumps(structure, ensure_ascii=False, indent=2)
    return structure

def _get_display_width(text: str) -> int:
    """
    计算文本的显示宽度：中文=2字符，英文/数字/符号/Markdown标记=1字符
    """
    width = 0
    for char in text:
        # 判断是否为中文字符（Unicode 基本汉字范围）
        if '\u4e00' <= char <= '\u9fff':
            width += 2
        else:
            width += 1
    return width

def format_markdown_table(table_str: str) -> str:
    """
    将Markdown表格转换为【右侧对齐、中英文宽度计算、移除分隔线】的格式化字符串
    :param table_str: 原始Markdown表格字符串
    :return: 格式化后的表格字符串
    """
    # 1. 分割行 + 去除首尾空格 + 过滤空行
    lines = [line.strip() for line in table_str.split('\n') if line.strip()]

    # 2. 过滤：移除包含分隔线（-----）的行
    valid_lines = [line for line in lines if '-----' not in line]

    if not valid_lines:
        return ""

    # 3. 解析每一行的单元格（按|分割，去除空单元格）
    table_cells = []
    for line in valid_lines:
        # 分割单元格 + 去除每个单元格首尾空格 + 过滤空字符串
        cells = [cell.strip() for cell in line.split('|') if cell.strip()]
        table_cells.append(cells)

    # 校验：所有行列数一致
    col_count = len(table_cells[0])
    for cells in table_cells:
        if len(cells) != col_count:
            raise ValueError("表格格式错误：各行列数不一致")

    # 4. 计算每一列的【最大显示宽度】
    max_col_widths = []
    for col_idx in range(col_count):
        # 取出当前列所有单元格的文本
        col_texts = [row[col_idx] for row in table_cells]
        # 计算每个单元格的显示宽度，取最大值
        max_width = max(_get_display_width(text) for text in col_texts)
        max_col_widths.append(max_width)

    # 5. 格式化每一行：右侧对齐 + 按最大宽度填充
    formatted_lines = []
    for row_cells in table_cells:
        formatted_cells = []
        for idx, cell in enumerate(row_cells):
            # 目标宽度
            target_w = max_col_widths[idx]
            # 当前宽度
            current_w = _get_display_width(cell)
            # 计算需要填充的空格数（右侧对齐，空格补在左侧）
            pad_space = target_w - current_w
            # 拼接：空格 + 单元格内容
            formatted_cell = ' ' * pad_space + cell
            formatted_cells.append(formatted_cell)
        # 拼接成行：| 单元格 | 单元格 |
        formatted_line = '| ' + ' | '.join(formatted_cells) + ' |'
        formatted_lines.append(formatted_line)

    # 6. 拼接所有行，返回结果
    return '\n'.join(formatted_lines)

# =========================

def count_chars(text: str) -> dict:
    # 匹配：中文字符 + 中文标点
    chinese = re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', text)
    # 匹配：英文字母 + 英文标点
    english = re.findall(r'[a-zA-Z\x20-\x7e]', text)

    return {"c": len(chinese), "e": len(english)}

def hex_color_avg(color_tuple: tuple[str, str], weight: float) -> str:
    # 解包元组：两个16进制颜色
    hex1, hex2 = color_tuple
    # 去除#号
    h1 = hex1.lstrip('#')
    h2 = hex2.lstrip('#')

    # 转RGB
    r1, g1, b1 = int(h1[0:2], 16), int(h1[2:4], 16), int(h1[4:6], 16)
    r2, g2, b2 = int(h2[0:2], 16), int(h2[2:4], 16), int(h2[4:6], 16)

    # 核心公式：颜色1×权重 + 颜色2×(1-权重)
    r = r1 * weight + r2 * (1 - weight)
    g = g1 * weight + g2 * (1 - weight)
    b = b1 * weight + b2 * (1 - weight)

    # 合规处理
    r = max(0, min(255, round(r)))
    g = max(0, min(255, round(g)))
    b = max(0, min(255, round(b)))

    # 返回16进制颜色
    return f"#{r:02X}{g:02X}{b:02X}"

# 配色方案
col_dict = {
    "pass": "#1cff6a",  # 0 通过 pass
    "reminder": "#ffe500",  # 1 警告 reminder
    "error": "#ff1c50",  # 2 错误 error

    "light": "#8064ff",  # 3 光
    "main": "#303047",  # 4 界面主色
    "bg": "#1b1b2a",  # 5 背景色
    "text": "#9e8cd2",  # 6 文字
}

# 主窗口 ==================================================================
class Win:
    def __init__(self, title="title", w=512, h=320, menu_config=None, page_config=None):
        self.menu_config = menu_config
        self.page_config = page_config
        self.title = title
        # 配置变量
        self._win_hid = False
        self.show_page = None
        self._while_num0 = 0
        self.w, self.h = w, h

        # 创建主窗口
        self._create_main_window()

        # 创建字体
        self._create_fonts()

        # 创建UI组件
        self._create_title_bar()

        # 绑定事件
        self._bind_events()

    def geometry(self, *args, **kwargs):
        self.root.geometry(*args, **kwargs)

    def _create_main_window(self):
        """创建主窗口"""
        self.root = tk.Tk()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.root.geometry(f'{self.w}x{self.h}+{screen_width // 2 - self.w // 2}+{screen_height // 2 - self.h // 2}')
        self.root.title(self.title)
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='#303047')

        self._hid_root = tk.Toplevel()
        self._hid_root.bind("<Map>", self._unhid_win)
        self._hid_root.iconify()

    def _create_fonts(self):
        """创建界面使用的字体"""
        self._font_12_b = font.Font(family='Minecraft AE Pixel', size=12, weight='bold')
        self._font_12 = font.Font(family='Minecraft AE Pixel', size=12)
        self._font_10_b = font.Font(family='Minecraft AE Pixel', size=10, weight='bold')
        self._font_9_b = font.Font(family='Minecraft AE Pixel', size=9, weight='bold')
        self._font_9 = font.Font(family='Minecraft AE Pixel', size=9)
        self._font_10 = font.Font(family='Minecraft AE Pixel', size=10)

    def to_page(self, title):
        # print(f"to_page {title}")
        self.show_page = title
        for t, button in self.page_buttons.items():
            # print(t, title)
            if t == title:
                self.page_buttons[t].label.configure(bg=col_dict['bg'], fg=col_dict['light'])
            else:
                self.page_buttons[t].label.configure(bg=col_dict['main'], fg=col_dict['text'])

        for t, screen in self.screen_frames.items():
            if title == t:
                screen.pack(padx=5, pady=5, expand=True, fill='both')
            else:
                screen.pack_forget()

    def _create_title_bar(self):
        """创建标题栏"""
        self._title_frame = tk.Frame(self.root, bg=col_dict["main"])
        self._title_frame.pack(fill='x', padx=1, pady=1)

        self.title_label = tk.Label(self._title_frame, text=f" # {self.title}", font=self._font_12_b,
                                     bg=col_dict["main"], fg=col_dict["text"], anchor='w')
        self.title_label.pack(fill='x', side='left', expand=True)

        self._min_win_button = Button(self._title_frame, '➖', stroke=False, command=self._min_win, font_pixel=False)
        self._min_win_button.pack(side='left')

        self._close_win_button = Button(self._title_frame, "❌", stroke=False, command=self._close_win, font_pixel=False)
        self._close_win_button.pack(side='left')

        self._menu_frame = tk.Frame(self.root, bg=col_dict["main"])
        self._menu_frame.pack(fill='x', padx=1, pady=1)

        tk.Frame(self._menu_frame, width=5, bg=col_dict['main']).pack(side='left')
        if self.menu_config:
            def get_menu(config):
                MenuWin(config)

            for title, config in self.menu_config.items():
                button = Button(self._menu_frame, f"{title} ", stroke=False, command=get_menu, command_args=config, font_size=8)
                button.pack(side='left')

        self.root_frame = tk.Frame(self.root, width=200, height=200, bg=col_dict["bg"])
        self.root_frame.pack(padx=5, pady=5, expand=True, fill='both')

        if self.page_config:
            self.page_frame = tk.Frame(self.root_frame, bg=col_dict["main"])
            self.page_frame.pack(fill='x', padx=5, pady=(5, 0))

            self.screen_frames = {}
            self.page_buttons = {}

            for i, title in enumerate(self.page_config):
                button = Button(self.page_frame, f"{title} ", stroke=False, command=self.to_page, command_args=title, font_size=8)
                button.pack(side='left', padx=(5, 0))

                screen_frame = tk.Frame(self.root_frame, bg=col_dict["main"], bd=0, height=5, width=30)
                self.screen_frames[title] = screen_frame
                self.page_buttons[title] = button

            self.screen_frames[self.page_config[0]].pack(padx=5, pady=5, expand=True, fill='both')

            self.to_page(self.page_config[0])
        else:
            self.screen_frame = tk.Frame(self.root_frame, bg=col_dict["main"], bd=0, height=5, width=30)
            self.screen_frame.pack(padx=5, pady=5, expand=True, fill='both')

    def add_page(self, title):
        if title in self.page_config:
            print(f"{title} 已存在")
        self.page_config.append(title)

        button = Button(self.page_frame, f"{title} ", stroke=False, command=self.to_page, command_args=title, font_size=8)
        button.pack(side='left', padx=(5, 0))
        screen_frame = tk.Frame(self.root_frame, bg=col_dict["main"], bd=0, height=5, width=30)
        self.screen_frames[title] = screen_frame
        self.page_buttons[title] = button

    def del_page(self, title):
        if title not in self.page_config:
            return
        for t in self.page_config:
            if t != title:
                self.to_page(t)
                break

        self.page_config.remove(title)
        del self.screen_frames[title]
        self.page_buttons[title].pack_forget()
        del self.page_buttons[title]

    def rename_page(self, title, new_title):
        self.page_buttons[title].configure(text=new_title)

        self.screen_frames[new_title] = self.screen_frames[title]
        self.page_buttons[new_title] = self.page_buttons[title]

        del self.screen_frames[title]
        del self.page_buttons[title]

    def _bind_events(self):
        """绑定事件处理函数"""
        # 标题栏拖动事件
        self.title_label.bind("<ButtonPress-1>", self._on_button_press0)
        self.title_label.bind("<ButtonRelease-1>", self._on_button_release0)

        # 窗口隐藏/显示事件
        self.root.bind("<Unmap>", self._hid_win)

    def _close_win(self):
        """关闭窗口"""
        self.root.destroy()

    def _min_win(self):
        """最小化窗口"""
        self.root.withdraw()

    def _unhid_win(self, e=None):
        """显示窗口"""
        if self._win_hid:
            self._win_hid = False
            self.root.deiconify()

        self._hid_root.withdraw()
        self._hid_root.iconify()

    def _hid_win(self, e=None):
        """隐藏窗口"""
        if e.widget == self.root and not self._win_hid:
            self._win_hid = True
            self.root.withdraw()

    def _on_button_press0(self, event):
        """鼠标按下事件处理（用于拖动窗口）"""
        self._while_num0 = 0
        while True:
            if self._while_num0 == 0:
                x, y = self.root.winfo_pointerxy()
                x0, y0 = event.x, event.y
                self.root.geometry("+{}+{}".format(x - x0 - 1, y - y0 - 1))
                self.root.update()
            else:
                break

    def _on_button_release0(self, event):
        """鼠标释放事件处理（用于拖动窗口）"""
        if self._while_num0 == 2:
            pass
        else:
            self._while_num0 = 1

    def mainloop(self):
        """运行主循环"""
        self.root.mainloop()

# 副窗口 ==================================================================
class Toplevel(Win):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _create_main_window(self):
        """创建主窗口"""
        self.root = tk.Toplevel()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.root.geometry(f'{self.w}x{self.h}+{screen_width // 2 - self.w // 2}+{screen_height // 2 - self.h // 2}')
        self.root.title(self.title)
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='#303047')

        self._hid_root = tk.Toplevel()
        self._hid_root.bind("<Map>", self._unhid_win)
        self._hid_root.iconify()

    def mainloop(self):
        """运行主循环"""
        pass

# 提醒框窗口 ==================================================================
class MessageBox:
    def __init__(self, title="MessageBox", message="This is an example of a MessageBox window.", mode='error', only=False):
        self.message = message
        self.mode = mode
        self.text_count = count_chars(message)

        self.only = only
        self.light_w = 0.0
        self.light_mode = 0

        self.title = title
        # 配置变量
        self.w = min(int((self.text_count['e'] + self.text_count['c'] * 1.5 + 100) * 3 ** (3/4) + 30), 420)
        self.h = min(int((self.text_count['e'] + self.text_count['c'] * 1.5 + 100) * 0.8 ** (1/4) + 30), 200)
        # 创建主窗口
        self._create_main_window()
        # 创建字体
        self._create_fonts()
        # 创建UI组件
        self._create_title_bar()
        self._create_main_frame()

        # 绑定事件
        self._bind_events()

    def _create_main_window(self):
        """创建主窗口"""
        if self.only:
            self._root = tk.Tk()
        else:
            self._root = tk.Toplevel()
        screen_width = self._root.winfo_screenwidth()
        screen_height = self._root.winfo_screenheight()
        self._root.geometry(f'{self.w}x{self.h}+{screen_width // 2 - self.w // 2}+{screen_height // 2 - self.h // 2}')
        self._root.title(self.title)
        self._root.overrideredirect(True)
        self._root.attributes('-topmost', True)
        self._root.configure(bg='#303047')

    def _bind_events(self):
        """绑定事件处理函数"""
        # 标题栏拖动事件
        self._title_label.bind("<ButtonPress-1>", self._on_button_press0)
        self._title_label.bind("<ButtonRelease-1>", self._on_button_release0)

    def _create_fonts(self):
        """创建界面使用的字体"""
        self._font_12_b = font.Font(family='Minecraft AE Pixel', size=12, weight='bold')
        self._font_12 = font.Font(family='Minecraft AE Pixel', size=12)
        self._font_11 = font.Font(family='Minecraft AE Pixel', size=11)

    def _create_title_bar(self):
        """创建标题栏"""
        self._title_frame = tk.Frame(self._root, bg=col_dict["main"])
        self._title_frame.pack(fill='x', padx=1, pady=1)

        self._title_label = tk.Label(self._title_frame, text=f" # {self.title}", font=self._font_12_b,
                                     bg=col_dict["main"], fg=col_dict['text'], anchor='w')
        self._title_label.pack(fill='x', side='left', expand=True)

        self._close_win_button = tk.Button(self._title_frame, text="❌", bg=col_dict["main"],
                                           fg=col_dict["text"], bd=0, command=self._close_win)
        self._close_win_button.pack(side='left')

    def light(self):
        if self.light_w < 1 and not self.light_mode:
            self.light_w += 0.1
        else:
            self.light_mode = 1

        if self.light_w > 0 and self.light_mode:
            self.light_w -= 0.1
        else:
            self.light_mode = 0

        col = hex_color_avg((col_dict[self.mode], col_dict["bg"]), self.light_w)
        self._root.update()
        try:
            self.light_box.configure(bg=col)
        except:
            return

        self._root.after(100, self.light)

    def _create_main_frame(self):
        """创建主框架"""
        self._root_frame = tk.Frame(self._root, width=200, height=200, bg=col_dict["bg"])
        self._root_frame.pack(padx=5, pady=5, expand=True, fill='both')

        self.light_box = tk.Frame(self._root_frame, width=200, height=200, bg=col_dict[self.mode])
        self.light_box.pack(padx=2, pady=2, expand=True, fill='both')

        self.screen_frame = tk.Frame(self.light_box, bg=col_dict["main"], bd=0, height=5, width=30)
        self.screen_frame.pack(padx=3, pady=3, expand=True, fill='both')

        self.title_label = tk.Label(self.screen_frame,
            text=f"{self.title}",
            font=self._font_12_b,
            bg=col_dict["main"], fg=col_dict[self.mode],
            anchor="center",  # 文字居中
            justify=tk.CENTER,  # 换行文字居中
            wraplength=self.w * 0.9)  # 自动换行
        self.title_label.pack(fill="x", pady=(16, 0))  # 组件在父容器完全居中

        self.message_label = tk.Label(self.screen_frame, text=f"{self.message}", font=self._font_11,
                                      bg=col_dict["main"], fg=col_dict[self.mode],
                                      anchor="center",  # 文字居中
                                      justify=tk.CENTER,  # 换行文字居中
                                      wraplength=self.w * 0.9)  # 自动换行
        self.message_label.pack(expand=True, fill="both", pady=(0, 16))  # 组件在父容器完全居中

        self.light()

    def _close_win(self):
        """关闭窗口"""
        self._root.destroy()
        self.only = False

    def _on_button_press0(self, event):
        """鼠标按下事件处理（用于拖动窗口）"""
        self._while_num0 = 0
        while True:
            if self._while_num0 == 0:
                x, y = self._root.winfo_pointerxy()
                x0, y0 = event.x, event.y
                self._root.geometry("+{}+{}".format(x - x0 - 1, y - y0 - 3))
                self._root.update()
            else:
                break

    def _on_button_release0(self, event):
        """鼠标释放事件处理（用于拖动窗口）"""
        if self._while_num0 == 2:
            pass
        else:
            self._while_num0 = 1

    def mainloop(self):
        """运行主循环"""
        self._root.mainloop()

# 确认框窗口 ==================================================================
class ConfirmationBox(MessageBox):
    def __init__(self, title="MessageBox", message="This is an example of a ConfirmationBox window.", mode='error'):
        super().__init__(title, message, mode)
        self.h += 20
        self._root.geometry(f'{self.w}x{self.h}')
        self.result = None

        button_frame = tk.Frame(self.screen_frame)
        button_frame.pack(expand=True, fill="x", pady=(0, 5), padx=5)
        Button(button_frame, 'Cancel', stroke=False, command=self._cancel).pack(expand=True, side='left', fill="x")
        Button(button_frame, 'confirm', stroke=False, command=self._confirm, fg=col_dict['pass']).pack(expand=True, side='left', fill="x")

    def _close_win(self):
        """关闭窗口"""
        self._root.destroy()
        self.result = False

    def _cancel(self):
        self._root.destroy()
        self.result = False

    def _confirm(self):
        self._root.destroy()
        self.result = True

    def get_result(self):
        while self.result is None:
            time.sleep(0.1)
            self._root.update()
        return self.result

# 菜单窗口 ==================================================================
class MenuWin:
    def __init__(self, config):
        self.root = tk.Toplevel()
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='#303047')
        x, y = get_mouse_pos(self.root)
        self.root.geometry(f'+{x}+{y}')

        frame = tk.Frame(self.root, bg=col_dict['bg'])
        frame.pack()
        n = 0
        pad = 5
        for title, command in config.items():
            button = Button(frame, f" {title}", stroke=False, anchor='w', height=1, command=command, font_size=10)
            if len(config) == 1:
                button.pack(padx=pad, pady=pad, expand=True, fill="x")
            elif n == 0:
                button.pack(padx=pad, pady=(pad, 1), expand=True, fill="x")
            elif n == len(config)-1:
                button.pack(padx=pad, pady=(1, pad), expand=True, fill="x")
            else:
                button.pack(padx=pad, pady=(1, 1), expand=True, fill="x")
            n += 1

        self.root.lift()  # 窗口置顶
        self.root.focus_force()  # 强制获取输入焦点（核心）
        self.on_focus()

    def on_focus(self):
        test =  is_focus(self.root)

        if test:
            self.root.after(100, self.on_focus)
        else:
            self.root.destroy()
            return

# 父级模块模板
class Module:
    def __init__(self):
        self.main_frame = None

    def destroy(self, *args, **kwargs):
        self.main_frame.destroy(*args, **kwargs)

    def configure(self, *args, **kwargs):
        self.main_frame.configure(*args, **kwargs)

    def pack(self, *args, **kwargs):
        self.main_frame.pack(*args, **kwargs)

    def place(self, *args, **kwargs):
        self.main_frame.place(*args, **kwargs)

    def pack_forget(self, *args, **kwargs):
        self.main_frame.pack_forget(*args, **kwargs)

    def place_forget(self, *args, **kwargs):
        self.main_frame.place_forget(*args, **kwargs)

    def bind(self, *args, **kwargs):
        self.main_frame.bind(*args, **kwargs)

    def config(self, *args, **kwargs):
        self.main_frame.config(*args, **kwargs)

# 文本框 ==================================================================
class Label(Module):
    def __init__(self, root, text, bg=col_dict["main"], fg=col_dict["text"], font_size=11, font_weight='bold',
                 anchor='w', width=None):
        super().__init__()
        self._font = font.Font(family='Minecraft AE Pixel', size=font_size, weight=font_weight)
        self.label = tk.Label(root, text=text, font=self._font, bg=bg, fg=fg, anchor=anchor, width=width)
        self.main_frame = self.label

# 按钮 ==================================================================
class Button(Module):
    def __init__(self, root, text, bg=col_dict["main"], fg=col_dict["text"], font_size=11, font_weight='bold',
                 anchor='center', width=None, height=None, stroke=False, font_pixel=True, command=None, switch=False,
                 command_args=None):
        super().__init__()
        self.switch = switch
        self.mode = None
        if switch:
            self.mode = False

        self.fg = fg
        self.command = command
        self.command_args = command_args
        self.stroke = stroke
        self._font = font.Font(family='Minecraft AE Pixel', size=font_size, weight=font_weight)

        self.bg = bg
        self.label = tk.Label(root, text=text, font=self._font if font_pixel else None, bg=bg, fg=self.fg, anchor=anchor, width=width, height=height)
        self.label.place(x=0, y=0)
        root.update()
        w, h = self.label.winfo_width(), self.label.winfo_height()
        self.w, self.h = w, h
        self.label.place_forget()

        if stroke:
            self.show_label = tk.Frame(root, bg=col_dict['bg'], width=w+10, height=h+10)
            self.label = tk.Label(self.show_label, text=text, font=self._font if font_pixel else None, bg=bg, fg=fg,
                                  anchor=anchor, width=width, height=height)
            self.label.pack(pady=5, padx=5, expand=True, fill='both')
        else:
            self.show_label = tk.Frame(root, bg=col_dict['bg'], width=w, height=h)
            self.label = tk.Label(self.show_label, text=text, font=self._font if font_pixel else None, bg=bg, fg=fg,
                                  anchor=anchor, width=width, height=height)
            self.label.pack(expand=True, fill='both')

        self.label.bind("<ButtonPress-1>", self._press)
        self.label.bind("<ButtonRelease-1>", self._release)
        self.label.bind("<Enter>", self._enter)  # 鼠标进入控件区域
        self.label.bind("<Leave>", self._leave)  # 鼠标离开控件区域

        self.main_frame = self.show_label

    def _enter(self, e):
        if self.switch:
            if self.mode:
                self.label.configure(fg=self.fg)
            else:
                self.label.configure(fg=col_dict['light'])
        else:
            self.label.configure(fg=col_dict['light'])

    def _leave(self, e):
        if self.switch:
            if self.mode:
                self.label.configure(fg=col_dict['light'])
            else:
                self.label.configure(fg=self.fg)
        else:
            self.label.configure(fg=self.fg)

    def _press(self, e):
        self.label.configure(bg=col_dict['bg'], fg=col_dict['light'])

    def _release(self, e):
        self.label.configure(bg=self.bg, fg=self.fg)
        if self.command:
            x, y = e.x, e.y
            if 0 < x < self.w and 0 < y < self.h:
                if self.switch:
                    if self.mode:
                        self.mode = False
                        if callable(self.command[0]):
                            if self.command_args and self.command_args[0] is not None:
                                self.command[0](self.command_args[0])
                            else:
                                self.command[0]()
                        else:
                            for function in self.command[0]:
                                if self.command_args and self.command_args[0] is not None:
                                    function(self.command_args[0])
                                else:
                                    function()
                    else:
                        self.mode = True
                        if callable(self.command[1]):
                            self.command[1]()
                        else:
                            for function in self.command[1]:
                                if self.command_args and self.command_args[1] is not None:
                                    function(self.command_args[1])
                                else:
                                    function()
                else:
                    if callable(self.command):
                        if self.command_args is not None:
                            self.command(self.command_args)
                        else:
                            self.command()
                    else:
                        for function in self.command:
                            if self.command_args:
                                function(self.command_args)
                            else:
                                function()

# 滑动条 ==================================================================
class ScrollBar(Module):
    def __init__(self, root_win, root, num_range, length, width, show_num=True, vertical=False):
        super().__init__()
        self.width = width
        self.show_num = show_num
        self.num_range = num_range
        self.root_win = root_win
        self.root = root
        self.x = 0
        self.click_x = None
        self.value = num_range[0]
        self.length = length
        self.show_label = tk.Frame(root, width=length, height=width, bg=col_dict['main'])

        self.bar_line = tk.Frame( self.show_label, width=length, height=int(width*0.64), bg=col_dict['bg'])
        self.bar_line.bind("<Button-1>", self._line_click)
        self.bar_line.place(x=0, y=(width - int(width*0.64)) // 2)
        self.button_bg = tk.Frame(self.show_label, width=int(length * 0.1), height=width, bg=col_dict['main'])
        self.button_bg.place(x=self.x, y=0)
        self.bar_button = tk.Frame(self.button_bg, width=int(length * 0.06), height=width, bg=col_dict['bg'])
        self.bar_button.place(x=int(length * 0.02), y=0)
        self.bar_button.bind("<ButtonPress-1>", self._press)
        self.bar_button.bind("<ButtonRelease-1>", self._release)
        self.bar_button.bind("<Enter>", self._enter)  # 鼠标进入控件区域
        self.bar_button.bind("<Leave>", self._leave)  # 鼠标离开控件区域
        self.bar_button.bind("<B1-Motion>", self._motion)  # 左键拖动

        if self.show_num:
            self.num_label = Label(self.bar_line, self.value, font_size=int(width*0.64) // 2, bg=col_dict['bg'], fg=col_dict['light'])
            self.num_label.bind(sequence="<Button-1>", func=self._num_label_click)
            self.num_label.place(x=0, y=0)

            if self.x < len(str(self.value)) * (int(self.width*0.64) // 2):
                self.num_label.place(x=self.x + self.length * 0.1, y=0)
            else:
                self.num_label.place(x=0, y=0)

        self.main_frame = self.show_label

    def _num_label_click(self, e):
        if self.x >= self.length * 0.3:
            self._line_click(e)

    def _line_click(self, e):
        w = self.button_bg.winfo_width()
        self.x = e.x - w / 2
        self.button_bg.place(x=self.x, y=0)

        self.value = round(self.x / (self.length * 0.9) * (self.num_range[1] - self.num_range[0]) + self.num_range[0], 2)

        if self.show_num:
            self.num_label.configure(text=self.value)
            if self.x < len(str(self.value)) * (int(self.width*0.64) // 2):
                self.num_label.place(x=self.x + self.length * 0.1, y=0)
            else:
                self.num_label.place(x=0, y=0)
            self.num_label.configure(text=self.value)

    def _motion(self, e):
        x, y = e.x, e.y
        if 0 <= self.x <= self.length * 0.9:
            self.x += x - self.click_x
            self.button_bg.place(x=self.x, y=0)
        elif self.x < 0:
            self.x = 0
        else:
            self.x = self.length * 0.9

    def _enter(self, e):
        self.bar_button.configure(bg=col_dict['light'])

    def _leave(self, e):
        self.bar_button.configure(bg=col_dict['bg'])

    def _press(self, e):
        self.bar_button.configure(bg=col_dict['light'])
        self.click_x = e.x

    def _release(self, e):
        self.bar_button.configure(bg=col_dict['bg'])
        if 0 <= self.x <= self.length * 0.9:
            pass
        elif self.x < 0:
            self.x = 0
        else:
            self.x = self.length * 0.9

        self.value = round(self.x / (self.length * 0.9) * (self.num_range[1] - self.num_range[0]) + self.num_range[0], 2)
        self.button_bg.place(x=self.x, y=0)

        if self.show_num:
            self.num_label.configure(text=self.value)
            if self.x < len(str(self.value)) * (int(self.width*0.64) // 2):
                self.num_label.place(x=self.x + self.length * 0.1, y=0)
            else:
                self.num_label.place(x=0, y=0)

    def get(self):
        return min(max(self.value, self.num_range[0]), self.num_range[1])

# 复选框 ======================================
class CheckBox(Module):
    def __init__(self, root, title="check_box", size=20):
        super().__init__()
        self.value = 0
        self.incompatibility_check_boxs = None
        self.title = title
        self.show_label = tk.Frame(root, width=size+4, height=size+4, bg=col_dict['bg'])
        self.border_label = tk.Frame(self.show_label, width=size, height=size, bg=col_dict['main'])
        self.border_label.pack(side='left', padx=2, pady=2)
        self.button = tk.Frame(self.border_label, width=size-10, height=size-10, bg=col_dict['bg'])
        self.button.bind("<Enter>", self._enter)  # 鼠标进入控件区域
        self.button.bind("<Leave>", self._leave)  # 鼠标离开控件区域
        self.button.bind("<Button-1>", self.click)
        self.button.place(x=5, y=5)
        if title:
            self.title_label = Label(self.show_label, f" {title}", font_size=int(size*0.5))
            self.title_label.pack(side='left', padx=(0, 2), pady=2, fill='x', expand=True)

        self.main_frame = self.show_label

    def _enter(self, e):
        self.show_label.configure(bg=col_dict['light'])

    def _leave(self, e):
        self.show_label.configure(bg=col_dict['bg'])

    def click(self, e):
        if self.incompatibility_check_boxs:
            if not self.value:
                self.value = 1
                self.button.configure(bg=col_dict['light'])

                for check_box in self.incompatibility_check_boxs:
                    if check_box == self:
                        continue
                    else:
                        print(check_box)
                        if check_box.get():
                            check_box.click(0)
            else:
                self.value = 0
                self.button.configure(bg=col_dict['bg'])
        else:
            if self.value:
                self.value = 0
                self.button.configure(bg=col_dict['bg'])
            else:
                self.value = 1
                self.button.configure(bg=col_dict['light'])

    def bind_incompatibility(self, check_boxs):
        self.incompatibility_check_boxs = check_boxs

    def get(self):
        return self.value

# 进度条 ==================================================================
class ProgressBar(Module):
    def __init__(self, root, title=None, length=200, width=10):
        super().__init__()
        self.loading = 0.0
        self.length = length
        self.root = root

        self.show_label = tk.Frame(root)
        if title:
            self.title_label = Label(self.show_label, title, font_size=width)
            self.title_label.pack(side='left')
        self.bar_bg = tk.Frame(self.show_label, width=length, height=width, bg=col_dict['bg'])
        self.bar_bg.pack(side='left', expand=True, fill='y')

        self.bar = tk.Frame(self.bar_bg, width=length * self.loading, height=width*2, bg=col_dict['light'])
        self.bar.place(x=0, y=0)

        tk.Frame(self.bar_bg, bg=col_dict['main'], width=length, height=width*0.5).place(x=0, y=0)
        tk.Frame(self.bar_bg, bg=col_dict['main'], width=length, height=width*0.5).place(x=0, y=width*1.4)

        self.loading_label = Label(self.show_label, f" {self.loading*100:.2f}%", font_size=width, fg=col_dict['light'])
        self.loading_label.pack(side='left')

        self.main_frame = self.show_label

    def update(self, i, total):
        try:
            self.loading = (i+1) / total
            self.loading_label.configure(text=f" {self.loading*100:.2f}%")
            self.bar.configure(width=self.length * self.loading)

            if i+1 == total:
                self.loading_label.configure(fg=col_dict['pass'])
                self.bar.configure(bg=col_dict['pass'])
            self.root.update()
        except: pass

    def pack(self, *args, **kwargs):
        self.show_label.pack(*args, **kwargs)

    def place(self, *args, **kwargs):
        self.show_label.place(*args, **kwargs)

# 加载条（无进度）==================================================================
class LoadingBar(Module):
    def __init__(self, root, title=None, length=200, width=10):
        super().__init__()
        self.bar_x = - length * 0.3
        self.length = length
        self.run = False

        self.root = root

        self.show_label = tk.Frame(root)
        if title:
            self.title_label = Label(self.show_label, title, font_size=width)
            self.title_label.pack(side='left')
        self.bar_bg = tk.Frame(self.show_label, width=length, height=width, bg=col_dict['bg'])
        self.bar_bg.pack(side='left', expand=True, fill='y')

        self.bar = tk.Frame(self.bar_bg, width=length * 0.3, height=width, bg=col_dict['light'])
        self.bar.place(x=self.bar_x, y=0)

        self.main_frame = self.show_label

    def start(self):
        self.run = True
        self.bar.configure(width=self.length * 0.3, bg=col_dict['light'])
        self.update()

    def done(self):
        self.run = False
        self.bar_x = self.length
        self.bar.configure(width=self.length, bg=col_dict['pass'])
        self.bar.place(x=0, y=0)

    def update(self):
        if self.run:
            try:
                self.bar_x += 5
                if self.bar_x > self.length * 1.3:
                    self.bar_x = - self.length * 0.3
                self.bar.place(x=self.bar_x, y=0)
                self.root.after(100, self.update)
            except: pass
        else:
            return

# 输入框 ==================================================================
class Entry(Module):
    def __init__(self, root, bg=col_dict['bg'], fg=col_dict['text'], width=None, font_size=11, stroke=True):
        super().__init__()
        self._font = font.Font(family='Minecraft AE Pixel', size=font_size)

        self.frame = tk.Frame(root, bg=col_dict['bg'])

        self.entry = tk.Entry(self.frame, bg=bg, fg=fg, bd=0, width=width, font=self._font)
        if stroke:
            self.entry.pack(padx=5, pady=5)
        else:
            self.entry.pack()
        self.main_frame = self.frame

    def delete(self, *args, **kwargs):
        self.entry.delete(*args, **kwargs)

    def insert(self, *args, **kwargs):
        self.entry.insert(*args, **kwargs)

    def get(self):
        return self.entry.get()

# 文本框 ==================================================================
class Text(Module):
    def __init__(self, root, bg=col_dict['bg'], fg=col_dict['text'], width=20, height=10, font_size=10, family='Minecraft AE Pixel',
                 spacing1=2, spacing2=5, spacing3=10, wrap=None, tag_config=[]):
        super().__init__()
        self._font = font.Font(family=family, size=font_size)


        self.main_frame = tk.Frame(root, bg=col_dict['bg'])
        self.text = tk.Text(self.main_frame, bg=bg, fg=fg, bd=0, width=width, height=height, font=self._font,
                            spacing1=spacing1,  # 段前
                            spacing2=spacing2,  # 自动换行间距
                            spacing3=spacing3,  # 段后
                            wrap=wrap
                            )
        self.text.pack(padx=5, pady=5)
        if tag_config:
            for tag_item in tag_config:
                self.text.tag_configure(**tag_item)

    def delete(self, *args, **kwargs):
        self.text.delete(*args, **kwargs)

    def insert(self, *args, **kwargs):
        self.text.insert(*args, **kwargs)

    def get(self, *args, **kwargs):
        return self.text.get(*args, **kwargs)

# 表格 ==================================================================
class Table(Module):
    def __init__(self, root, config, height=4, font_size=10):
        super().__init__()
        self.height = height
        self.config = config
        self.font_size = font_size
        style = ttk.Style()
        style.configure('Treeview', font=('Minecraft AE Pixel', 8), background=col_dict['bg'],
                        foreground=col_dict['text'])
        self._font_11_b = font.Font(family='Minecraft AE Pixel', size=11, weight='bold')

        self.table = ttk.Treeview(root, columns=tuple(config.keys()), show='headings', height=height)

        # for code_path, data in self.code_data.items():
        #     self.entry.insert('', 'end', values=(os.path.basename(code_path), data['state'], code_path))
        #
        for _ in range(height):
            self.table.insert('', 'end', values=('',) * len(config))
        for key, value in config.items():
            self.table.heading(key, text=key)
            self.table.column(key, width=value)
        self.table.place(x=0, y=0)

        # 绑定鼠标点击事件
        # self.table.bind("<ButtonRelease-1>", self.on_tree_click)
        # 绘制标题空间
        place_x = 1
        for k, v in config.items():
            f = tk.Frame(self.table, bg=col_dict['main'], width=v, height=25)
            f.place(x=place_x, y=0)
            Label(f, text=k, bg=col_dict["main"], fg=col_dict['text'], anchor='w', font_size=self.font_size).place(x=0,y=5)
            place_x += v

        root.update()
        w, h = self.table.winfo_width(), self.table.winfo_height()
        tk.Frame(self.table, bg=col_dict['bg'], width=w, height=1).place(x=0, y=0)
        tk.Frame(self.table, bg=col_dict['bg'], width=1, height=h).place(x=0, y=0)
        tk.Frame(self.table, bg=col_dict['bg'], width=1, height=h).place(x=w - 1, y=0)
        tk.Frame(self.table, bg=col_dict['bg'], width=w, height=1).place(x=0, y=h - 1)

        self.main_frame = self.table

    def clear(self, fill=True):
        for item in self.table.get_children():
            self.table.delete(item)
        if fill:
            for _ in range(self.height):
                self.table.insert('', 'end', values=('',) * len(self.config))

    def append(self, new_data):
        # 获取所有行的唯一ID（正序）
        items = self.table.get_children()

        # 反向遍历（从最后一行往第一行走）
        last_empty_item = None
        for item in reversed(items):
            row_values = self.table.item(item, "values")
            is_empty = all(str(val).strip() == "" for val in row_values)

            if is_empty:
                last_empty_item = item
            else:
                break

        if last_empty_item:
            self.table.item(last_empty_item, values=new_data)
        else:
            self.table.insert("", "end", values=new_data)

    def update(self, data_list):
        self.clear(fill=False)
        l = len(data_list)
        for v in data_list:
            self.table.insert("", "end", values=v)
        for _ in range(self.height - l):
            self.table.insert('', 'end', values=('',) * len(self.config))

    def on_tree_click(self, e):
        # 获取当前选中的项
        selected_item = self.table.selection()
        if not selected_item:
            return  # 没有选中项，直接返回

        # 获取选中项的 ID
        item_id = selected_item[0]

        row_index = self.table.index(item_id)
        # 获取项的所有列值
        values = self.table.item(item_id, "values")
        print(values)

# 图片展示框 ==================================================================
def b64_to_pil(b64_str):
    # 剔除base64头部标识
    if ',' in b64_str:
        b64_str = b64_str.split(',')[1]
    # base64解码为字节
    img_data = base64.b64decode(b64_str)
    # 字节流转PIL图像
    return Image.open(BytesIO(img_data))

class ImgLabel(Module):
    def __init__(self, root, img=None, bg=col_dict['bg'], size=()):
        super().__init__()
        if img:
            print(type(img))
            if type(img) is type(Image.new('RGB', (1, 1), 'white')):
                image = img
            else:
                try:
                    image = Image.open(img)
                except:
                    image = b64_to_pil(img)
        else:
            image = Image.new("RGB", size, bg)

        self.frame = tk.Frame(root, bg=bg, width=size[0], height=size[1])

        self.size = size
        if self.size:
            w, h = image.size
            if w < h:
                new_h = self.size[1]
                new_w = int(new_h / h * w)
            else:
                new_w = self.size[0]
                new_h = int(new_w / w * h)
            image = image.resize((new_w, new_h))
            self.photo = ImageTk.PhotoImage(image)
            self.label = tk.Label(self.frame, bd=0, image=self.photo)
            if w < h:
                self.label.place(x=(self.size[0] - new_w) // 2, y=0)
            else:
                self.label.place(x=0, y=(self.size[1] - new_h) // 2)

            self.update(image)
        else:
            self.photo = ImageTk.PhotoImage(image)
            self.label = tk.Label(self.frame, bd=0, image=self.photo)
            self.label.pack()

        self.main_frame = self.frame

    def resize(self, size):
        self.size = size
        self.frame.configure(width=size[0], height=size[1])

    def update(self, img):
        # 1. 加载图片（兼容路径字符串 / PIL图像对象）
        if isinstance(img, str):
            image = Image.open(img)
        else:
            image = img

        if self.size:
            container_w, container_h = self.size  # 容器宽高
            img_w, img_h = image.size  # 原始图片宽高

            # 同时计算 图片比例 + 容器比例，自动判断按宽/按高缩放
            img_ratio = img_w / img_h  # 图片宽高比
            container_ratio = container_w / container_h  # 容器宽高比

            if img_ratio >= container_ratio:
                # 图片更宽 → 按容器宽度缩放（高度自动适配，不会溢出）
                new_w = container_w
                new_h = int(new_w / img_ratio)
            else:
                # 图片更高/正方形 → 按容器高度缩放（宽度自动适配，不会溢出）
                new_h = container_h
                new_w = int(new_h * img_ratio)

            # 高清缩放图片
            image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(image)
            self.label.configure(image=self.photo)

            # 固定居中：水平+垂直完全居中（无任何判断，通用所有情况）
            x = (container_w - new_w) // 2
            y = (container_h - new_h) // 2
            self.label.place(x=x, y=y)


        else:
            # 无容器尺寸时，直接显示
            self.photo = ImageTk.PhotoImage(image)
            self.label.configure(image=self.photo)

# 互斥复选框 ====================================================================
class OptionBox(Module):
    def __init__(self, root, option_config, name_mode=False):
        super().__init__()
        self.frame = tk.Frame(root, bg=col_dict['bg'])
        self.name_mode = name_mode
        self.option_config = option_config

        f = tk.Frame(self.frame)
        f.pack(pady=3, padx=3)
        self.check_boxs = []
        for title in option_config:
            check_box = CheckBox(f, title=title)
            check_box.pack(fill='x', expand=True)
            self.check_boxs.append(check_box)

        for i, check_box in enumerate(self.check_boxs):
            check_box.bind_incompatibility(self.check_boxs)

        self.main_frame = self.frame

    def get(self):
        values = [check_box.value for check_box in self.check_boxs]
        if self.name_mode:
            return self.option_config[values.index(1)]
        else:
            return values.index(1)

# 下拉选择框 =====================================================================
class ChoiceBox(Module):
    def __init__(self, root, choices, width=10, font_size=10):
        super().__init__()
        self.font_size = font_size
        self.choices = choices
        self.index = 0
        self.expand = False

        self.choice = choices[self.index]

        self.width = width
        self.frame = tk.Frame(root, bg=col_dict['bg'])

        label_frame = tk.Frame(self.frame, bg=col_dict['bg'])
        label_frame.pack()
        self.label = Label(label_frame, self.choice, font_size=font_size, width=self.width, anchor='w')
        self.label.pack(padx=(5, 1), pady=5, side='left')
        self.button = Button(label_frame, '▼', font_size=font_size, width=2, command=self.click_button)
        self.button.pack(padx=(1, 5), pady=5, side='left')

        self.button_frame = tk.Frame(self.frame, bg=col_dict['bg'])
        self.button_frame.pack()
        self.button_show = []

        self.main_frame = self.frame

    def click_button(self):
        def update(index):
            self.index = index
            self.choice = self.choices[self.index]
            self.label.configure(text=self.choice)

        if self.expand:
            self.expand = False
            for frame in self.button_show:
                frame.pack_forget()
            self.button_show = []
            self.button_frame.pack_forget()
        else:
            self.button_frame.pack()
            self.expand = True
            last = len(self.choices) - 1
            for i, choice in enumerate(self.choices):
                frame = tk.Frame(self.button_frame, bg=col_dict['bg'])
                frame.pack()
                button = Button(frame, choice, font_size=self.font_size, width=self.width, anchor='w', command=update, command_args=i)
                block = Label(frame, '', font_size=self.font_size, width=2, bg=col_dict['bg'])
                if i == last:
                    button.pack(padx=(5, 1), pady=(0, 5), side='left')
                    block.pack(padx=(1, 5), pady=(0, 5), side='left')
                else:
                    button.pack(padx=(5, 1), pady=(0, 2), side='left')
                    block.pack(padx=(1, 5), pady=(0, 2), side='left')
                self.button_show.append(frame)

    def get(self):
        return self.index, self.choice

    def set(self, index=None, choice=None):
        if index:
            self.index = index
            self.choice = self.choices[self.index]
            self.label.configure(text=self.choice)
        elif choice:
            if choice in self.choices:
                self.index = self.choices.index(choice)
                self.choice = choice
                self.label.configure(text=self.choice)
            else:
                raise (ValueError, f"值 {choice} 在选项中不存在：{self.choices}")

# markdown文本框 ==============================================================
class MarkdownText(Module):
    def __init__(self, root, width, height):
        super().__init__()
        self.frame = tk.Frame(root, bg=col_dict['bg'])

        f = tk.Frame(self.frame, bg=col_dict['main'], width=width-10, height=height-10)
        f.pack(padx=5, pady=5)
        self.bg_frame = tk.Frame(f, bg=col_dict['main'], width=width-20, height=height-20)
        self.bg_frame.pack(padx=5, pady=5)

        self.text = Text(self.bg_frame, bg=col_dict['main'], fg=col_dict['text'], width=width, height=height, font_size=10,
                         family="Fusion Pixel 12px Mono zh_hans")
        self.text.pack(fill='both', expand=True)
        # all_fonts = font.families()
        # for i in all_fonts:
        #     if 'Pixel' in i:
        #         print(i)

        # italic 斜体
        self.text.text.tag_configure("T0", font=("Fusion Pixel 12px Mono zh_hans", 12, "bold"), foreground=col_dict['text'])
        self.text.text.tag_configure("T1", font=("Fusion Pixel 12px Mono zh_hans", 11, "bold"), foreground=col_dict['text'])
        self.text.text.tag_configure("T2", font=("Fusion Pixel 12px Mono zh_hans", 10, "bold"), foreground=col_dict['text'])
        self.text.text.tag_configure("q", font=("Fusion Pixel 12px Mono zh_hans", 9), foreground=col_dict['light'])
        self.text.text.tag_configure("p", font=("Fusion Pixel 12px Mono zh_hans", 9), foreground=col_dict['text'])
        self.text.text.tag_configure("p_b", font=("Fusion Pixel 12px Mono zh_hans", 9, "bold"), foreground=col_dict['text'])
        self.text.text.tag_configure("t", font=("Fusion Pixel 12px Mono zh_hans", 9),
                                     foreground=col_dict['text'], background=col_dict['bg'],
                                     spacing1=1, spacing2=1, spacing3=1)
        self.text.text.tag_configure("c", font=("Fusion Pixel 12px Mono zh_hans", 8, "bold"),
                                     foreground=col_dict['light'], background=col_dict['bg'],
                                     spacing1=2, spacing2=1, spacing3=2)
        self.main_frame = self.frame

    def add_page(self, content, tag='p'):
        if type(content) is list:
            for c, b in content:
                if b:
                    self.text.insert(tk.END, f"{c}", 'p_b')
                else:
                    self.text.insert(tk.END, f"{c}", 'p')
            self.text.insert(tk.END, f"\n", 'p')
        else:
            self.text.insert(tk.END, f"{content}\n", tag)

    def update(self, content):
        self.text.delete(0.0, 'end')
        res = parse_markdown(content)

        for i in res:
            # print(i)
            p_type = i['type']
            content = i['content']

            level = i.get('level')
            if level and p_type == 'heading':
                if level - 1 > 2:
                    level = 3
                tag = f'T{level - 1}'
            elif p_type == 'code_block':
                tag = 'c'
                content = f"[{i['language']}]\n\n{content}\n"
            elif p_type == 'quote':
                tag = 'q'
                content = f">>> {content}\n"
            else:
                c0, c1 = content.count('|'), (content.count('\n') + 1)
                if c0 % c1 == 0 and c0 > 0:
                    tag = f't'
                    content = format_markdown_table(content)
                    content = f"\n{content}\n"
                else:
                    content = parse_markdown_bold(content)
                    tag = f'p'

            self.add_page(content, tag=tag)

# 工作流组件 ===================================================================
class WorkFlow(Module):
    def __init__(self, root, width, height):
        super().__init__()
        self.root = root
        self.width = width
        self.height = height
        self.canvas = tk.Canvas(root, bg=col_dict['bg'], highlightthickness=0, width=width, height=height)
        for x in range(0, width, 20):
            self.canvas.create_line(x, 0, x, height, width=1, fill='black', tags="grid")
        for y in range(0, height, 20):
            self.canvas.create_line(0, y, width, y, width=1, fill='black', tags="grid")

        self.canvas.bind("<B1-Motion>", self._move)  # 左键拖动
        self.canvas.bind("<ButtonPress-1>", self._click)  # 左键按下

        self.wfm = None
        self.nodes_config = None

        self.zero_point = 0, 0
        self.start_x = 0  # 鼠标按下起点X
        self.start_y = 0  # 鼠标按下起点Y
        # 新增：拖动锁，防止高频事件冲突
        self.is_dragging = False
        self.run_test = False
        self.module_init_pos = {}  # 保存所有模块的初始位置

        self.main_frame = self.canvas

        self.module = []
        self.input_dict = {}

        run_button = Button(self.canvas, text='run', command=self.run, stroke=True)
        run_button.place(x=5, y=610)
        _, h = get_frame_size(run_button.main_frame, run_button.main_frame)
        run_button.place(x=5, y=height - h - 5)

        self.selected_index = None

    def bind_WorkFlowNodeManager(self, wfm):
        def shoe_wfm():
            self.wfm.place(x=self.width - 300, y=0)

        def hid_wfm():
            self.wfm.place_forget()

        self.wfm = wfm

        wfm_b = Button(self.canvas, text="🧬", font_size=12, stroke=True, switch=True, command=[hid_wfm, shoe_wfm])
        wfm_b.place(x=5, y=5)

    def selected(self, index):
        self.selected_index = index
        if self.wfm:
            module = self.module[self.selected_index]
            if not self.wfm.mode_button.mode:
                show_list = [[i] for i in module.output_list]
                self.wfm.output_node_tabel.update(show_list)
                self.wfm.output_index_l.configure(text=module.title)
                code = f"{inspect.getsource(module.function)}"

                i = 0
                for i in range(len(code.split('\n')[0])):
                    if code.split('\n')[0][i] != ' ':
                        break

                self.wfm.code_text.delete(0.0, 'end')
                for line in code.split('\n'):
                    self.wfm.code_text.insert('end', f"{line[i:]}\n")

            else:
                show_list = [[i] for i in module.input_list]
                self.wfm.input_node_tabel.update(show_list)
                self.wfm.input_index = module.index
                self.wfm.input_index_l.configure(text=module.title)
                code = inspect.getsource(module.function)

                i = 0
                for i in range(len(code.split('\n')[0])):
                    if code.split('\n')[0][i] != ' ':
                        break

                self.wfm.code_text.delete(0.0, 'end')
                for line in code.split('\n'):
                    self.wfm.code_text.insert('end', f"{line[i:]}\n")

    def run(self):
        if not self.run_test:
            threading.Thread(target=self._run).start()
            self.run_test = True

    def _move(self, e):
        # 防止重复回调
        if self.is_dragging:
            return
        self.is_dragging = True

        try:
            dx = e.x - self.start_x
            dy = e.y - self.start_y

            for i, module in enumerate(self.module):
                # 安全校验：模块存在才移动
                if module not in self.module_init_pos:
                    continue
                orig_x, orig_y = self.module_init_pos[module]

                module.main_frame.place(x=orig_x + dx, y=orig_y + dy)

            # 安全重绘
            self.draw_connect()
        except Exception as e:
            # 打印错误但不崩溃
            print(f"拖动异常: {e}")
        finally:
            # 释放锁
            self.is_dragging = False

    def _click(self, e):
        # 记录鼠标按下的初始坐标
        self.start_x = e.x
        self.start_y = e.y
        # 保存所有模块【按下瞬间】的位置
        self.module_init_pos = {}
        for module in self.module:
            try:
                x = module.main_frame.winfo_x()
                y = module.main_frame.winfo_y()
                self.module_init_pos[module] = (x, y)
            except:
                continue

    def bind_module(self, *modules):
        self.module.extend(modules)
        for i, module in enumerate(modules):
            module.bind_screen(self, i)

    def draw_line(self, points=[], tags=None):
        if len(points) >= 2:
            self.canvas.create_line(
                *points,
                smooth=True,  # 关键：自动平滑所有控制点
                width=6, fill=col_dict['bg'], tags=tags
            )
            self.canvas.create_line(
                # -50, 100,  # 起点
                # 150, 30,  # 控制点1
                # 250, 170,  # 控制点2
                # 350, 50,  # 控制点3
                # 450, 120,  # 终点
                *points,
                smooth=True,  # 关键：自动平滑所有控制点
                width=2, fill=col_dict['light'], tags=tags
            )

    def _get_node_loc(self, module_index, node_name):
        return get_relative_pos(self.module[module_index].nodes[node_name]['node'], self.canvas)

    def add_node(self, node_config):
        index = len(self.module)

        self.nodes_config['modules'].append(node_config)

        # 实例化
        wfn = WorkFlowNode(self.main_frame, config=node_config['function_arges'])
        wfn.place(**node_config['place_config'])

        # 绑定
        self.module.append(wfn)
        wfn.bind_screen(self, index)
        self.wfm.order_table.update(
            [(i, module['function_arges']['title']) for i, module in enumerate(self.nodes_config['modules'])])

    def remove_node(self, index):
        self.nodes_config['modules'].pop(index)
        self.module[index].main_frame.destroy()
        self.module.pop(index)

        for module in self.module:
            module.index = self.module.index(module)

        self.wfm.order_table.update(
            [(i, module['function_arges']['title']) for i, module in enumerate(self.nodes_config['modules'])])

        for edge in copy.deepcopy(self.nodes_config['edge']):
            print(index, edge)
            if index in edge:
                self.remove_connect(*edge)

    def add_connect(self, module_index_0, node_name_0, module_index_1, node_name_1):
        edge = (module_index_0, node_name_0, module_index_1, node_name_1)
        if edge not in self.nodes_config['edge']:
            self.nodes_config['edge'].append((module_index_0, node_name_0, module_index_1, node_name_1))
            self.draw_connect(module_index_0)

    def remove_connect(self, module_index_0, node_name_0, module_index_1, node_name_1):
        edge = module_index_0, node_name_0, module_index_1, node_name_1
        while edge in self.nodes_config['edge']:
            self.nodes_config['edge'].remove((module_index_0, node_name_0, module_index_1, node_name_1))
        self.canvas.delete(f"{module_index_0}{node_name_0}{module_index_1}{node_name_1}")

    def draw_connect(self, index=None):
        # self.canvas.delete(tk.ALL)
        for module_index_0, node_name_0, module_index_1, node_name_1 in self.nodes_config['edge']:
            if index and index != module_index_0 and index != module_index_1:
                continue
            try:
                self.canvas.delete(f"{module_index_0}{node_name_0}{module_index_1}{node_name_1}")
                self.main_frame.update()
                x0, y0 = self._get_node_loc(module_index=module_index_0, node_name=node_name_0)
                x0 += 2
                y0 += 2
                x1, y1 = self._get_node_loc(module_index=module_index_1, node_name=node_name_1)
                x1 += 2
                y1 += 2
                d = ((x0 - x1) ** 2 + (y1 - y0) ** 2) ** (1 / 2)
                self.draw_line(points=[x0, y0, x0 + d / 4, y0, x1 - d / 4, y1, x1, y1], tags=f"{module_index_0}{node_name_0}{module_index_1}{node_name_1}")
            except: pass

    def _run(self):
        if not self.nodes_config:
            return
        node_connect_list = self.nodes_config['edge']

        self.input_dict = {}
        input_dict = {}
        for i, module in enumerate(self.module):
            # try:
                if not node_connect_list:
                    pass
                elif i not in [module_index_0 for module_index_0, _, _, _ in node_connect_list] + [module_index_1 for _, _, module_index_1, _ in node_connect_list]:
                    continue
                input_data = {}
                if module.text_input:
                    for title, text in module.text_input.items():
                        input_data[title] = text.get(0.0, 'end')

                # 如果需要输入
                # 更换节点顺序之后，连接索引没有同步更新导致参数读取为空，待修复 ❌
                if module.input_list:
                    for k in module.input_list:
                        if (i, k) not in input_dict:
                            continue
                        input_data[k] = input_dict[(i, k)]
                        del input_dict[(i, k)]
                    output_data = module.run_function(**input_data)
                    if output_data:
                        for k, v in output_data.items():
                            self.input_dict[(i, k)] = output_data
                    if output_data:
                        for k, v in output_data.items():
                            for a, b, c, d in self.nodes_config['edge']:
                                if (a, b) == (i, k):
                                    if (i, k) in input_dict:
                                        input_dict[(c, d)] = v
                                        self.input_dict[(c, d)] = v
                # 如果不需要输入（起点节点）
                else:
                    output_data = module.run_function()
                    # 记录输出供给前端节点按钮查看
                    if output_data:
                        for k, v in output_data.items():
                            self.input_dict[(i, k)] = v
                    for k, v in output_data.items():
                        # 遍历所有有连接的节点
                        for a, b, c, d in self.nodes_config['edge']:
                            # 判断是否是当前节点
                            if (a, b) == (i, k):
                                # 给下一节点记录输入值方便读取
                                input_dict[(c, d)] = v
                                # 记录输入供给前端节点按钮查看
                                self.input_dict[(c, d)] = v
                if not self.nodes_config['edge']:
                    break
            # except KeyError as e:
            #     MessageBox(title="Run Error", message=f"Module {module.title}: {e} is a necessary input.", mode='error')
            # except Exception as e:
            #     module.main_frame.configure(bg=col_dict['error'])
            #     MessageBox(title="Run Error", message=f"Module {module.title}: {e}", mode='error')
            #     break

        self.run_test = False

    # 加载工作流
    def load_flow(self, nodes_config):
        self.nodes_config = nodes_config["node_config"]
        value_config = nodes_config["value_config"]

        # 实例化模块
        wfn_l = []
        modules = self.nodes_config['modules']
        for index in range(len(self.nodes_config['modules'])):
            module = modules[index]
            title = module['function_arges']['title']
            wfn = WorkFlowNode(self.main_frame, config=self.nodes_config["modules"][index]['function_arges'], value_config=value_config[title] if value_config else {})
            wfn.place(**module['place_config'])
            wfn_l.append(wfn)

        # 绑定模块到节点背景
        self.bind_module(*wfn_l)

        for edge in self.nodes_config['edge']:
            # 添加连接
            self.add_connect(*edge)

        self.draw_connect()  # 绘制连接

    def update_config(self):
        self.nodes_config = self.export_flow()['node_config']

    def export_flow(self):
        node_config = {
            "modules": [],
            "edge": []
        }
        for i, module in enumerate(self.module):
            title = module.title
            function = module.function
            text_input = module.text_input
            file_input = module.file_input
            img_input = module.img_input
            value_input = module.value_input
            x, y = get_relative_pos(module.main_frame, self.canvas)
            function_arges = {
                "title": title,
                "function": function,
                "text_input": list(text_input.keys()),
                "file_input": list(file_input.keys()),
                "img_input": list(img_input.keys()),
                "value_input": list(value_input.keys())
            }
            place_config = {"x": x, "y": y}
            node_config['modules'].append({"function_arges": function_arges, "place_config": place_config})
        node_config['edge'] = self.nodes_config['edge']

        values = {}
        for module in self.module:
            data = {"value_input": {}, "img_input": {}, "text_input": {}, "file_input": {}}
            print(module.title)
            for node_name, (value_entry, value_choice) in module.value_input.items():
                value = value_entry.get()
                index, value_type = value_choice.get()
                print(f"{node_name}: {value},{value_type}")
                data["value_input"][node_name] = (value, value_type)

            for node_name, (img_entry, _) in module.img_input.items():
                img_path = img_entry.get()
                print(f"{node_name}: {img_path}")
                data['img_input'][node_name] = img_path

            for node_name, text_text in module.text_input.items():
                text = text_text.get(0.0, 'end')
                print(f"{node_name}: {text}")
                data["text_input"][node_name] = text

            for node_name, file_entry in module.file_input.items():
                file_path = file_entry.get()
                print(f"{node_name}: {file_path}")
                data["file_input"][node_name] = file_path
            values[module.title] = data

        print(values)
        all_config = {
            "node_config": node_config,
            "value_config": values
        }
        return all_config

# 节点类
class WorkFlowNode(Module):
    def __init__(self, root, title="Node", config=None, value_config={}, function=None, text_input=[], file_input=[], img_input=[], value_input=[]):
        super().__init__()
        self.click_x, self.click_y = 0, 0
        self.screen = None
        self.index = None
        self.root = root
        self.is_moving = False

        if config:
            self.value_config = value_config
            self.title = config['title']
            function = config['function']
            input_list, output_list = get_func_structure(function)
            text_input, file_input, img_input, value_input = config['text_input'], config['file_input'], config['img_input'], config['value_input']
            self.input_list = [item for item in input_list if item not in text_input+file_input+img_input+value_input]
            self.output_list = output_list
            self.function = function
            self.text_input_l = text_input
            self.file_input_l = file_input
            self.img_input_l = img_input
            self.value_input_l = value_input
        else:
            self.title = title
            input_list, output_list = get_func_structure(function)
            self.input_list = [item for item in input_list if item not in text_input + file_input + img_input+value_input]
            self.output_list = output_list
            self.function = function
            self.text_input_l = text_input
            self.file_input_l = file_input
            self.img_input_l = img_input
            self.value_input_l = value_input

        width = 200
        height = 0
        self.width = width
        self.main_frame = tk.Frame(root, bg=col_dict['bg'], width=width, height=height)

        self.light_bg = tk.Frame(self.main_frame, bg=col_dict['bg'], width=width-6, height=height-6)
        self.light_bg.place(x=3, y=3)

        self.bg_f = tk.Frame(self.main_frame, bg=col_dict['main'], width=width-10, height=height-10)
        self.bg_f.bind("<B1-Motion>", self.move)  # 左键拖动
        self.bg_f.bind("<ButtonPress-1>", self._click)  # 左键按下
        self.bg_f.bind("<ButtonRelease-1>", self._release)  # 左键释放
        self.bg_f.place(x=5, y=5)

        self.title_l = Label(self.bg_f, text=self.title, font_size=8)
        self.title_l.place(x=5, y=5)
        self.title_l.bind("<B1-Motion>", self.move)  # 左键拖动
        self.title_l.bind("<ButtonPress-1>", self._click)  # 左键按下
        self.title_l.bind("<ButtonRelease-1>", self._release)  # 左键释放
        self.title_l.bind("<Double-Button-1>", self._d_click)  # 左键双击
        self.title_e = Entry(self.bg_f, font_size=8, width=10, stroke=True)
        self.title_e.bind("<Leave>", self._enter)  # 左键双击

        tk.Frame(self.bg_f, bg=col_dict['bg'], width=width, height=5).place(x=0, y=25)

        self._set_node_input()

    def _d_click(self, e):
        self.title_e.delete(0, 'end')
        self.title_e.insert(0, self.title)
        self.title_l.place_forget()
        self.title_e.place(x=5, y=5)

    def _enter(self, e):
        content = self.title_e.get()
        self.title_l.place(x=5, y=5)
        self.title_e.place_forget()

        self.title = content
        self.title_l.configure(text=content)

        self.screen.update_config()
        self.screen.wfm.order_table.update([(i, module['function_arges']['title']) for i, module in enumerate(self.screen.nodes_config['modules'])])

    def _set_node_input(self):
        def click_l(name):
            if name in self.input_list:
                self.index, name
                self.screen.wfm.input_index = self.index
                self.screen.wfm.input_node = name
                self.screen.wfm.output_index_l.configure(text=self.title)

            elif name in self.output_list:
                self.screen.wfm.output_index = self.index
                self.screen.wfm.output_node = name
                self.screen.wfm.input_index_l.configure(text=self.title)
            self.screen.wfm.update()

            x, y = get_mouse_pos(self.main_frame)
            if (self.index, name) in self.screen.input_dict:
                content = self.screen.input_dict[(self.index, name)]
                win = Toplevel(title=f'{name}', w=233, h=236)
                win.root.geometry(f'+{x}+{y}')
                if type(content) is bytes:
                    Label(win.screen_frame, text='Type: <Bytes>', font_size=10).place(x=5, y=5)
                    text = Text(win.screen_frame, width=20, height=6)
                    text.place(x=5, y=30)
                    text.insert('end', f"{content[:50]}")
                elif isinstance(content, Image.Image):
                    Label(win.screen_frame, text='Type: <Image>', font_size=10).place(x=5, y=5)
                    self._mid_img_label = ImgLabel(win.screen_frame, size=(203, 152))
                    self._mid_img_label.place(x=5, y=30)
                    self._mid_img_label.update(content)
                else:
                    Label(win.screen_frame, text=f'Type: {type(content)}', font_size=10).place(x=5, y=5)
                    text = Text(win.screen_frame, width=20, height=6)
                    text.place(x=5, y=30)
                    if content:
                        if f"{content}".replace('\n', ''):
                            text.insert(0.0, f"{content}")

        self.nodes = {}
        y = 35
        for i_t in self.input_list:
            node_l = Button(self.bg_f, text=i_t, font_size=6, command=click_l, command_args=i_t)
            node_l.place(x=3, y=y)
            node = tk.Frame(self.main_frame, bg=col_dict['light'], width=5, height=5)
            node.place(x=0, y=y + 10)
            y += 15
            self.nodes[i_t] = {'label': node_l, "node": node}

        y = 35
        for o_t in self.output_list:
            node_l = Button(self.bg_f, text=o_t, font_size=6, command=click_l, command_args=o_t)
            node_l.place(x=0, y=y)
            node = tk.Frame(self.main_frame, bg=col_dict['light'], width=5, height=5)
            node.place(x=self.width - 5, y=y + 10)

            w, _ = get_frame_size(self.main_frame, frame=node_l.main_frame)
            node_l.place(x=self.width - w - 11, y=y)
            y += 15
            self.nodes[o_t] = {'label': node_l, "node": node}

        # 高度补齐
        y = 35 + max(len(self.input_list), len(self.output_list)) * 15

        # 值输入框 choice_box 会被挡住，故仅记录位置然后在最后再实例化
        self.value_input = {}
        choice_box_place = {}
        for v in self.value_input_l:
            choice_box_place[v] = {'label': (0, y)}
            y += 15
            choice_box_place[v]['entry'] = (5, y)
            choice_box_place[v]['choice_box'] = (122, y-1)
            y += 25

        print(f"value_config: =========================================\n{self.value_config}")

        # 文本输入框
        self.text_input = {}

        for t in self.text_input_l:
            text_l = Label(self.bg_f, text=t, font_size=6)
            text_l.place(x=0, y=y)
            text = Text(self.bg_f, width=int(self.width / 9), height=3, font_size=8, spacing1=1, spacing2=1, spacing3=1)
            y += 15
            text.place(x=5, y=y)

            self.text_input[t] = text
            y += 45

        # 文件输入框
        def file_open(title):
            file_path = filedialog.askopenfilename(
                title='选择文件',
            )
            if file_path:
                self.file_input[title].delete(0, 'end')
                self.file_input[title].insert(0, file_path)

        self.file_input = {}
        for f in self.file_input_l:
            text_l = Label(self.bg_f, text=f, font_size=6)
            text_l.place(x=0, y=y)
            y += 15
            entry = Entry(self.bg_f, width=int(self.width / 9 - 4), font_size=8)
            entry.place(x=5, y=y)
            w, _ = get_frame_size(self.main_frame, frame=entry.main_frame)
            button = Button(self.bg_f, text='...', stroke=True, font_size=5, command=file_open, command_args=f)
            button.place(x=5 + w - 3, y=y)
            self.file_input[f] = entry

            y += 30

        # 图片输入框
        def img_open(title):
            file_path = filedialog.askopenfilename(
                filetypes=[("图片文件", "*.png;*.jpg")]
            )
            if file_path:
                self.img_input[title].delete(0, 'end')
                self.img_input[title].insert(0, file_path)
                img_l.update(file_path)

        self.img_input = {}
        for i in self.img_input_l:
            text_l = Label(self.bg_f, text=i, font_size=6)
            text_l.place(x=0, y=y)
            y += 15
            entry = Entry(self.bg_f, width=int(self.width / 9 - 4), font_size=8)
            entry.place(x=5, y=y)
            w, _ = get_frame_size(self.main_frame, frame=entry.main_frame)
            button = Button(self.bg_f, text='...', stroke=True, font_size=5, command=img_open, command_args=i)
            button.place(x=5 + w - 3, y=y)
            y += 30
            img_l = ImgLabel(self.bg_f, size=(self.width-20, self.width-20), img=None)
            img_l.place(x=5, y=y)
            self.img_input[i] = (entry, img_l)

            y += self.width - 15

        for k, item in choice_box_place.items():
            v = k
            x, y_ = item['label']
            text_l = Label(self.bg_f, text=v, font_size=6)
            text_l.place(x=x, y=y_)
            x, y_ = item['entry']
            entry = Entry(self.bg_f, width=int(self.width / 9 - 4 - 5), font_size=8)
            entry.place(x=x, y=y_)
            x, y_ = item['choice_box']
            choice_box = ChoiceBox(self.bg_f, width=3, choices=['str', 'int', 'flo'], font_size=6)
            choice_box.place(x=x, y=y_)
            self.value_input[v] = (entry, choice_box)


        # 录入预设数值
        if self.value_config:
            text_value = self.value_config['text_input']
            for t in self.text_input_l:
                text = self.text_input[t]
                text.insert(0.0, text_value[t])

            file_value = self.value_config['file_input']
            for f in self.file_input_l:
                entry = self.file_input[f]
                entry.insert(0, file_value[f])

            img_value = self.value_config['img_input']
            for i in self.img_input_l:
                entry, img_l = self.img_input[i]
                img_path = img_value[i]
                img_l.update(img_path)
                entry.insert(0, img_path)

            value_value = self.value_config['value_input']
            for k, item in choice_box_place.items():
                v = k
                entry, choice_box = self.value_input[v]
                entry.insert(0, value_value[k][0])
                choice_box.set(choice=value_value[k][1])

        self.main_frame.configure(height=y+15)
        self.light_bg.configure(height=y+10)
        self.bg_f.configure(height=y+5)

    def bind_screen(self, screen, index):
        self.screen = screen
        self.index = index

    def _click(self, e):
        # 防止重复点击
        if self.is_moving:
            return
        self.click_x, self.click_y = e.x, e.y
        self.main_frame.configure(bg=col_dict['light'])

        self.screen.selected(self.index)
        self.screen.wfm.select_node = self.index

    def _release(self, e):
        try:
            if self.screen:
                self.screen.draw_connect()
        except:
            pass
        self.click_x, self.click_y = 0, 0
        self.main_frame.configure(bg=col_dict['bg'])

    def move(self, e):
        # 锁：防止高频事件叠加
        if self.is_moving:
            return
        self.is_moving = True

        # try:
        locx, locy = get_relative_pos(self.main_frame, self.root)
        x, y = e.x, e.y
        self.main_frame.place(x=locx + x - self.click_x, y=locy + y - self.click_y)

        # 安全重绘连线（防止screen未绑定）
        if self.screen:
            self.screen.draw_connect(self.index)
        # except Exception as e:
        #     # 打印错误但不崩溃
        #     print(f"模块拖动异常: {e}")
        # finally:

        # 释放锁
        self.is_moving = False

    def run_function(self, **input_data):
        # if len(set(self.input_list) & set(input_data.keys())) != len(self.input_list):
        #     raise (ValueError, "输入输出不对应")
        if self.function:
            # 用户值输入
            if self.value_input:
                for title, (value, choice_box) in self.value_input.items():
                    _, v_type = choice_box.get()
                    v = value.get()
                    if v_type == 'int':
                        input_data[title] = int(v)
                    elif v_type == 'flo':
                        input_data[title] = float(v)
                    elif v_type == 'str':
                        input_data[title] = v
                    else:
                        input_data[title] = v
            # 用户文本输入
            if self.text_input:
                for title, text in self.text_input.items():
                    input_data[title] = text.get(0.0, 'end').strip()
            # 用户图片输入
            if self.img_input:
                for title, (entry, _) in self.img_input.items():
                    path = entry.get().strip()
                    if path:
                        input_data[title] = Image.open(path)
                    else:
                        input_data[title] = None
            # 用户文件输入
            if self.file_input:
                for title, entry in self.file_input.items():
                    path = entry.get().strip()
                    if path:
                        with open(path, mode='rb') as f:
                            input_data[title] = f.read()
                    else:
                        input_data[title] = None

            self.main_frame.configure(bg=col_dict['light'])
            if self.input_list or self.text_input:
                result = self.function(**input_data)
            else:
                result = self.function()
            self.main_frame.configure(bg=col_dict['bg'])
            return result
        return None

# 节点管理器类
class WorkFlowNodeManager(Module):
    def __init__(self, root, height=300):
        super().__init__()
        self.wf = None
        self.height = height
        self.main_frame = tk.Frame(root, bg=col_dict['bg'], width=300, height=height)
        self.bg_f = tk.Frame(self.main_frame, bg=col_dict['main'], width=290, height=self.height - 10)
        self.bg_f.place(x=5, y=5)

        self.select_node = None

        self._edge()
        self._code()
        self._order()

    def update(self):
        self.input_node_l.configure(text=self.input_node)
        self.output_node_l.configure(text=self.output_node)
        selected_edge = self.output_index, self.output_node, self.input_index, self.input_node
        if selected_edge in self.wf.nodes_config['edge']:
            self.add_remove_b.label.configure(text="Connect")
            self.edge_line.place(x=105, y=42)
        else:
            self.add_remove_b.label.configure(text="Disconnect")
            self.edge_line.place_forget()

    def _order(self):
        Label(self.bg_f, text='Order', font_size=8).place(x=5, y=390)

        self.order_table = Table(self.bg_f, {'ID': 50, 'Title': 210}, height=7)
        self.order_table.bind("<ButtonRelease-1>", self.order_table_click)
        self.order_table.place(x=5, y=415)

        add_b = Button(self.bg_f, text='+', command=self.add_b)
        add_b.place(x=270, y=420)
        del_b = Button(self.bg_f, text='-', command=self.del_b)
        del_b.place(x=270, y=445)
        up_b = Button(self.bg_f, text='⬆️', command=self.up_b)
        up_b.place(x=270, y=470)
        down_b = Button(self.bg_f, text='⬇️', command=self.down_b)
        down_b.place(x=270, y=495)

    def order_table_click(self, e):
        # 获取当前选中的项
        selected_item = self.order_table.table.selection()
        if not selected_item:
            return  # 没有选中项，直接返回
        # 获取选中项的 ID
        item_id = selected_item[0]
        row_index = self.order_table.table.index(item_id)
        # 获取项的所有列值
        values = self.order_table.table.item(item_id, "values")
        self.select_node = int(values[0])

    def add_b(self):
        print('add_b')

    def del_b(self):
        print('del_b')

    def up_b(self):
        print('up_b')

    def down_b(self):
        print('down_b')

    def _code(self):
        Label(self.bg_f, text='Code', font_size=8).place(x=5, y=250)
        self.code_text = Text(self.bg_f, width=46, height=8, font_size=9, wrap=tk.NONE, family='Fusion Pixel 12px Mono zh_hans',
                              spacing1=1, spacing2=1, spacing3=1)
        self.code_text.text.tag_configure("变量/标识符", font=("Fusion Pixel 12px Mono zh_hans", 8), foreground=col_dict['text'])
        self.code_text.text.tag_configure("关键字", font=("Fusion Pixel 12px Mono zh_hans", 8, "bold"), foreground='orange')
        self.code_text.text.tag_configure("运算符", font=("Fusion Pixel 12px Mono zh_hans", 8), foreground="white")
        self.code_text.place(x=5, y=270)

    def _edge(self):
        Label(self.bg_f, text='Edge', font_size=8).place(x=5, y=5)

        self.mode_button = Button(self.bg_f, text='Switch', width=29, switch=True, stroke=True, command=[(self._click_0,), (self._click_1,)], font_size=8)
        self.mode_button.place(x=5, y=125)

        self.output_index = None
        self.output_node = None
        self.output_node_tabel = Table(self.bg_f, {'output_name': 135}, height=3)
        self.output_node_tabel.bind("<ButtonRelease-1>", self._output_click)
        self.output_node_tabel.place(x=5, y=25)
        self.output_mode_f = tk.Frame(self.bg_f, bg=col_dict['light'], width=137, height=5)
        self.output_mode_f.place(x=5, y=115)

        self.input_index = None
        self.input_node = None
        self.input_node_tabel = Table(self.bg_f, {'input_name': 135}, height=3)
        self.input_node_tabel.bind("<ButtonRelease-1>", self._input_click)
        self.input_node_tabel.place(x=145, y=25)
        self.input_mode_f = tk.Frame(self.bg_f, bg=col_dict['bg'], width=137, height=5)
        self.input_mode_f.place(x=145, y=115)

        node_bg = tk.Frame(self.bg_f, bg=col_dict['bg'], width=280, height=90)
        node_bg.place(x=5, y=157)
        self.output_index_l = Label(node_bg, text='OutputNode', width=11)
        self.output_index_l.place(x=5, y=5)
        self.input_index_l = Label(node_bg, text='InputNode', width=11, anchor='e')
        self.input_index_l.place(x=5, y=5)
        w, _ = get_frame_size(self.main_frame, self.input_index_l.main_frame)
        self.input_index_l.place(x=275 - w, y=5)

        self.output_node_l = Label(node_bg, text='Node', anchor='e', width=10, font_size=8)
        self.output_node_l.place(x=5, y=36)
        output_node = tk.Frame(node_bg, width=5, height=5, bg=col_dict['light'])
        output_node.place(x=105, y=41)

        self.input_node_l = Label(node_bg, text='Node', anchor='w', width=10, font_size=8)
        self.input_node_l.place(x=275 - 96, y=36)
        input_node = tk.Frame(node_bg, width=5, height=5, bg=col_dict['light'])
        input_node.place(x=265 - 96, y=41)

        self.edge_line = tk.Frame(node_bg, width=64, height=3, bg=col_dict['light'])

        self.add_remove_b = Button(node_bg, text='Edge', width=22, stroke=True, command=self._add_remove)
        self.add_remove_b.place(x=0, y=56)

    def _add_remove(self):
        selected_edge = self.output_index, self.output_node, self.input_index, self.input_node
        if selected_edge in self.wf.nodes_config['edge']:
            self.wf.remove_connect(*selected_edge)
        else:
            self.wf.add_connect(*selected_edge)
        self.update()

    def bind_screen(self, wf):
        self.wf = wf
        self.order_table.update([(i, module['function_arges']['title']) for i, module in enumerate(self.wf.nodes_config['modules'])])

    def _input_click(self, e):
        selected_item = self.input_node_tabel.table.selection()
        if not selected_item:
            return

        item_id = selected_item[0]
        row_index = self.input_node_tabel.table.index(item_id)
        values = self.input_node_tabel.table.item(item_id, "values")
        self.input_node = values[0]

        if self.wf:
            for in_i, in_node_name, out_i, out_node_name in self.wf.nodes_config['edge']:
                if out_node_name == self.input_node and in_node_name == self.output_node:
                    self.edge_line.place(x=105, y=42)
                    break
                else:
                    self.edge_line.place_forget()

        self.update()

    def _output_click(self, e):
        selected_item = self.output_node_tabel.table.selection()
        if not selected_item:
            return

        item_id = selected_item[0]
        row_index = self.output_node_tabel.table.index(item_id)
        values = self.output_node_tabel.table.item(item_id, "values")
        self.output_node = values[0]

        if self.wf:
            for in_i, in_node_name, out_i, out_node_name in self.wf.nodes_config['edge']:
                if out_node_name == self.input_node and in_node_name == self.output_node:
                    self.edge_line.place(x=105, y=42)
                    break
                else:
                    self.edge_line.place_forget()

        self.update()

    def _click_0(self):
        self.output_mode_f.configure(bg=col_dict['light'])
        self.input_mode_f.configure(bg=col_dict['bg'])

    def _click_1(self):
        self.output_mode_f.configure(bg=col_dict['bg'])
        self.input_mode_f.configure(bg=col_dict['light'])

# 判断鼠标是否在指定容器内或容器的子元素内
def in_frame(frame):
    widget = frame.winfo_containing(frame.winfo_pointerx(), frame.winfo_pointery())
    return widget.winfo_toplevel() == frame if widget else False

# 判断焦点是否在指定容器内或容器的子元素内
def is_focus(frame):
    focus = frame.focus_get()
    return focus is not None and focus.winfo_toplevel() == frame

# 获取鼠标在整个屏幕的坐标 (x, y)
def get_mouse_pos(frame):
    return frame.winfo_pointerx(), frame.winfo_pointery()

# 获取容器的占用的真实像素大小
def get_frame_size(root, frame):
    root.update()
    return frame.winfo_width(), frame.winfo_height()

# 获取容器位于屏幕的坐标
def get_pos(frame):
    return frame.winfo_rootx(), frame.winfo_rooty()

def get_relative_pos(widget: tk.Widget, reference_widget: tk.Widget) -> tuple[int, int]:
    """
    获取 widget 相对于 reference_widget (0,0) 点的相对坐标
    :param widget: 目标控件
    :param reference_widget: 参考控件（非父级也可以）
    :return: (相对x, 相对y)
    """
    # 控件绝对坐标（屏幕左上角为原点）
    x1 = widget.winfo_rootx()
    y1 = widget.winfo_rooty()
    # 参考控件绝对坐标
    x2 = reference_widget.winfo_rootx()
    y2 = reference_widget.winfo_rooty()
    # 计算相对坐标
    return x1 - x2, y1 - y2

# 获取函数的输入输出
def get_func_structure(func) -> tuple[list[str], list[str]]:
    """
    永久固定函数名
    不执行函数 | 无副作用 | 适配你的固定返回格式：return {"key": var, ...}
    返回：(参数名列表, 字典键列表)
    """
    # ------------- 1. 获取参数（稳定可用，保留）-------------
    try:
        params = list(inspect.signature(func).parameters.keys())
    except:
        params = []

    # ------------- 2. 正则提取字典键（绝对可行，核心方案）-------------
    keys = []
    try:
        # 获取函数源码
        code = inspect.getsource(func)
        # 正则匹配 return { xxx } 中的所有双引号字符串键
        # 适配你的格式：{"user_input": user_input, ...}
        pattern = r'"([^"]+)"\s*:'
        keys = re.findall(pattern, code)
        # 去重（如果有重复键）+ 保留顺序
        keys = list(dict.fromkeys(keys))
    except:
        keys = []

    return params, keys

if __name__ == "__main__":
    def new():
        print('new')

    def path():
        print('path')

    win = Win(
        title='Main win',
        # 顶端菜单
        menu_config={
            "File": {"new": new},
            "Open": {"path": path}
        },
        page_config=['page1', 'page2'],
        w=1200, h=800
    )

    # # 副窗口
    # win_ = Toplevel(title='Toplevel test')

    # # 提醒弹窗
    # MessageBox(title="test", mode='pass')

    # # 确认弹窗
    # confirmation_box = ConfirmationBox(title="test", mode='reminder', message="确定要执行吗？")
    # result = confirmation_box.get_result()
    # print(result)

    # # 表格
    # table = Table(win.screen_frames["page1"], {'名字': 120, '状态': 100}, height=10)
    # table.place(x=5, y=5)
    #
    # table.append((1, 2))
    # table.append(('a', 'b'))
    # table.update([(1, 5), ('c', 'n')])
    # table.clear()

    # # 文本
    # label = Label(win.screen_frames["page2"], '测试')
    # label.place(x=150, y=50)

    # win.add_page("page3")
    #
    # win.del_page("page1")

    # # 按钮
    # def f0():
    #     print()
    #
    # def f1():
    #     print(choice_box.get())
    #
    # button = Button(win.screen_frame, '按钮测试', stroke=True, width=6, height=2, command=(f0, f1))
    # button.place(x=150, y=50)

    # # 切换按钮
    # def f0():
    #     print(0)
    #
    # def f1():
    #     print(1)
    #
    # button = Button(win.screen_frame, '按钮测试', stroke=True, width=6, height=2, command=[(f0, f1), (f1, f0)], switch=True)
    # button.place(x=150, y=50)

    # # 滑动条
    # scroll_bar = ScrollBar(win.screen_frame, win.screen_frame, num_range=(20, 230), length=200, width=25)
    # scroll_bar.place(x=5, y=5)

    # # 复选框
    # check_box = CheckBox(win.screen_frame, title="check_box")
    # check_box.place(x=5, y=5)

    # # 进度条
    # progress_bar = ProgressBar(win.screen_frame, title='test')
    # progress_bar.place(x=5, y=5)
    #
    # for i in range(50):
    #     progress_bar.update(i, 50)
    #     time.sleep(0.1)

    # 加载条
    # loading_bar = LoadingBar(win.screen_frames['page1'])
    # loading_bar.place(x=5, y=20)
    #
    # loading_bar.start()
    #
    # for i in range(100):
    #     time.sleep(0.1)
    #     win.root.update()
    #
    # loading_bar.done()

    # # 输入框
    # entry = Entry(win.screen_frame)
    # entry.place(x=5, y=5)

    # # 文本框
    # text = Text(win.screen_frame)
    # text.place(x=5, y=5)

    # # 菜单栏
    # def new():
    #     print('new')
    #
    # def delete():
    #     print('delete')
    # MenuWin({'new': new, 'delete': delete})

    # # 图片展示
    # img = Image.new('RGB', (80, 20), 'pink')
    # img_label = ImgLabel(win.screen_frames['page1'], img, size=(100, 100))
    # img_label.place(x=5, y=5)
    #
    # def update():
    #     img = Image.new('RGB', (random.randint(100, 200), random.randint(100, 200)), tuple([random.randint(0, 255) for _ in range(3)]))
    #     img_label.update(img)
    #
    #     win.root.after(500, update)
    #
    # update()

    # # 互斥复选框
    # option_box = OptionBox(win.screen_frames['page1'], ['选项1', '选项2', '选项3'], name_mode=True)
    # option_box.place(x=5, y=5)

    # # 选择框
    # choice_box = ChoiceBox(win.screen_frames['page1'], ['选项1', '选项2'])
    # choice_box.place(x=5, y=120)

#     # MD渲染器
#     md_b = MarkdownText(win.screen_frames['page1'], width=50, height=24)
#     md_b.place(x=5, y=5)
#
#     def t():
#         test_md = """# 一级标题 T0
# 这是普通段落，包含**加粗文本**和。
#
# | 表头1 | 表头2 | 表头3 |
# | ----- | ----- | ----- |
# | 普通单元格 | 加粗单元格 | 斜体单元格 |
#
# ```python
# def test():
#     # 多行代码块测试
#     print("hello world")
#     return True
# ```
# """
#         # 模拟流式更新
#         c = ''
#         for i in test_md:
#             c += i
#             try:
#                 md_b.update(c)
#                 win.root.update()
#                 time.sleep(0.05)
#             except: pass
#     threading.Thread(target=t).start()

    # 工作流画布

    # 实例化工作流画布
    wf = WorkFlow(win.screen_frames['page1'], width=1060, height=600)
    wf.place(x=5, y=5)

    # 模块函数
    def node_0_function(value_input=None, user_input=None, file_input=None, img_input=None):
        """
        输入定义的变量名会直接在模块中显示
        输出必须是字典格式，的键也会在模块中显示
        高度绑定的格式化要求不能改变，一个模块内的所有变量名不可重复
        """
        time.sleep(1)
        return {"value_input": value_input, "user_input": user_input, "file_input": file_input, "img_input": img_input}

    def node_1_function(input0=None):
        time.sleep(1)
        print(input0)
        return

    def node_2_function(input1=None, input2=None):
        time.sleep(1)
        if input1:
            print(type(input1), len(input1))
        if input2:
            print(type(input2), input2.size)
        return


    node_config = {
        "node_config": {
            "modules": [
                {
                    "function_arges": {
                        "title": "Node0",
                        "function": node_0_function,
                        "text_input": ["user_input"],
                        "file_input": ["file_input"],
                        "img_input": ["img_input"],
                        "value_input": ["value_input"]
                    },
                    "place_config": {"x": 20, "y": 80},
                },
                {
                    "function_arges": {
                        "title": "Node1",
                        "function": node_1_function,
                        "text_input": [],
                        "file_input": [],
                        "img_input": [],
                        "value_input": []
                    },
                    "place_config": {"x": 400, "y": 20},
                },
                {
                    "function_arges": {
                        "title": "Node2",
                        "function": node_2_function,
                        "text_input": [],
                        "file_input": [],
                        "img_input": [],
                        "value_input": []
                    },
                    "place_config": {"x": 400, "y": 160},
                }
            ],
            "edge": [
                (0, 'user_input', 1, 'input0'),
                (0, 'file_input', 2, 'input1'),
                (0, 'img_input', 2, 'input2')
            ]
        },
        "value_config": {
            'Node0': {'value_input': {'value_input': ('value_test', 'str')},
                      'img_input': {'img_input': r"F:\pixel\2.png"},
                      'text_input': {'user_input': 'text_input_test'},
                      'file_input': {'file_input': r"F:\pixel\2.png"}},
            'Node1': {'value_input': {},
                      'img_input': {},
                      'text_input': {},
                      'file_input': {}},
            'Node2': {'value_input': {},
                      'img_input': {},
                      'text_input': {},
                      'file_input': {}},
            'Node3': {'value_input': {},
                      'img_input': {},
                      'text_input': {},
                      'file_input': {}}}
    }
    # with open("test_workflow.pkl", "rb") as f:
    #     nodes_config = pickle.load(f)
    # 加载工作流
    wf.load_flow(node_config)

    # 添加节点
    add_node_config = {
        "function_arges": {
            "title": "Node3",
            "function": node_2_function,
            "text_input": [],
            "file_input": [],
            "img_input": [],
            "value_input": []
        },
        "place_config": {"x": 400, "y": 160},
    }

    # 创建管理器（必要显式调用）
    wfm = WorkFlowNodeManager(wf.canvas, height=wf.height)
    wfm.bind_screen(wf)

    wf.bind_WorkFlowNodeManager(wfm)

    # wf.add_node(add_node_config)
    # wf.remove_node(3)

    # 导出工作流
    workflow = wf.export_flow()
    print(workflow)
    with open("test_workflow.pkl", "wb") as f:
        pickle.dump(workflow, f)

    win.mainloop()