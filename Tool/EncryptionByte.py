import secrets
import random
# 你的原有依赖导入（保留）
from Crypto.Random import get_random_bytes
from Crypto.Cipher import AES, DES, DES3, ARC4, ChaCha20, Salsa20, Blowfish
from Crypto.Util.Padding import pad, unpad

from cryptography.hazmat.primitives.asymmetric import rsa, padding, ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.serialization import load_der_public_key
from cryptography.hazmat.backends import default_backend
from Crypto.PublicKey import RSA as PycRSA
from Crypto.Cipher import PKCS1_OAEP

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec, x25519
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
import os

# -------------------------- 1. XOR 异或加密 --------------------------
class XorCipher:
    """
    【XOR加密】类型：流加密 | 密钥：任意长度
    优点：实现极简、速度极快、无依赖
    缺点：安全性极低，仅适合简单混淆
    场景：本地数据简单混淆、非敏感数据处理
    """
    name = "XOR"
    description = "流加密，实现极简、速度极快、无依赖，安全性极低，仅适合本地数据简单混淆、非敏感数据处理"

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        if not key:
            raise ValueError("密钥不能为空")
        return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        return self.encrypt(data, key)

    def generate_random_key(self) -> bytes:
        # 无长度限制，生成8-32字节合法随机密钥
        return secrets.token_bytes(random.randint(8, 32))


# -------------------------- 2. AES-CBC 加密 --------------------------
class AesCipher:
    """
    【AES-CBC加密】类型：分组加密 | 密钥：16字节
    优点：标准对称加密，安全性高
    缺点：CBC模式易受Padding Oracle攻击
    场景：通用数据加密、兼容旧系统
    """
    name = "AES-CBC"
    description = "分组加密，标准对称加密，安全性高，CBC模式易受Padding Oracle攻击，适用于通用数据加密、兼容旧系统"

    BLOCK_SIZE = 16
    KEY_SIZE = 16

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        if len(key) != self.KEY_SIZE:
            raise ValueError(f"AES密钥必须为{self.KEY_SIZE}字节")
        iv = get_random_bytes(self.BLOCK_SIZE)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        encrypted = cipher.encrypt(pad(data, self.BLOCK_SIZE))
        return iv + encrypted

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        if len(key) != self.KEY_SIZE:
            raise ValueError(f"AES密钥必须为{self.KEY_SIZE}字节")
        iv = data[:self.BLOCK_SIZE]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(data[self.BLOCK_SIZE:]), self.BLOCK_SIZE)
        return decrypted

    def generate_random_key(self) -> bytes:
        # 固定16字节合法密钥
        return secrets.token_bytes(self.KEY_SIZE)


# -------------------------- 3. DES-CBC 加密 --------------------------
class DesCipher:
    """
    【DES-CBC加密】类型：分组加密 | 密钥：8字节
    优点：历史悠久，兼容性极强
    缺点：密钥过短，已被破解，完全过时
    场景：仅用于老旧遗留系统兼容
    """
    name = "DES-CBC"
    description = "分组加密，历史悠久、兼容性极强，密钥过短已被破解完全过时，仅用于老旧遗留系统兼容"

    BLOCK_SIZE = 8
    KEY_SIZE = 8

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        if len(key) != self.KEY_SIZE:
            raise ValueError(f"DES密钥必须为{self.KEY_SIZE}字节")
        iv = get_random_bytes(self.BLOCK_SIZE)
        cipher = DES.new(key, DES.MODE_CBC, iv)
        encrypted = cipher.encrypt(pad(data, self.BLOCK_SIZE))
        return iv + encrypted

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        if len(key) != self.KEY_SIZE:
            raise ValueError(f"DES密钥必须为{self.KEY_SIZE}字节")
        iv = data[:self.BLOCK_SIZE]
        cipher = DES.new(key, DES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(data[self.BLOCK_SIZE:]), self.BLOCK_SIZE)
        return decrypted

    def generate_random_key(self) -> bytes:
        # 固定8字节合法密钥
        return secrets.token_bytes(self.KEY_SIZE)


