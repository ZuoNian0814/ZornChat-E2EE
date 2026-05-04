import urllib.parse
import base64
import urllib.parse
import codecs
import string
import html
import xml.sax.saxutils

# ==================== 工具函数：统一类型处理 ====================
def _check_input(data):
    """校验输入必须为字符串或字节"""
    if not isinstance(data, (str, bytes)):
        raise ValueError("仅支持字符串(str)或字节(bytes)类型输入")

def _str_to_bytes(data: str) -> bytes:
    """字符串转UTF-8字节"""
    return data.encode("utf-8")

def _bytes_to_str(data: bytes) -> str:
    """字节转UTF-8字符串"""
    return data.decode("utf-8")

# ==============================================================================
# 1. Base64 编码（最常用：图片/接口传输/加密后数据）
# ==============================================================================
class Base64:
    """Base64编码：3字节转4字符，通用数据传输编码"""
    def encode(self, data):
        _check_input(data)
        if isinstance(data, str):
            return _bytes_to_str(base64.b64encode(_str_to_bytes(data)))
        return base64.b64encode(data)

    def decode(self, data):
        _check_input(data)
        try:
            if isinstance(data, str):
                return _bytes_to_str(base64.b64decode(_str_to_bytes(data)))
            return base64.b64decode(data)
        except Exception:
            raise ValueError("非法Base64编码")

# ==============================================================================
# 2. Base32 编码（验证码/文件校验，不区分大小写）
# ==============================================================================
class Base32:
    """Base32编码：适合不区分大小写的场景"""
    def encode(self, data):
        _check_input(data)
        if isinstance(data, str):
            return _bytes_to_str(base64.b32encode(_str_to_bytes(data)))
        return base64.b32encode(data)

    def decode(self, data):
        _check_input(data)
        try:
            if isinstance(data, str):
                return _bytes_to_str(base64.b32decode(_str_to_bytes(data)))
            return base64.b32decode(data)
        except Exception:
            raise ValueError("非法Base32编码")

# ==============================================================================
# 3. Hex / Base16 编码（十六进制：字节转明文，调试/哈希展示）
# ==============================================================================
class Hex:
    """十六进制编码：字节转16进制字符串，最常用调试编码"""
    def encode(self, data):
        _check_input(data)
        if isinstance(data, str):
            return _str_to_bytes(data).hex()
        return data.hex()

    def decode(self, data):
        _check_input(data)
        try:
            if isinstance(data, str):
                return bytes.fromhex(data)
            return bytes.fromhex(_bytes_to_str(data))
        except Exception:
            raise ValueError("非法十六进制编码")

# ==============================================================================
# 4. Base85 编码（比Base64更紧凑：IPv6/PDF/二进制传输）
# ==============================================================================
class Base85:
    """Base85(a85)编码：压缩率更高，空间占用更小"""
    def encode(self, data):
        _check_input(data)
        if isinstance(data, str):
            return _bytes_to_str(base64.b85encode(_str_to_bytes(data)))
        return base64.b85encode(data)

    def decode(self, data):
        _check_input(data)
        try:
            if isinstance(data, str):
                return _bytes_to_str(base64.b85decode(_str_to_bytes(data)))
            return base64.b85decode(data)
        except Exception:
            raise ValueError("非法Base85编码")

# ==============================================================================
# 5. URL 编码（百分号编码：网址参数/表单传输）
# ==============================================================================
class UrlEncode:
    """URL编码：处理中文/特殊字符，网页传输必备"""
    def encode(self, data):
        _check_input(data)
        if isinstance(data, str):
            return urllib.parse.quote(data)
        return urllib.parse.quote(_bytes_to_str(data)).encode("utf-8")

    def decode(self, data):
        _check_input(data)
        try:
            if isinstance(data, str):
                return urllib.parse.unquote(data)
            return urllib.parse.unquote(_bytes_to_str(data)).encode("utf-8")
        except Exception:
            raise ValueError("非法URL编码")

