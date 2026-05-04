import Tool.EncryptionByte as EncryptionByte
import Tool.CompressZip as CompressZip
import secrets, json
from Tool.DirAnalys import DirAnalys
from Tool.EnDecode import Base64
import os

# 后续优化，对于在线字节包可以增加“收件人”输入，编码为字节后作为密钥加密文件头以增加身份安全性

# 字节打包
# 文件标识： 文件头*Zorn* (6字节) | 压缩方式声明 (10字节) | 加密文件字节
# 字节标识： 文件备注 (255字节) | 原字节
# 打包：拼接文件备注 + 加密方式+字节 → 加密 → 压缩 → 拼接文件头和压缩方式
# 解包：拆解文件头和压缩方式 → 解压缩 → 解密 → 拆解文件备注和字节

# 文件夹打包：
# 打包：拼接备注 + 配置长度声明(8字节) + 配置 + 每个文件[拼接位置声明+文件 → 加密 → 压缩] → 拼接文件头和压缩方式
# 解包：拆解文件头、压缩方式和分隔文件 → 每个文件逐个解压缩

base64 = Base64()

def fill_byte(data, length, fill:bytes=None):
    if len(data) > length:
        raise (ValueError, f'长度超出限制: {length}')
    if fill:
        while len(data) < length:
            data = b'0' + data
    else:
        data += b'^'
        while len(data) < length:
            fb = secrets.token_bytes(1)
            if fb == b'^':
                continue
            data += fb
    return data

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

class ZN:
    head = b"*Zorn*"
    head_length = 6
    zip_type_length = 10
    note_length = 255
    encryption_length = 10

    path_note_length = 4
    package_len_length = 18
    def pack(self, byte_content: bytes, data_note:dict={}, zip_type=None, encryption_steps: list[tuple] = [], mode=True):
        if mode:
            note_byte = json.dumps(data_note, ensure_ascii=False).encode()
            new_byte = fill_byte(note_byte, self.note_length) + byte_content
        else:
            new_byte = byte_content

        # ===================== 加密 =====================
        for encryption_name, key in encryption_steps:
            if type(key) is str:
                key = hex_bytes(key)
            if encryption_name in EncryptionByte.map_asymmetric:
                d, enc = EncryptionByte.map_asymmetric[encryption_name]
            else:
                d, enc = EncryptionByte.Map[encryption_name]
            encryption_item = enc()
            new_byte = encryption_item.encrypt(new_byte, key)
            print(f"[Pack]>>> 对文件执行{encryption_name}加密：{d} - 长度比{len(new_byte)/len(byte_content)*100:.2f}%")

        # ===================== 压缩 =====================
        zip_name_bype = fill_byte(b"", length=self.zip_type_length)
        if zip_type:
            d, zip_ = CompressZip.Map[zip_type]
            zip_item = zip_()
            # 压缩【拼接后的数据】，不是原始byte_content
            zip_byte = zip_item.compress(new_byte)
            print(
                f"[Pack]>>> 对文件执行{zip_type}压缩：{d} - 压缩比{(1 - len(zip_byte) / len(new_byte)) * 100:.2f}%")

            if 1 - len(zip_byte) / len(new_byte) <= 0:
                print("[Pack]>>> 压缩低于预期，自动舍弃")
            else:
                zip_name_bype = fill_byte(zip_type.encode(), length=self.zip_type_length)
                new_byte = zip_byte

        # 拼接头部（不动）
        if mode:
            new_byte = self.head + zip_name_bype + new_byte
        else:
            new_byte = self.head + new_byte
        print("[Pack]>>> 已完成文件打包")
        return new_byte

    def unpack(self, data: bytes, keys: list[tuple] = [], mode=True):
        head = data[:self.head_length]
        if self.head == head:
            print("[Unpack]>>> 确认包类型，符合要求")
        else:
            print("[Unpack]>>> 不可识别的包")
            return None

        if mode:
            zip_type = data[self.head_length: self.head_length + self.zip_type_length]
            file_data = data[self.head_length + self.zip_type_length:]
            new_data = file_data
        else:
            file_data = data[self.head_length:]
            new_data = file_data
            zip_type = b"^" + b"_" * (self.zip_type_length - 1)

        # ===================== 解压 =====================
        break_i = None
        for i, b in enumerate(zip_type[::-1]):
            if b == ord('^'):
                break
            break_i = (self.zip_type_length - (i + 2))
        if break_i is None:
            print("[Unpack]>>> 压缩方式解析错误")
            return None
        elif break_i == 0:
            print("[Unpack]>>> 未压缩的文件，直接解析")
        else:
            zip_name = zip_type[:break_i].decode()
            print(f"[Unpack]>>> 压缩方式: {zip_name}")

            d, zip_ = CompressZip.Map[zip_name]
            zip_item = zip_()
            new_data = zip_item.decompress(new_data)
            print(f"[Unpack]>>> 对文件执行{zip_type}解压缩 - 长度比{(len(new_data) / len(file_data)) * 100:.2f}%")

        # ===================== 解密 =====================
        for encryption_name, key in keys[::-1]:
            if type(key) is str:
                try:
                    key = hex_bytes(key)
                except:
                    key = base64.decode(key.encode())
            if encryption_name in EncryptionByte.map_asymmetric:
                d, enc = EncryptionByte.map_asymmetric[encryption_name]
            else:
                d, enc = EncryptionByte.Map[encryption_name]
            encryption_item = enc()
            # print(key)
            new_data = encryption_item.decrypt(new_data, key)
            print(f"[Unpack]>>> 对文件执行{encryption_name}解密 - 长度比{len(new_data)/len(file_data)*100:.2f}%")

        if mode:
            note_byte = new_data[:self.note_length]
            break_i = None
            for i, b in enumerate(note_byte[::-1]):
                if b == ord('^'):
                    break
                break_i = (self.note_length - (i + 2))
            if break_i is None or break_i < 0:
                print("[Unpack]>>> 包备注解析错误")
                return None
            note = json.loads(note_byte[:break_i].decode())
            content = new_data[self.note_length:]
        else:
            note = []
            content = new_data
        print(f'[Unpack]>>> 包备注信息：{note}')
        # print(f"[Unpack]>>> 内容：{content}")
        return note, content

    def pack_folder(self, dir_path: str, data_note: dict = {}, zip_type=None, encryption_steps: list[tuple] = [], save_path='save/encryption_folder.zornf'):
        da = DirAnalys(dir_path)
        path_dict = da.recursion_analys()
        all_file_data = []
        for file_path_note, file_path in path_dict.items():
            file_path_note_b = file_path_note.encode()
            path_note_length_b = fill_byte(str(len(file_path_note_b)).encode(), self.path_note_length, fill=b'0')
            note_b = path_note_length_b + file_path_note_b

            with open(file_path, mode='rb') as f:
                file_data = f.read()

                file_package = self.pack(file_data, data_note={}, zip_type=None, encryption_steps=[], mode=False)

                file_package_length_b = fill_byte(str(len(file_package)).encode(), self.package_len_length, fill=b'0')
                file_package = file_package_length_b + file_package

            onefile_data = note_b + file_package
            all_file_data.append(onefile_data)

        zip_name_bype = fill_byte(b"", length=self.zip_type_length)
        if zip_type:
            zip_name_bype = fill_byte(zip_type.encode(), length=self.zip_type_length)

        data = zip_name_bype + b''.join(all_file_data)

        all_data = self.pack(data, data_note, zip_type, encryption_steps)

        with open(save_path, mode='wb') as f:
            f.write(all_data)

        return all_data

    def unpack_folder(self, data: bytes, keys: list[tuple] = [], save_path='save'):
        data_note, all_data = self.unpack(data, keys)

        zip_type = all_data[: self.zip_type_length]
        file_data = all_data[self.zip_type_length:]

        break_i = None
        for i, b in enumerate(zip_type[::-1]):
            if b == ord('^'):
                break
            break_i = (self.zip_type_length - (i + 2))
        if break_i is None:
            print("[Unpack]>>> 压缩方式解析错误")
            return None
        elif break_i == 0:
            print("[Unpack]>>> 未压缩的文件，直接解析")
        else:
            zip_name = zip_type[:break_i].decode()
            print(f"[Unpack]>>> 压缩方式: {zip_name}")

        all_length = len(file_data)
        count = 0
        other = file_data
        while count < all_length:
            path_length_b, other = cut_bype(other, self.path_note_length)
            count += len(path_length_b)
            path_length = int(path_length_b.decode())

            path_b, other = cut_bype(other, path_length)
            count += len(path_b)
            path = path_b.decode()

            file_length_b, other = cut_bype(other, self.package_len_length)
            count += len(file_length_b)
            file_length = int(file_length_b.decode())

            file_b, other = cut_bype(other, file_length)
            count += len(file_b)

            _, output = self.unpack(file_b, keys=[], mode=False)

            save_file_path = os.path.join(save_path, path)

            # 自动创建目录
            dir_path = os.path.dirname(save_file_path)
            os.makedirs(dir_path, exist_ok=True)

            # 写入文件（二进制模式正确）
            with open(save_file_path, mode='wb') as f:
                f.write(output)

            # print(f"✅ 已保存：{save_file_path}")

        return data_note