# -------------------------- 4. 3DES-CBC 加密 --------------------------
class TripleDesCipher:
    """
    【3DES-CBC加密】类型：分组加密 | 密钥：24字节
    优点：DES升级版，兼容性好
    缺点：速度慢，安全性一般，已过时
    场景：金融/工业老旧系统兼容
    """
    name = "3DES-CBC"
    description = "分组加密，DES升级版、兼容性好，速度慢、安全性一般已过时，适用于金融/工业老旧系统兼容"

    BLOCK_SIZE = 8
    KEY_SIZE = 24

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        if len(key) != self.KEY_SIZE:
            raise ValueError(f"3DES密钥必须为{self.KEY_SIZE}字节")
        iv = get_random_bytes(self.BLOCK_SIZE)
        cipher = DES3.new(key, DES3.MODE_CBC, iv)
        encrypted = cipher.encrypt(pad(data, self.BLOCK_SIZE))
        return iv + encrypted

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        if len(key) != self.KEY_SIZE:
            raise ValueError(f"3DES密钥必须为{self.KEY_SIZE}字节")
        iv = data[:self.BLOCK_SIZE]
        cipher = DES3.new(key, DES3.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(data[self.BLOCK_SIZE:]), self.BLOCK_SIZE)
        return decrypted

    def generate_random_key(self) -> bytes:
        # 固定24字节合法密钥
        return secrets.token_bytes(self.KEY_SIZE)


# -------------------------- 5. RC4 加密 --------------------------
class Rc4Cipher:
    """
    【RC4加密】类型：流加密 | 密钥：任意长度
    优点：实现简单、速度快
    缺点：存在严重安全漏洞，已过时禁用
    场景：仅用于老旧系统兼容
    """
    name = "RC4"
    description = "流加密，实现简单、速度快，存在严重安全漏洞已过时禁用，仅用于老旧系统兼容"

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        if not key:
            raise ValueError("密钥不能为空")
        cipher = ARC4.new(key)
        return cipher.encrypt(data)

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        return self.encrypt(data, key)

    def generate_random_key(self) -> bytes:
        # 无长度限制，生成8-32字节合法随机密钥
        return secrets.token_bytes(random.randint(8, 32))


# -------------------------- 6. ChaCha20 加密 --------------------------
class ChaCha20Cipher:
    """
    【ChaCha20加密】类型：流加密 | 密钥：32字节
    优点：现代顶级安全、移动端/物联网性能极佳
    缺点：无明显缺点
    场景：移动端、弱网设备、现代应用加密
    """
    name = "ChaCha20"
    description = "流加密，现代顶级安全、移动端/物联网性能极佳，无明显缺点，适用于移动端、弱网设备、现代应用加密"

    KEY_SIZE = 32
    NONCE_SIZE = 12

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        if len(key) != self.KEY_SIZE:
            raise ValueError(f"ChaCha20密钥必须为{self.KEY_SIZE}字节")
        nonce = get_random_bytes(self.NONCE_SIZE)
        cipher = ChaCha20.new(key=key, nonce=nonce)
        return nonce + cipher.encrypt(data)

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        if len(key) != self.KEY_SIZE:
            raise ValueError(f"ChaCha20密钥必须为{self.KEY_SIZE}字节")
        nonce = data[:self.NONCE_SIZE]
        cipher = ChaCha20.new(key=key, nonce=nonce)
        return cipher.decrypt(data[self.NONCE_SIZE:])

    def generate_random_key(self) -> bytes:
        # 固定32字节合法密钥
        return secrets.token_bytes(self.KEY_SIZE)


# -------------------------- 7. AES-GCM 加密 --------------------------
class AesGcmCipher:
    """
    【AES-GCM加密】类型：分组加密 | 密钥：16/24/32字节
    优点：全球工业标准、防篡改、顶级安全、高性能
    缺点：无明显缺点
    场景：金融、通信、生产环境首选
    """
    name = "AES-GCM"
    description = "分组加密，全球工业标准、防篡改、顶级安全、高性能，无明显缺点，适用于金融、通信、生产环境首选"

    NONCE_SIZE = 12
    TAG_SIZE = 16

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        if len(key) not in (16, 24, 32):
            raise ValueError("AES-GCM密钥必须为16/24/32字节")
        nonce = get_random_bytes(self.NONCE_SIZE)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        return nonce + tag + ciphertext

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        if len(key) not in (16, 24, 32):
            raise ValueError("AES-GCM密钥必须为16/24/32字节")
        nonce = data[:self.NONCE_SIZE]
        tag = data[self.NONCE_SIZE: self.NONCE_SIZE + self.TAG_SIZE]
        ciphertext = data[self.NONCE_SIZE + self.TAG_SIZE:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)

    def generate_random_key(self) -> bytes:
        # 生成16字节标准合法密钥（最常用，可改为24/32）
        return secrets.token_bytes(16)