# ==============================================================================
# 6. Unicode 编码（\u 转中文：多语言文本传输）
# ==============================================================================
class Unicode:
    """Unicode编码：中文转\\uXXXX格式，跨平台文本兼容"""
    def encode(self, data):
        _check_input(data)
        if isinstance(data, str):
            return data.encode("unicode_escape").decode("utf-8")
        return data.decode("utf-8").encode("unicode_escape")

    def decode(self, data):
        _check_input(data)
        try:
            if isinstance(data, str):
                return codecs.decode(data, "unicode_escape")
            return codecs.decode(_bytes_to_str(data), "unicode_escape").encode("utf-8")
        except Exception:
            raise ValueError("非法Unicode编码")

# ==============================================================================
# 7. UTF-8 编码（全球通用字符集）
# ==============================================================================
class UTF8:
    """UTF-8编码：国际标准字符集，全语言兼容"""
    def encode(self, data):
        _check_input(data)
        if isinstance(data, str):
            return data.encode("utf-8")
        return data

    def decode(self, data):
        _check_input(data)
        try:
            if isinstance(data, bytes):
                return data.decode("utf-8")
            return data
        except Exception:
            raise ValueError("非法UTF-8编码")

# ==============================================================================
# 8. GBK 编码（中文国标字符集）
# ==============================================================================
class GBK:
    """GBK编码：中文系统专用编码"""
    def encode(self, data):
        _check_input(data)
        if isinstance(data, str):
            return data.encode("gbk")
        return data

    def decode(self, data):
        _check_input(data)
        try:
            if isinstance(data, bytes):
                return data.decode("gbk")
            return data
        except Exception:
            raise ValueError("非法GBK编码")

# ==============================================================================
# 9. Punycode 编码（域名编码：中文域名转英文）
# ==============================================================================
class Punycode:
    """Punycode编码：中文域名→英文域名，浏览器专用"""
    def encode(self, data):
        _check_input(data)
        if isinstance(data, str):
            return data.encode("idna").decode("utf-8")
        return data.decode("utf-8").encode("idna")

    def decode(self, data):
        _check_input(data)
        try:
            if isinstance(data, str):
                return _str_to_bytes(data).decode("idna")
            return data.decode("idna").encode("utf-8")
        except Exception:
            raise ValueError("非法Punycode编码")

# ==============================================================================
# 10. Quoted-Printable 编码（邮件编码：文本/附件）
# ==============================================================================
class QuotedPrintable:
    """QP编码：邮件专用，兼容老旧邮件系统"""
    def encode(self, data):
        _check_input(data)
        if isinstance(data, str):
            return codecs.encode(_str_to_bytes(data), "quoted-printable").decode("utf-8")
        return codecs.encode(data, "quoted-printable")

    def decode(self, data):
        _check_input(data)
        try:
            if isinstance(data, str):
                return codecs.decode(_str_to_bytes(data), "quoted-printable").decode("utf-8")
            return codecs.decode(data, "quoted-printable")
        except Exception:
            raise ValueError("非法Quoted-Printable编码")

# ==============================================================================
# 11. Base58 编码（区块链专用：比特币/钱包地址）
# ==============================================================================
class Base58:
    """Base58编码：无易混淆字符，数字货币专用"""
    ALPHABET = string.ascii_uppercase + string.ascii_lowercase + string.digits
    ALPHABET = ALPHABET.replace("0", "").replace("O", "").replace("I", "").replace("l", "")

    def encode(self, data):
        _check_input(data)
        if isinstance(data, str):
            data = _str_to_bytes(data)
        # 编码逻辑
        orig_len = len(data)
        data = int.from_bytes(data, "big")
        encode = ""
        while data > 0:
            data, idx = divmod(data, 58)
            encode = self.ALPHABET[idx] + encode
        # 补前导0
        return b"\x00" * orig_len + encode.encode() if isinstance(data, bytes) else "\x00" * orig_len + encode

    def decode(self, data):
        _check_input(data)
        try:
            if isinstance(data, str):
                data = _str_to_bytes(data)
            data = _bytes_to_str(data)
            orig_len = len(data) - len(data.lstrip(self.ALPHABET[0]))
            num = 0
            for c in data:
                num = num * 58 + self.ALPHABET.index(c)
            decoded = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
            decoded = b"\x00" * orig_len + decoded
            return decoded if isinstance(data, bytes) else _bytes_to_str(decoded)
        except Exception:
            raise ValueError("非法Base58编码")

