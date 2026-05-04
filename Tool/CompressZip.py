import lz4.frame               # pip install lz4
import snappy                  # pip install python-snappy
import zstandard as zstd       # pip install zstandard
import zlib
import gzip
import bz2
import lzma
import zipfile
import io

# ==============================================
# 1. zlib 压缩（标准库 | DEFLATE算法 | 最通用）
# ==============================================
class ZlibCompressor:
    """
    【zlib压缩】算法：DEFLATE
    优点：速度快、兼容性拉满、内置无依赖
    缺点：压缩率中等
    场景：网络传输、通用数据压缩
    """
    name = "zlib"
    description = "DEFLATE算法，速度快、兼容性拉满、内置无依赖，压缩率中等，适用于网络传输、通用数据压缩"

    def compress(self, data: bytes, level: int = 6) -> bytes:
        # level: 1(最快)~9(最高压缩) 默认6
        return zlib.compress(data, level=level)

    def decompress(self, data: bytes) -> bytes:
        return zlib.decompress(data)


# ==============================================
# 2. gzip 压缩（标准库 | Gzip格式 | 兼容文件）
# ==============================================
class GzipCompressor:
    """
    【gzip压缩】算法：DEFLATE
    优点：兼容.gz文件、内置、通用
    缺点：比zlib多文件头
    场景：生成gzip压缩文件、数据存储
    """
    name = "gzip"
    description = "DEFLATE算法，兼容.gz文件、内置、通用，比zlib多文件头，适用于生成gzip压缩文件、数据存储"

    def compress(self, data: bytes, level: int = 6) -> bytes:
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=level) as f:
            f.write(data)
        return buf.getvalue()

    def decompress(self, data: bytes) -> bytes:
        buf = io.BytesIO(data)
        with gzip.GzipFile(fileobj=buf, mode='rb') as f:
            return f.read()


# ==============================================
# 3. bz2 压缩（标准库 | BZIP2 | 高压缩率）
# ==============================================
class Bz2Compressor:
    """
    【bz2压缩】算法：BZIP2
    优点：压缩率高于zlib、内置
    缺点：压缩/解压速度慢
    场景：磁盘存储、追求高压缩率
    """
    name = "bz2"
    description = "BZIP2算法，压缩率高于zlib、内置，压缩/解压速度慢，适用于磁盘存储、追求高压缩率"

    def compress(self, data: bytes, level: int = 9) -> bytes:
        # level: 1~9 默认9(最高压缩)
        return bz2.compress(data, compresslevel=level)

    def decompress(self, data: bytes) -> bytes:
        return bz2.decompress(data)


# ==============================================
# 4. lzma 压缩（标准库 | LZMA/XZ | 超高压缩率）
# ==============================================
class LzmaCompressor:
    """
    【lzma压缩】算法：LZMA2/XZ
    优点：压缩率极高、内置
    缺点：速度最慢、消耗内存高
    场景：超大文件、极限压缩
    """
    name = "lzma"
    description = "LZMA2/XZ算法，压缩率极高、内置，速度最慢、消耗内存高，适用于超大文件、极限压缩"

    def compress(self, data: bytes, level: int = 6) -> bytes:
        # level: 0~9 默认6
        return lzma.compress(data, preset=level)

    def decompress(self, data: bytes) -> bytes:
        return lzma.decompress(data)


# ==============================================
# 5. zip 压缩（标准库 | ZIP归档 | 单文件压缩）
# ==============================================
class ZipCompressor:
    """
    【zip压缩】格式：ZIP单文件归档
    优点：兼容所有系统、内置
    缺点：压缩率一般、有归档开销
    场景：生成zip包、跨平台兼容
    """
    name = "zip"
    description = "ZIP单文件归档格式，兼容所有系统、内置，压缩率一般、有归档开销，适用于生成zip包、跨平台兼容"

    def compress(self, data: bytes, level: int = 6) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=level) as f:
            f.writestr("data", data)
        return buf.getvalue()

    def decompress(self, data: bytes) -> bytes:
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf, 'r') as f:
            return f.read(f.namelist()[0])