# -------------------------- 8. AES-CTR 加密 --------------------------
class AesCtrCipher:
    """
    【AES-CTR加密】类型：流加密 | 密钥：16/24/32字节
    优点：无填充、速度极快、高安全性
    缺点：无内置认证
    场景：大文件加密、流媒体传输
    """
    name = "AES-CTR"
    description = "流加密，无填充、速度极快、高安全性，无内置认证，适用于大文件加密、流媒体传输"

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        if len(key) not in (16, 24, 32):
            raise ValueError("AES-CTR密钥必须为16/24/32字节")
        nonce = get_random_bytes(8)
        cipher = AES.new(key, AES.MODE_CTR, nonce=nonce)
        return nonce + cipher.encrypt(data)

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        if len(key) not in (16, 24, 32):
            raise ValueError("AES-CTR密钥必须为16/24/32字节")
        nonce = data[:8]
        cipher = AES.new(key, AES.MODE_CTR, nonce=nonce)
        return cipher.decrypt(data[8:])

    def generate_random_key(self) -> bytes:
        # 生成16字节标准合法密钥（最常用，可改为24/32）
        return secrets.token_bytes(16)


# -------------------------- 9. Salsa20 加密 --------------------------
class Salsa20Cipher:
    """
    【Salsa20加密】类型：流加密 | 密钥：32字节
    优点：轻量、安全、无专利、适配弱设备
    缺点：安全性略低于ChaCha20
    场景：嵌入式设备、轻量级加密
    """
    name = "Salsa20"
    description = "流加密，轻量、安全、无专利、适配弱设备，安全性略低于ChaCha20，适用于嵌入式设备、轻量级加密"

    KEY_SIZE = 32
    NONCE_SIZE = 8

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        if len(key) != self.KEY_SIZE:
            raise ValueError(f"Salsa20密钥必须为{self.KEY_SIZE}字节")
        nonce = get_random_bytes(self.NONCE_SIZE)
        cipher = Salsa20.new(key=key, nonce=nonce)
        return nonce + cipher.encrypt(data)

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        if len(key) != self.KEY_SIZE:
            raise ValueError(f"Salsa20密钥必须为{self.KEY_SIZE}字节")
        nonce = data[:self.NONCE_SIZE]
        cipher = Salsa20.new(key=key, nonce=nonce)
        return cipher.decrypt(data[self.NONCE_SIZE:])

    def generate_random_key(self) -> bytes:
        # 固定32字节合法密钥
        return secrets.token_bytes(self.KEY_SIZE)


# -------------------------- 10. Blowfish 加密 --------------------------
class BlowfishCipher:
    """
    【Blowfish加密】类型：分组加密 | 密钥：4~56字节
    优点：无后门、轻量、未被破解
    缺点：块大小较小，现代应用少
    场景：嵌入式系统、本地小数据加密
    """
    name = "Blowfish"
    description = "分组加密，无后门、轻量、未被破解，块大小较小现代应用少，适用于嵌入式系统、本地小数据加密"

    BLOCK_SIZE = 8

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        if not (4 <= len(key) <= 56):
            raise ValueError("Blowfish密钥长度4~56字节")
        iv = get_random_bytes(self.BLOCK_SIZE)
        cipher = Blowfish.new(key, Blowfish.MODE_CBC, iv)
        return iv + cipher.encrypt(pad(data, self.BLOCK_SIZE))

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        if not (4 <= len(key) <= 56):
            raise ValueError("Blowfish密钥长度4~56字节")
        iv = data[:self.BLOCK_SIZE]
        cipher = Blowfish.new(key, Blowfish.MODE_CBC, iv)
        return unpad(cipher.decrypt(data[self.BLOCK_SIZE:]), self.BLOCK_SIZE)

    def generate_random_key(self) -> bytes:
        # 4-56字节限制，生成8-32字节合法随机密钥
        return secrets.token_bytes(random.randint(8, 32))