def cut_bype(data, length):
    return data[:length], data[length:]

if __name__ == '__main__':
    zn = ZN()

    # result = zn.pack(b"test", "data_note", "zlib", encryption_steps=[('Blowfish', b'data_key')])
    #
    # with open("test.zorn", mode='wb') as f:
    #     f.write(result)
    #
    # content = zn.unpack(result, [('Blowfish', b'data_key')])

    # with open(r"F:\PythonProject\python_人工智能自动化\软件自动化智能体\Tool\test.zorn", mode='rb') as f:
    #     result = f.read()

    # result = zn.pack(b"test", [{"type": "测试文件"}], "zlib", encryption_steps=[("Blowfish", b"Zorn1027")])

    data = ['test_data']
    data = json.dumps(data, ensure_ascii=False).encode()

    aesGcm = EncryptionByte.Map['AES-GCM'][1]()
    key = aesGcm.generate_random_key()
    result = zn.pack(data, [{"type": "测试文件"}], "zstd", encryption_steps=[("AES-GCM", key)])

    # with open("test.bin", mode='wb') as f:
    #     f.write(result)
    #
    # with open(r"test.zorn", mode='rb') as f:
    #     result = f.read()

    note, content = zn.unpack(result, keys=[("AES-GCM", key)])

    # result = zn.pack_folder("_压缩测试文件夹", "data_note", "zlib", encryption_steps=[('Blowfish', b'data_key')])
    # print(result)
    #
    # result = zn.unpack_folder(result, keys=[('Blowfish', b'data_key')])