# ==================== 复用工具函数（直接和上一轮代码共用） ====================
def _check_input(data):
    if not isinstance(data, (str, bytes)):
        raise ValueError("仅支持 str / bytes 类型")

def _to_bytes(data):
    return data.encode("utf-8") if isinstance(data, str) else data

def _to_str(data):
    return data.decode("utf-8") if isinstance(data, bytes) else data

# ==============================================================================
# 12. Base64URL 编码（JWT、URL安全版Base64，去掉+/=）
# ==============================================================================
class Base64URL:
    def encode(self, data):
        _check_input(data)
        b = _to_bytes(data)
        res = base64.urlsafe_b64encode(b).rstrip(b"=")
        return _to_str(res) if isinstance(data, str) else res

    def decode(self, data):
        _check_input(data)
        b = _to_bytes(data)
        b += b"=" * ((4 - len(b) % 4) % 4)
        res = base64.urlsafe_b64decode(b)
        return _to_str(res) if isinstance(data, str) else res

# ==============================================================================
# 13. ASCII85 / Adobe85 编码（PDF、PostScript专用）
# ==============================================================================
class ASCII85:
    def encode(self, data):
        _check_input(data)
        b = _to_bytes(data)
        res = base64.a85encode(b)
        return _to_str(res) if isinstance(data, str) else res

    def decode(self, data):
        _check_input(data)
        b = _to_bytes(data)
        res = base64.a85decode(b)
        return _to_str(res) if isinstance(data, str) else res

# ==============================================================================
# 14. UUEncode 编码（老式邮件/新闻组，仍兼容）
# ==============================================================================
class UUEncode:
    def encode(self, data):
        _check_input(data)
        b = _to_bytes(data)
        res = codecs.encode(b, "uu")
        return _to_str(res) if isinstance(data, str) else res

    def decode(self, data):
        _check_input(data)
        b = _to_bytes(data)
        res = codecs.decode(b, "uu")
        return _to_str(res) if isinstance(data, str) else res

# ==============================================================================
# 15. HTML 实体编码（< → &lt; > → &gt; 网页防注入）
# ==============================================================================
class HTMLEntity:
    def encode(self, data):
        _check_input(data)
        s = _to_str(data)
        res = html.escape(s)
        return res if isinstance(data, str) else res.encode("utf-8")

    def decode(self, data):
        _check_input(data)
        s = _to_str(data)
        res = html.unescape(s)
        return res if isinstance(data, str) else res.encode("utf-8")

# ==============================================================================
# 16. XML 实体编码（XML专用转义）
# ==============================================================================
class XMLEntity:
    def encode(self, data):
        _check_input(data)
        s = _to_str(data)
        res = xml.sax.saxutils.escape(s)
        return res if isinstance(data, str) else res.encode("utf-8")

    def decode(self, data):
        _check_input(data)
        s = _to_str(data)
        res = xml.sax.saxutils.unescape(s)
        return res if isinstance(data, str) else res.encode("utf-8")

# ==============================================================================
# 17. ROT13 编码（简单字母轮换，弱混淆）
# ==============================================================================
class ROT13:
    def encode(self, data):
        _check_input(data)
        s = _to_str(data)
        res = codecs.decode(s, "rot_13")
        return res if isinstance(data, str) else res.encode("utf-8")

    def decode(self, data):
        return self.encode(data)  # 加解密相同