Map_list = [
    XorCipher,
    AesCipher,
    DesCipher,
    TripleDesCipher,
    Rc4Cipher,
    ChaCha20Cipher,
    AesGcmCipher,
    AesCtrCipher,
    Salsa20Cipher,
    BlowfishCipher
]
Map = {i.name: [i.description, i] for i in Map_list}

# 全局固定PEM标识（内置拼接，永不写入密钥本体，所有算法共用）
PEM_PUBLIC_HEAD = b"-----BEGIN PUBLIC KEY-----\n"
PEM_PUBLIC_FOOT = b"\n-----END PUBLIC KEY-----\n"
PEM_PRIVATE_HEAD = b"-----BEGIN PRIVATE KEY-----\n"
PEM_PRIVATE_FOOT = b"\n-----END PRIVATE KEY-----\n"
PEM_RSA_PRIV_HEAD = b"-----BEGIN RSA PRIVATE KEY-----\n"
PEM_RSA_PRIV_FOOT = b"\n-----END RSA PRIVATE KEY-----\n"

# 辅助函数：字节异或
def xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes([i ^ j for i, j in zip(a, b)])

# HKDF密钥派生（ECIES/X25519必备，安全标准化共享密钥）
def hkdf_derive(shared_secret: bytes) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"encrypt_chat_v1",
        backend=default_backend()
    )
    return hkdf.derive(shared_secret)

# AES-GCM认证加密（防篡改、防重放，唯一标准对称加密）
def aes_gcm_encrypt(key: bytes, data: bytes) -> tuple[bytes, bytes, bytes]:
    nonce = os.urandom(12)
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(data) + encryptor.finalize()
    return nonce, encryptor.tag, ciphertext

def aes_gcm_decrypt(key: bytes, nonce: bytes, tag: bytes, ciphertext: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag))
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()

