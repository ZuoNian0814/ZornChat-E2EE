import math

def hex_str(data: bytes, upper: bool = True, separator: str = " ") -> str:
    """
    将字节数据转换为十六进制字符串
    :param data: 输入的字节数据 (bytes)
    :param upper: 是否输出大写十六进制（默认True，匹配010Editor显示）
    :param separator: 字节分隔符（空=无分隔，空格=编辑器样式）
    :return: 十六进制可视化字符串
    """
    # 核心：bytes内置hex方法，高效转换
    hex_str = data.hex(sep=separator)
    return hex_str.upper() if upper else hex_str

def hex_bytes(hex_str: str, separator: str = " ") -> bytes:
    """
    将十六进制字符串反向转换回字节数据（配套 hex_str 函数使用）
    :param hex_str: 十六进制字符串（支持大小写、带分隔符）
    :param separator: 字符串中的分隔符（需和 hex_str 中的 separator 一致）
    :return: 原始字节数据
    """
    # 1. 移除所有分隔符（如空格）
    clean_str = hex_str.replace(separator, "")
    # 2. 解码为 bytes（内置方法，自动兼容大小写）
    return bytes.fromhex(clean_str)

class HexAnalyzer:
    def __init__(self, hex_str: str):
        self.raw_hex = hex_str.strip()
        self.data = self._hex_to_bytes()

    def _hex_to_bytes(self) -> bytes:
        try:
            clean_hex = self.raw_hex.replace(" ", "").replace("\n", "")
            return bytes.fromhex(clean_hex)
        except:
            return b""

    # 1. 大小
    def analyze_basic(self) -> dict:
        title = "大小"
        if not self.data:
            return {"title": title, "value": "无效数据", "note": "十六进制字符串格式错误"}

        size = len(self.data)
        kb_size = round(size / 1024, 2)
        value = f"{size}字节 / {kb_size}KB"
        note = "数据总长度，1KB=1024字节"
        return {"title": title, "value": value, "note": note}

    # 2. 类型
    def analyze_file_type(self) -> dict:
        title = "类型"
        if not self.data:
            return {"title": title, "value": "无效数据", "note": "无法检测文件头"}

        magic_map = {
            b"\xFF\xD8\xFF": "JPG图片",
            b"\x89PNG": "PNG图片",
            b"GIF8": "GIF图片",
            b"PK\x03\x04": "ZIP压缩包",
            b"%PDF-": "PDF文档",
            b"MZ": "EXE程序",
            b"<?xml": "XML文件",
            b"#!": "脚本文件",
        }
        file_type = "未知二进制"
        for magic, name in magic_map.items():
            if self.data.startswith(magic):
                file_type = name
                break

        if b"\x00" not in self.data and len(self.data) < 10000:
            file_type = "纯文本"

        header = self.data[:16].hex(" ").upper()
        value = file_type
        note = f"文件头十六进制：{header}"
        return {"title": title, "value": value, "note": note}

    # 3. 文本
    def analyze_readable_text(self, encoding="utf-8") -> dict:
        title = "文本"
        if not self.data:
            return {"title": title, "value": "无数据", "note": "无法解码"}

        try:
            text = self.data.decode(encoding, errors="ignore")
            text = "".join([c for c in text if c.isprintable() or c in "\n\r\t"])
            value = text[:200] + "..." if len(text) > 200 else text
            note = f"使用 {encoding} 解码，已过滤乱码与不可打印字符"
        except:
            value = "解码失败"
            note = "不支持当前编码格式"
        return {"title": title, "value": value, "note": note}

    # 4. 空字节
    def analyze_null_bytes(self) -> dict:
        title = "空字节"
        if not self.data:
            return {"title": title, "value": "无数据", "note": "无法统计"}

        total = len(self.data)
        null_count = self.data.count(b"\x00")
        ratio = round(null_count / total * 100, 1) if total else 0
        judge = "二进制文件(图片/程序)" if ratio > 5 else "文本文件"

        value = f"{null_count}个 / {ratio}%"
        note = f"空字节占比高=二进制文件，低=文本文件 | 判断结果：{judge}"
        return {"title": title, "value": value, "note": note}

    # 5. 搜索
    def analyze_search(self, keyword: str, is_hex: bool = False) -> dict:
        title = "搜索"
        if not self.data:
            return {"title": title, "value": "无数据", "note": "无法搜索"}

        try:
            if is_hex:
                target = bytes.fromhex(keyword.replace(" ", ""))
                search_type = "十六进制"
            else:
                target = keyword.encode("utf-8")
                search_type = "文本"

            if target in self.data:
                pos = self.data.index(target)
                value = f"第{pos}字节"
                note = f"搜索类型：{search_type} | 关键词：{keyword}"
            else:
                value = "未找到"
                note = f"搜索类型：{search_type} | 关键词：{keyword}"
        except:
            value = "搜索失败"
            note = "关键词格式错误"
        return {"title": title, "value": value, "note": note}

    # 6. 二进制
    def analyze_binary_bits(self, limit: int = 8) -> dict:
        title = "二进制"
        if not self.data:
            return {"title": title, "value": "无数据", "note": "无法解析"}

        bits = []
        for i, b in enumerate(self.data[:limit]):
            bits.append(f"[{i:02d}] {b:02X}={bin(b)[2:].zfill(8)}")
        value = " | ".join(bits)
        note = f"展示前 {limit} 个字节的二进制底层数据"
        return {"title": title, "value": value, "note": note}

    # 7. 熵值
    def analyze_entropy(self) -> dict:
        title = "熵值"
        if not self.data or len(self.data) < 4:
            return {"title": title, "value": "数据过短", "note": "无法计算熵值"}

        freq = [0] * 256
        length = len(self.data)
        for b in self.data:
            freq[b] += 1

        entropy = 0.0
        for count in freq:
            if count == 0:
                continue
            p = count / length
            entropy -= p * math.log(p)

        entropy = round(entropy, 2)
        if entropy > 7.0:
            res = "高混乱度 → 加密/压缩文件"
        elif entropy > 3.0:
            res = "中等混乱度 → 普通二进制文件"
        else:
            res = "低混乱度 → 纯文本文件"

        value = f"{entropy}"
        note = res
        return {"title": title, "value": value, "note": note}

if __name__ == '__main__':
    # 1. 输入你的十六进制字符串（来自010Editor）
    test_hex = "48 65 6C 6C 6F 20 57 6F 72 6C 64 00 00 FF D8 FF E0"

    # 2. 初始化分析器
    analyzer = HexAnalyzer(test_hex)

    # 3. 调用所有分析方法，输出标准格式
    import json
    print("="*60)
    # 遍历所有分析方法
    methods = [
        analyzer.analyze_basic,
        analyzer.analyze_file_type,
        analyzer.analyze_readable_text,
        analyzer.analyze_null_bytes,
        analyzer.analyze_binary_bits,
        analyzer.analyze_entropy,
    ]
    for func in methods:
        result = func()
        # 格式化打印JSON（美观易读）
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("-"*60)

    # 单独调用搜索功能（传关键词）
    search_result = analyzer.analyze_search("Hello")
    print(json.dumps(search_result, ensure_ascii=False, indent=2))