# ==============================================================================
# 18. Bin 二进制编码（字节 → 01 字符串）
# ==============================================================================
class Binary:
    def encode(self, data):
        _check_input(data)
        b = _to_bytes(data)
        res = ''.join(f'{x:08b}' for x in b)
        return res if isinstance(data, str) else res.encode("utf-8")

    def decode(self, data):
        _check_input(data)
        s = _to_str(data).replace(" ", "")
        if not all(c in "01" for c in s):
            raise ValueError("非法二进制编码")
        if len(s) % 8 != 0:
            raise ValueError("二进制长度必须是8的倍数")
        res = bytes(int(s[i:i+8], 2) for i in range(0, len(s), 8))
        return res if isinstance(data, bytes) else _to_str(res)

# ==============================================================================
# 19. Oct 八进制编码
# ==============================================================================
class Octal:
    def encode(self, data):
        _check_input(data)
        b = _to_bytes(data)
        res = ''.join(f'{x:03o}' for x in b)
        return res if isinstance(data, str) else res.encode("utf-8")

    def decode(self, data):
        _check_input(data)
        s = _to_str(data).replace(" ", "")
        if len(s) % 3 != 0:
            raise ValueError("八进制长度必须为3的倍数")
        res = bytes(int(s[i:i+3], 8) for i in range(0, len(s), 3))
        return res if isinstance(data, bytes) else _to_str(res)

# ==============================================================================
# 20. UTF-16 LE / BE（Windows、部分系统编码）
# ==============================================================================
class UTF16:
    def encode(self, data, byteorder="le"):
        _check_input(data)
        enc = "utf-16-le" if byteorder == "le" else "utf-16-be"
        b = _to_str(data).encode(enc)
        return b if isinstance(data, bytes) else _to_str(b)

    def decode(self, data, byteorder="le"):
        _check_input(data)
        enc = "utf-16-le" if byteorder == "le" else "utf-16-be"
        b = _to_bytes(data)
        res = b.decode(enc)
        return res if isinstance(data, str) else res.encode("utf-8")

# ==============================================================================
# 21. UTF-32 LE / BE
# ==============================================================================
class UTF32:
    def encode(self, data, byteorder="le"):
        _check_input(data)
        enc = "utf-32-le" if byteorder == "le" else "utf-32-be"
        b = _to_str(data).encode(enc)
        return b if isinstance(data, bytes) else _to_str(b)

    def decode(self, data, byteorder="le"):
        _check_input(data)
        enc = "utf-32-le" if byteorder == "le" else "utf-32-be"
        b = _to_bytes(data)
        res = b.decode(enc)
        return res if isinstance(data, str) else res.encode("utf-8")