# # -------------------------- 11. RSA-OAEP 非对称加密（cryptography，首选） --------------------------
# class RsaOaepCipher:
#     """
#     【RSA-OAEP加密】类型：非对称加密 | 密钥：4096位密钥对
#     优点：工业标准、安全OAEP填充、无已知漏洞、兼容性极强
#     缺点：仅支持短数据加密，性能低于对称加密
#     场景：加密对称密钥、数字证书、金融/通信核心加密
#     """
#     name = "RSA-OAEP"
#     description = "非对称加密，工业标准、安全OAEP填充、4096位密钥，仅加密短数据/对称密钥，生产环境首选"
#
#     def generate_random_key(self):
#         private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096, backend=default_backend())
#         public_key = private_key.public_key()
#         # 导出纯密钥内容，剔除所有头部尾部
#         private_bytes = private_key.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption()).replace(PEM_PRIVATE_HEAD, b"").replace(PEM_PRIVATE_FOOT, b"")
#         public_bytes = public_key.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo).replace(PEM_PUBLIC_HEAD, b"").replace(PEM_PUBLIC_FOOT, b"")
#         return private_bytes, public_bytes
#
#     def encrypt(self, data: bytes, public_key_bytes: bytes) -> bytes:
#         # 内置拼接头部，密钥本体无任何标识
#         pem_public = PEM_PUBLIC_HEAD + public_key_bytes + PEM_PUBLIC_FOOT
#         public_key = serialization.load_pem_public_key(pem_public, backend=default_backend())
#         ciphertext = public_key.encrypt(data, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
#         return ciphertext
#
#     def decrypt(self, data: bytes, private_key_bytes: bytes) -> bytes:
#         # 内置拼接头部，密钥本体无任何标识
#         pem_private = PEM_PRIVATE_HEAD + private_key_bytes + PEM_PRIVATE_FOOT
#         private_key = serialization.load_pem_private_key(pem_private, password=None, backend=default_backend())
#         plaintext = private_key.decrypt(data, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
#         return plaintext
#
# # -------------------------- 12. RSA-OAEP-Pyc 非对称加密（pycryptodome，兼容旧项目） --------------------------
# class RsaOaepPycCipher:
#     """
#     【RSA-OAEP-Pyc加密】类型：非对称加密 | 密钥：4096位密钥对
#     优点：兼容老旧项目、API简洁、OAEP安全填充
#     缺点：仅支持短数据加密，维护性低于cryptography
#     场景：遗留系统兼容、旧项目非对称加密
#     """
#     name = "RSA-OAEP-Pyc"
#     description = "非对称加密，基于pycryptodome，OAEP填充、4096位密钥，兼容旧项目，仅加密短数据"
#
#     def generate_random_key(self):
#         key = PycRSA.generate(4096)
#         # 导出纯密钥内容，剔除所有头部尾部
#         private_bytes = key.export_key().replace(PEM_RSA_PRIV_HEAD, b"").replace(PEM_RSA_PRIV_FOOT, b"")
#         public_bytes = key.publickey().export_key().replace(PEM_PUBLIC_HEAD, b"").replace(PEM_PUBLIC_FOOT, b"")
#         return private_bytes, public_bytes
#
#     def encrypt(self, data: bytes, public_key_bytes: bytes) -> bytes:
#         # 内置拼接头部，密钥本体无任何标识
#         pem_public = PEM_PUBLIC_HEAD + public_key_bytes + PEM_PUBLIC_FOOT
#         public_key = PycRSA.import_key(pem_public)
#         cipher = PKCS1_OAEP.new(public_key)
#         return cipher.encrypt(data)
#
#     def decrypt(self, data: bytes, private_key_bytes: bytes) -> bytes:
#         # 内置拼接头部，密钥本体无任何标识
#         pem_private = PEM_RSA_PRIV_HEAD + private_key_bytes + PEM_RSA_PRIV_FOOT
#         private_key = PycRSA.import_key(pem_private)
#         cipher = PKCS1_OAEP.new(private_key)
#         return cipher.decrypt(data)
#
# # -------------------------- 13. ECIES-ECC 非对称加密（椭圆曲线，现代首选）【加密结果无头部版】 --------------------------
# class EciesEccCipher:
#     """
#     【ECC】类型：非对称加密 | 密钥：secp256r1椭圆曲线密钥对
#     优点：轻量高效、安全强度极高、密钥体积小、性能远超RSA
#     缺点：部分老旧系统不兼容
#     场景：移动端、物联网、现代应用、高性能加密场景
#     """
#     name = "ECC"
#     description = "非对称加密，椭圆曲线ECDH方案，全版本兼容、稳定无报错，椭圆曲线，现代首选"
#
#     def generate_random_key(self):
#         private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
#         public_key = private_key.public_key()
#         private_bytes = private_key.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption()).replace(PEM_PRIVATE_HEAD, b"").replace(PEM_PRIVATE_FOOT, b"")
#         public_bytes = public_key.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo).replace(PEM_PUBLIC_HEAD, b"").replace(PEM_PUBLIC_FOOT, b"")
#         return private_bytes, public_bytes
#
#     def encrypt(self, data: bytes, public_key_bytes: bytes) -> bytes:
#         pem_public = PEM_PUBLIC_HEAD + public_key_bytes + PEM_PUBLIC_FOOT
#         public_key = serialization.load_pem_public_key(pem_public, backend=default_backend())
#         ephemeral_private = ec.generate_private_key(ec.SECP256R1(), default_backend())
#         shared_secret = ephemeral_private.exchange(ec.ECDH(), public_key)
#         # 🔥 核心：加密结果里的临时公钥也剔除头部，纯内容输出
#         ephemeral_public_bytes = ephemeral_private.public_key().public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo).replace(PEM_PUBLIC_HEAD, b"").replace(PEM_PUBLIC_FOOT, b"")
#         separator = b"|||SEPARATOR|||"
#         ciphertext = xor_bytes(shared_secret, data)
#         return ephemeral_public_bytes + separator + ciphertext
#
#     def decrypt(self, data: bytes, private_key_bytes: bytes) -> bytes:
#         pem_private = PEM_PRIVATE_HEAD + private_key_bytes + PEM_PRIVATE_FOOT
#         private_key = serialization.load_pem_private_key(pem_private, password=None, backend=default_backend())
#         separator = b"|||SEPARATOR|||"
#         sep_index = data.index(separator)
#         ephemeral_public_bytes = data[:sep_index]
#         ciphertext = data[sep_index + len(separator):]
#         # 🔥 核心：内置拼接头部，纯公钥内容自动补全标识
#         pem_ephemeral_public = PEM_PUBLIC_HEAD + ephemeral_public_bytes + PEM_PUBLIC_FOOT
#         ephemeral_public = serialization.load_pem_public_key(pem_ephemeral_public, backend=default_backend())
#         shared_secret = private_key.exchange(ec.ECDH(), ephemeral_public)
#         return xor_bytes(shared_secret, ciphertext)
#
# # -------------------------- 14. X25519 (Curve25519) 椭圆曲线加密（现代顶级标准）【加密结果无头部版】 --------------------------
# class X25519Cipher:
#     name = "X25519"
#     description = "非对称加密，Curve25519椭圆曲线，安全高效，现代顶级标准"
#
#     def generate_random_key(self):
#         private_key = X25519PrivateKey.generate()
#         public_key = private_key.public_key()
#         private_bytes = private_key.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption()).replace(PEM_PRIVATE_HEAD, b"").replace(PEM_PRIVATE_FOOT, b"")
#         public_bytes = public_key.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo).replace(PEM_PUBLIC_HEAD, b"").replace(PEM_PUBLIC_FOOT, b"")
#         return private_bytes, public_bytes
#
#     def encrypt(self, data: bytes, public_key_bytes: bytes) -> bytes:
#         pem_public = PEM_PUBLIC_HEAD + public_key_bytes + PEM_PUBLIC_FOOT
#         public_key = serialization.load_pem_public_key(pem_public, backend=default_backend())
#         ephemeral_private = X25519PrivateKey.generate()
#         shared_secret = ephemeral_private.exchange(public_key)
#         # 🔥 核心：加密结果里的临时公钥也剔除头部，纯内容输出
#         ephemeral_public = ephemeral_private.public_key().public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo).replace(PEM_PUBLIC_HEAD, b"").replace(PEM_PUBLIC_FOOT, b"")
#         separator = b"|||SEPARATOR|||"
#         ciphertext = xor_bytes(shared_secret, data)
#         return ephemeral_public + separator + ciphertext
#
#     def decrypt(self, data: bytes, private_key_bytes: bytes) -> bytes:
#         pem_private = PEM_PRIVATE_HEAD + private_key_bytes + PEM_PRIVATE_FOOT
#         private_key = serialization.load_pem_private_key(pem_private, password=None, backend=default_backend())
#         separator = b"|||SEPARATOR|||"
#         sep_index = data.index(separator)
#         ephemeral_public_bytes = data[:sep_index]
#         ciphertext = data[sep_index + len(separator):]
#         # 🔥 核心：内置拼接头部，纯公钥内容自动补全标识
#         pem_ephemeral_public = PEM_PUBLIC_HEAD + ephemeral_public_bytes + PEM_PUBLIC_FOOT
#         ephemeral_public = serialization.load_pem_public_key(pem_ephemeral_public, backend=default_backend())
#         shared_secret = private_key.exchange(ephemeral_public)
#         return xor_bytes(shared_secret, ciphertext)