# ==============================================
# 6. lz4 压缩（第三方 | 极速压缩 | 大数据专用）
# ==============================================
class Lz4Compressor:
    """
    【lz4压缩】算法：LZ4
    优点：速度极快、接近内存拷贝速度
    缺点：压缩率低
    场景：实时数据、大数据、高性能服务
    """
    name = "lz4"
    description = "LZ4算法，速度极快、接近内存拷贝速度，压缩率低，适用于实时数据、大数据、高性能服务"

    def compress(self, data: bytes, level: int = 0) -> bytes:
        if not lz4: raise ImportError("请安装：pip install lz4")
        return lz4.frame.compress(data, compression_level=level)

    def decompress(self, data: bytes) -> bytes:
        if not lz4: raise ImportError("请安装：pip install lz4")
        return lz4.frame.decompress(data)


# ==============================================
# 7. snappy 压缩（第三方 | 谷歌 | 超高速）
# ==============================================
class SnappyCompressor:
    """
    【snappy压缩】算法：Snappy(谷歌)
    优点：速度极快、稳定性强、大数据生态标配
    缺点：压缩率低
    场景：Hadoop、Spark、实时流处理
    """
    name = "snappy"
    description = "Snappy(谷歌)算法，速度极快、稳定性强、大数据生态标配，压缩率低，适用于Hadoop、Spark、实时流处理"

    def compress(self, data: bytes) -> bytes:
        if not snappy: raise ImportError("请安装：pip install python-snappy")
        return snappy.compress(data)

    def decompress(self, data: bytes) -> bytes:
        if not snappy: raise ImportError("请安装：pip install python-snappy")
        return snappy.decompress(data)


# ==============================================
# 8. zstd 压缩（第三方 | Facebook | 速度/压缩率平衡）
# ==============================================
class ZstdCompressor:
    """
    【zstd压缩】算法：Zstandard(Facebook)
    优点：压缩率高+速度快、完美平衡
    缺点：需第三方库
    场景：现代存储、传输、通用最优解
    """
    name = "zstd"
    description = "Zstandard(Facebook)算法，压缩率高+速度快、完美平衡，需第三方库，适用于现代存储、传输、通用最优解"

    def compress(self, data: bytes, level: int = 3) -> bytes:
        if not zstd: raise ImportError("请安装：pip install zstandard")
        return zstd.compress(data, level=level)

    def decompress(self, data: bytes) -> bytes:
        if not zstd: raise ImportError("请安装：pip install zstandard")
        return zstd.decompress(data)


# ====================== 压缩算法 导航映射（和加密类格式完全一致） ======================
Map_list = [
    ZlibCompressor,
    GzipCompressor,
    Bz2Compressor,
    LzmaCompressor,
    ZipCompressor,
    Lz4Compressor,
    SnappyCompressor,
    ZstdCompressor
]
Map = {i.name: [i.description, i] for i in Map_list}

# ======================== 统一测试：所有压缩/解压算法验证 ========================
if __name__ == '__main__':
    # 测试用大字节数据（重复文本提高压缩效果）
    # choice = [b"abcdef", b'qwer', b'wasd1234', b'jkli', b'nmba']
    # original_data = b''.join([random.choice(choice) for i in range(1000)])
    original_data = b"python"

    from EnDecode import Base64
    from PIL import  Image
    from io import BytesIO

    base64 = Base64()

    img = Image.open(r"F:\pixel\0.png")
    byte_buffer = BytesIO()
    img.save(byte_buffer, format="PNG")
    img_bytes = byte_buffer.getvalue()
    original_data = base64.encode(img_bytes)

    original_size = len(original_data)
    print(f"原始数据大小：{original_size} 字节\n")

    # 压缩器列表（标准库默认启用，第三方注释即可）
    compressors = [
        (ZlibCompressor(), "zlib"),
        (GzipCompressor(), "gzip"),
        (Bz2Compressor(), "bz2"),
        (LzmaCompressor(), "lzma"),
        (ZipCompressor(), "zip"),
        (Lz4Compressor(), "lz4"),
        (SnappyCompressor(), "snappy"),
        (ZstdCompressor(), "zstd"),
    ]

    # 遍历测试所有算法
    for compressor, name in compressors:
        try:
            # 压缩
            compressed = compressor.compress(original_data)
            # 解压
            decompressed = compressor.decompress(compressed)
            # 验证
            success = original_data == decompressed
            ratio = (1 - len(compressed) / original_size) * 100
            # 输出结果
            print(f"【{name}】")
            print(f"  描述：{compressor.description}")
            print(f"  压缩后：{len(compressed)} 字节 | 压缩率：{ratio:.1f}%")
            print(f"  验证结果：{'✅ 成功' if success else '❌ 失败'}")
        except Exception as e:
            print(f"【{name}】❌ 失败：{str(e)}\n")