# ==============================================================================
# 22. Base91 编码（比Base64更紧凑，小众但实用）
# ==============================================================================
class Base91:
    ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!#$%&()*+,./:;<=>?@[]^_`{|}~\""

    def encode(self, data):
        _check_input(data)
        b = _to_bytes(data)
        if not b:
            return "" if isinstance(data, str) else b""

        buffer = 0
        bits = 0
        output = []
        for byte in b:
            buffer |= (byte & 0xFF) << bits
            bits += 8
            while bits >= 13:
                value = buffer & 0x1FFF
                if value > 88:
                    buffer >>= 13
                    bits -= 13
                else:
                    value = buffer & 0x3FFF
                    buffer >>= 14
                    bits -= 14
                output.append(self.ALPHABET[value % 91])
                output.append(self.ALPHABET[value // 91])
        if bits > 0:
            output.append(self.ALPHABET[buffer % 91])
            if bits > 7 or buffer > 90:
                output.append(self.ALPHABET[buffer // 91])

        result = ''.join(output)
        return result if isinstance(data, str) else result.encode('utf-8')

    def decode(self, data):
        _check_input(data)
        s = _to_str(data)
        if not s:
            return b"" if isinstance(data, bytes) else ""

        # 过滤非法字符
        s = ''.join(c for c in s if c in self.ALPHABET)
        buffer = 0
        bits = 0
        value = -1
        output = []

        for c in s:
            v = self.ALPHABET.index(c)
            if value == -1:
                value = v
            else:
                value += v * 91
                buffer |= value << bits
                bits += 13 if (value & 0x1FFF) > 88 else 14
                while bits >= 8:
                    output.append(buffer & 0xFF)
                    buffer >>= 8
                    bits -= 8
                value = -1
        if value != -1:
            output.append((buffer | (value << bits)) & 0xFF)

        result = bytes(output)
        # 关键修复：输入是字符串就转回UTF-8，输入是字节就返回字节
        return result if isinstance(data, bytes) else result.decode('utf-8', errors='replace')

# ==============================================================================
# 23. Punycode 完整版（兼容国际域名）
# 24. PercentEncode 严格编码（全字符URL编码）
# ==============================================================================
class StrictURLEncode:
    def encode(self, data):
        _check_input(data)
        s = _to_str(data)
        res = urllib.parse.quote_plus(s, safe="")
        return res if isinstance(data, str) else res.encode("utf-8")

    def decode(self, data):
        _check_input(data)
        s = _to_str(data)
        res = urllib.parse.unquote_plus(s)
        return res if isinstance(data, str) else res.encode("utf-8")

if __name__ == '__main__':
    # 测试数据
    test_str = "测试编码 123!@#米奇妙妙屋"
    test_bytes = b"test encoding 123!@#"

    print("=" * 60)
    print("1. Base64 编码测试")
    b64 = Base64()
    print("字符串编码:", b64.encode(test_str))
    print("字符串解码:", b64.decode(b64.encode(test_str)))
    print("字节编码:", b64.encode(test_bytes))
    print("字节解码:", b64.decode(b64.encode(test_bytes)))

    print("\n" + "=" * 60)
    print("2. Hex 十六进制测试")
    hex_code = Hex()
    print("字符串编码:", hex_code.encode(test_str))
    print("字符串解码:", hex_code.decode(hex_code.encode(test_str)))
    print("字节编码:", hex_code.encode(test_bytes))
    print("字节解码:", hex_code.decode(hex_code.encode(test_bytes)))

    print("\n" + "=" * 60)
    print("3. URL 编码测试")
    url = UrlEncode()
    print("字符串编码:", url.encode(test_str))
    print("字符串解码:", url.decode(url.encode(test_str)))

    print("\n" + "=" * 60)
    print("4. Unicode 编码测试")
    unicode_code = Unicode()
    print("字符串编码:", unicode_code.encode(test_str))
    print("字符串解码:", unicode_code.decode(unicode_code.encode(test_str)))

    print("\n" + "=" * 60)
    print("5. Punycode 域名编码测试")
    puny = Punycode()
    print("中文域名编码:", puny.encode("米奇妙妙屋.com"))
    print("域名解码:", puny.decode(puny.encode("米奇妙妙屋.com")))

    # 其余编码（Base32/Base85/UTF8/GBK/QP/Base58）用法完全一致
    print("\n其余编码调用方式完全相同，可直接替换类名使用！")

    test_str = "测试 <>& 米奇妙妙屋 123!@#"
    test_bytes = b"test <>& 123"

    # 示例1：Base64URL（JWT必用）
    b64u = Base64URL()
    print("=== Base64URL ===")
    print(b64u.encode(test_str))
    print(b64u.decode(b64u.encode(test_str)))

    # 示例2：HTML编码
    html_enc = HTMLEntity()
    print("\n=== HTML实体编码 ===")
    print(html_enc.encode(test_str))
    print(html_enc.decode(html_enc.encode(test_str)))

    # 示例3：二进制编码
    binary = Binary()
    print("\n=== Binary(01) ===")
    print(binary.encode(test_str))
    print(binary.decode(binary.encode(test_str)))

    # 示例4：ROT13
    rot13 = ROT13()
    print("\n=== ROT13 ===")
    print(rot13.encode(test_str))
    print(rot13.decode(rot13.encode(test_str)))

    # 示例5：Base91
    base91 = Base91()
    print("\n=== Base91 ===")
    print(base91.encode(test_str))
    print(base91.decode(base91.encode(test_str)))