# RSA-OAEP 4096（工业级兼容）
class RsaOaepCipher:
    """
    【RSA-OAEP加密】类型：非对称加密 | 密钥：4096位密钥对
    优点：国际标准、OAEP安全填充、全平台兼容
    缺点：性能较低，仅用于加密对称密钥
    场景：兼容旧设备、金融通信、备用加密方案
    """
    name = "RSA-OAEP"
    description = "非对称加密，工业标准、SHA256-OAEP填充、4096位强密钥，生产环境兼容方案"

    def generate_random_key(self):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096, backend=default_backend())
        public_key = private_key.public_key()
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).replace(PEM_PRIVATE_HEAD, b"").replace(PEM_PRIVATE_FOOT, b"")
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).replace(PEM_PUBLIC_HEAD, b"").replace(PEM_PUBLIC_FOOT, b"")
        return private_bytes, public_bytes

    def encrypt(self, data: bytes, public_key_bytes: bytes) -> bytes:
        pem_public = PEM_PUBLIC_HEAD + public_key_bytes + PEM_PUBLIC_FOOT
        public_key = serialization.load_pem_public_key(pem_public, default_backend())
        return public_key.encrypt(data, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))

    def decrypt(self, data: bytes, private_key_bytes: bytes) -> bytes:
        pem_private = PEM_PRIVATE_HEAD + private_key_bytes + PEM_PRIVATE_FOOT
        private_key = serialization.load_pem_private_key(pem_private, None, default_backend())
        return private_key.decrypt(data, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))

