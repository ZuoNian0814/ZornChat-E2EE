import hashlib
import hmac

# 内部工具函数
def _to_bytes(data):
    if isinstance(data, str):
        return data.encode("utf-8")
    if isinstance(data, bytes):
        return data
    raise TypeError("仅支持str/bytes")

# ------------------------------ 哈希算法类（统一 name + description） ------------------------------
class Md5Hash:
    name = "Md5Hash"
    description = "MD5哈希算法，32位十六进制，适用于文件校验、非安全场景"
    @staticmethod
    def compute(data):
        return hashlib.md5(_to_bytes(data)).hexdigest()

class Sha1Hash:
    name = "Sha1Hash"
    description = "SHA1哈希算法，40位十六进制，适用于文件校验、非安全场景"
    @staticmethod
    def compute(data):
        return hashlib.sha1(_to_bytes(data)).hexdigest()

class Sha224Hash:
    name = "Sha224Hash"
    description = "SHA224哈希算法，SHA2家族轻量安全算法"
    @staticmethod
    def compute(data):
        return hashlib.sha224(_to_bytes(data)).hexdigest()

class Sha256Hash:
    name = "Sha256Hash"
    description = "SHA256哈希算法，主流安全加密，用于密码、签名、证书"
    @staticmethod
    def compute(data):
        return hashlib.sha256(_to_bytes(data)).hexdigest()

class Sha384Hash:
    name = "Sha384Hash"
    description = "SHA384哈希算法，高安全SHA2系列算法"
    @staticmethod
    def compute(data):
        return hashlib.sha384(_to_bytes(data)).hexdigest()

class Sha512Hash:
    name = "Sha512Hash"
    description = "SHA512哈希算法，超高安全SHA2系列算法"
    @staticmethod
    def compute(data):
        return hashlib.sha512(_to_bytes(data)).hexdigest()

# class Sha512_224Hash:
#     name = "Sha512_224Hash"
#     description = "SHA512/224哈希算法，SHA2截断变体算法"
#     @staticmethod
#     def compute(data):
#         return hashlib.sha512_224(_to_bytes(data)).hexdigest()
#
# class Sha512_256Hash:
#     name = "Sha512_256Hash"
#     description = "SHA512/256哈希算法，SHA2截断变体算法"
#     @staticmethod
#     def compute(data):
#         return hashlib.sha512_256(_to_bytes(data)).hexdigest()

class Sha3_224Hash:
    name = "Sha3_224Hash"
    description = "SHA3-224哈希算法，新一代抗量子安全算法"
    @staticmethod
    def compute(data):
        return hashlib.sha3_224(_to_bytes(data)).hexdigest()

class Sha3_256Hash:
    name = "Sha3_256Hash"
    description = "SHA3-256哈希算法，新一代抗量子安全算法"
    @staticmethod
    def compute(data):
        return hashlib.sha3_256(_to_bytes(data)).hexdigest()

class Sha3_384Hash:
    name = "Sha3_384Hash"
    description = "SHA3-384哈希算法，新一代抗量子安全算法"
    @staticmethod
    def compute(data):
        return hashlib.sha3_384(_to_bytes(data)).hexdigest()

class Sha3_512Hash:
    name = "Sha3_512Hash"
    description = "SHA3-512哈希算法，新一代抗量子安全算法"
    @staticmethod
    def compute(data):
        return hashlib.sha3_512(_to_bytes(data)).hexdigest()

class Shake128Hash:
    name = "Shake128Hash"
    description = "SHAKE128可变长输出哈希算法，SHA3衍生算法"
    @staticmethod
    def compute(data, length=32):
        return hashlib.shake_128(_to_bytes(data)).hexdigest(length)

class Shake256Hash:
    name = "Shake256Hash"
    description = "SHAKE256可变长输出哈希算法，SHA3衍生算法"
    @staticmethod
    def compute(data, length=64):
        return hashlib.shake_256(_to_bytes(data)).hexdigest(length)

class Blake2sHash:
    name = "Blake2sHash"
    description = "BLAKE2s轻量高速哈希算法，适合嵌入式/移动端"
    @staticmethod
    def compute(data):
        return hashlib.blake2s(_to_bytes(data)).hexdigest()

class Blake2bHash:
    name = "Blake2bHash"
    description = "BLAKE2b高性能哈希算法，适合服务器/桌面端"
    @staticmethod
    def compute(data):
        return hashlib.blake2b(_to_bytes(data)).hexdigest()

class HmacMd5Hash:
    name = "HmacMd5Hash"
    description = "HMAC-MD5带密钥消息认证码，带密钥校验"
    @staticmethod
    def compute(data, key):
        return hmac.new(_to_bytes(key), _to_bytes(data), hashlib.md5).hexdigest()

class HmacSha1Hash:
    name = "HmacSha1Hash"
    description = "HMAC-SHA1带密钥消息认证码，带密钥校验"
    @staticmethod
    def compute(data, key):
        return hmac.new(_to_bytes(key), _to_bytes(data), hashlib.sha1).hexdigest()

class HmacSha256Hash:
    name = "HmacSha256Hash"
    description = "HMAC-SHA256带密钥消息认证码，主流安全接口签名"
    @staticmethod
    def compute(data, key):
        return hmac.new(_to_bytes(key), _to_bytes(data), hashlib.sha256).hexdigest()

class HmacSha512Hash:
    name = "HmacSha512Hash"
    description = "HMAC-SHA512带密钥消息认证码，高安全接口签名"
    @staticmethod
    def compute(data, key):
        return hmac.new(_to_bytes(key), _to_bytes(data), hashlib.sha512).hexdigest()

# ------------------------------ 你要的核心导航格式（完全一致） ------------------------------
Map_list = [
    Md5Hash,
    Sha1Hash,
    Sha224Hash,
    Sha256Hash,
    Sha384Hash,
    Sha512Hash,
    # Sha512_224Hash,
    # Sha512_256Hash,
    Sha3_224Hash,
    Sha3_256Hash,
    Sha3_384Hash,
    Sha3_512Hash,
    Shake128Hash,
    Shake256Hash,
    Blake2sHash,
    Blake2bHash,
    HmacMd5Hash,
    HmacSha1Hash,
    HmacSha256Hash,
    HmacSha512Hash
]

Map = {i.name: [i.description, i] for i in Map_list}

if __name__ == '__main__':
    # 测试数据
    test_data = b"Hello, World!"
    test_key = b"my_secret_key"

    # 遍历所有哈希
    for name, (desc, cls) in Map.items():
        print(name, "->", desc)
        try:
            print('无密钥：', cls.compute(test_data))
        except TypeError:
            print('有密钥：', cls.compute(test_data, test_key))