# ECIES-ECC（secp256r1 高性能）
class EciesEccCipher:
    """
    【ECIES-ECC加密】类型：非对称加密 | 密钥：secp256r1椭圆曲线
    优点：轻量高效、密钥体积小、防篡改
    场景：移动端、高性能即时通讯
    """
    name = "ECC"
    description = "非对称加密，ECIES标准方案，secp256r1椭圆曲线，AES-GCM认证加密"

    def generate_random_key(self):
        private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        public_key = private_key.public_key()
        private_bytes = private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).replace(PEM_PRIVATE_HEAD, b"").replace(PEM_PRIVATE_FOOT, b"")
        public_bytes = public_key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).replace(PEM_PUBLIC_HEAD, b"").replace(PEM_PUBLIC_FOOT, b"")
        return private_bytes, public_bytes

    def encrypt(self, data: bytes, public_key_bytes: bytes) -> bytes:
        pem_public = PEM_PUBLIC_HEAD + public_key_bytes + PEM_PUBLIC_FOOT
        public_key = serialization.load_pem_public_key(pem_public, default_backend())
        ephemeral_private = ec.generate_private_key(ec.SECP256R1(), default_backend())
        shared_secret = ephemeral_private.exchange(ec.ECDH(), public_key)
        aes_key = hkdf_derive(shared_secret)
        nonce, tag, ciphertext = aes_gcm_encrypt(aes_key, data)
        ephem_pub = ephemeral_private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).replace(PEM_PUBLIC_HEAD, b"").replace(PEM_PUBLIC_FOOT, b"")
        return b"|||".join([ephem_pub, nonce, tag, ciphertext])

    def decrypt(self, data: bytes, private_key_bytes: bytes) -> bytes:
        pem_private = PEM_PRIVATE_HEAD + private_key_bytes + PEM_PRIVATE_FOOT
        private_key = serialization.load_pem_private_key(pem_private, None, default_backend())
        ephem_pub, nonce, tag, ciphertext = data.split(b"|||")
        pem_ephem = PEM_PUBLIC_HEAD + ephem_pub + PEM_PUBLIC_FOOT
        ephem_key = serialization.load_pem_public_key(pem_ephem, default_backend())
        shared_secret = private_key.exchange(ec.ECDH(), ephem_key)
        aes_key = hkdf_derive(shared_secret)
        return aes_gcm_decrypt(aes_key, nonce, tag, ciphertext)

# X25519（现代顶级标准，主选算法）
class X25519Cipher:
    """
    【X25519加密】类型：非对称加密 | 密钥：Curve25519椭圆曲线
    优点：顶级安全、抗侧信道攻击、无后门、Signal/WhatsApp标准选型
    场景：端到端加密聊天、高隐私保护核心算法
    """
    name = "X25519"
    description = "非对称加密，Curve25519椭圆曲线，HKDF+AES-GCM，现代顶级安全标准"

    def generate_random_key(self):
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key()
        private_bytes = private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).replace(PEM_PRIVATE_HEAD, b"").replace(PEM_PRIVATE_FOOT, b"")
        public_bytes = public_key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).replace(PEM_PUBLIC_HEAD, b"").replace(PEM_PUBLIC_FOOT, b"")
        return private_bytes, public_bytes

    def encrypt(self, data: bytes, public_key_bytes: bytes) -> bytes:
        pem_public = PEM_PUBLIC_HEAD + public_key_bytes + PEM_PUBLIC_FOOT
        public_key = serialization.load_pem_public_key(pem_public, default_backend())
        ephemeral_private = x25519.X25519PrivateKey.generate()
        shared_secret = ephemeral_private.exchange(public_key)
        aes_key = hkdf_derive(shared_secret)
        nonce, tag, ciphertext = aes_gcm_encrypt(aes_key, data)
        ephem_pub = ephemeral_private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).replace(PEM_PUBLIC_HEAD, b"").replace(PEM_PUBLIC_FOOT, b"")
        return b"|||".join([ephem_pub, nonce, tag, ciphertext])

    def decrypt(self, data: bytes, private_key_bytes: bytes) -> bytes:
        pem_private = PEM_PRIVATE_HEAD + private_key_bytes + PEM_PRIVATE_FOOT
        private_key = serialization.load_pem_private_key(pem_private, None, default_backend())
        ephem_pub, nonce, tag, ciphertext = data.split(b"|||")
        pem_ephem = PEM_PUBLIC_HEAD + ephem_pub + PEM_PUBLIC_FOOT
        ephem_key = serialization.load_pem_public_key(pem_ephem, default_backend())
        shared_secret = private_key.exchange(ephem_key)
        aes_key = hkdf_derive(shared_secret)
        return aes_gcm_decrypt(aes_key, nonce, tag, ciphertext)

# ======================== 非对称加密 - 列表与映射（独立命名，对接原有格式） ========================
Map_list_asymmetric = [
    # RsaOaepCipher,
    # # RsaOaepPycCipher,     # 极慢
    # EciesEccCipher,
    # X25519Cipher,
    RsaOaepCipher,
    EciesEccCipher,
    X25519Cipher
]
map_asymmetric = {i.name: [i.description, i] for i in Map_list_asymmetric}

# ======================== 统一测试：所有算法加解密验证 ========================
if __name__ == '__main__':
    # 统一测试原始字节数据
    original_data = b"test byte encryption"
    print("原始数据：", original_data.decode('utf-8'), "\n")

    # 定义所有加密算法实例 + 对应密钥
    cipher_list = [
        XorCipher(),
        AesCipher(),
        DesCipher(),
        TripleDesCipher(),
        Rc4Cipher(),
        ChaCha20Cipher(),
        AesGcmCipher(),
        AesCtrCipher(),
        Salsa20Cipher(),
        BlowfishCipher(),
    ]

    # 遍历测试所有算法
    for cipher in cipher_list:
        try:
            key = cipher.generate_random_key()
            encrypted = cipher.encrypt(original_data, key)
            decrypted = cipher.decrypt(encrypted, key)
            success = original_data == decrypted
            print(f"【{cipher.__class__.__name__}】")
            print(f"  描述：{cipher.description}")
            print(f"  加密结果：{encrypted[:32]}...")  # 只打印前32字节
            print(f"  解密结果：{decrypted.decode('utf-8')}")
            print(f"  长度比：{len(encrypted) / len(original_data) * 100:.2f}%")
            print(f"  验证结果：{'✅ 成功' if success else '❌ 失败'}\n")
        except Exception as e:
            print(f"【{cipher.__class__.__name__}】❌ 报错：{str(e)}\n")

    # 非对称加密统一测试短数据（非对称仅支持短数据）==========================================================
    original_data = b"test asymmetric encryption"
    print("=" * 60)
    print("🔒 非对称加密算法测试")
    print("原始数据：", original_data.decode('utf-8'), "\n")

    # 非对称算法实例列表（自动遍历新封装类）
    asymmetric_ciphers = [cls() for cls in Map_list_asymmetric]

    # 遍历测试所有非对称算法
    for i, cipher in enumerate(asymmetric_ciphers):
        # 生成密钥对（私钥，公钥）
        private_key, public_key = cipher.generate_random_key()
        # 加密（公钥）/ 解密（私钥）
        encrypted = cipher.encrypt(original_data, public_key)
        decrypted = cipher.decrypt(encrypted, private_key)
        success = original_data == decrypted

        print(f"【{cipher.__class__.__name__}】")
        print(f"  描述：{cipher.description}")
        print(f"  加密结果：{encrypted[:32]}…[{len(encrypted)}]")
        print(f"  私钥：{private_key[:32]}…[{len(private_key)}]")
        print(f"  公钥：{public_key[:32]}…[{len(public_key)}]")
        print(f"  解密结果：{decrypted.decode('utf-8')}")
        print(f"  长度比：{len(encrypted) / len(original_data) * 100:.2f}%")
        print(f"  验证结果：{'✅ 成功' if success else '❌ 失败'}\n")
