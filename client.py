import random
from Tool.PixelUI import col_dict, MessageBox
import Tool.PixelUI as ui
import tkinter as tk
import time, re
from PIL import Image, ImageTk, ImageEnhance
from io import BytesIO
from tkinter import filedialog
import sys, os
import PackageAnalys as Pkg
from SocketModuleV2 import SocketClient
from Tool.EncryptionByte import X25519Cipher, AesGcmCipher
from Tool.HashCalcu import Sha256Hash
from Tool.EnDecode import Base64
from Tool.QRcodeFun import generate_qr, decode_qr
from Tool.DeviceInfo import ThreadSafeScreenshotManager
import json


def get_root_path():
    # 判断是否是打包后的exe
    if getattr(sys, 'frozen', False):
        # 打包后：返回exe所在的文件夹路径
        return os.path.dirname(sys.executable)
    # 正常运行.py：返回脚本所在目录
    return os.path.dirname(os.path.abspath(__file__))

user_name = 'Zorn'
zip_type = "zstd"
config_path = f'chat_config'
file_path = f'chat_files'
imgs_path = f'chat_images'
os.makedirs(config_path, exist_ok=True)
os.makedirs(file_path, exist_ok=True)
os.makedirs(imgs_path, exist_ok=True)

script_dir = get_root_path()

# 服务器仅存储用户公钥哈希、临时离线消息队列，不储存任何聊天记录、联系人关系
class ServerFun(SocketClient):
    def __init__(self, server_ip: str = '127.0.0.1', port: int = 10276):
        super().__init__(server_ip, port)
        # 新增：主窗口引用（用于消息刷新）
        self.main_win = None

        # 检查本地是否存在非对称密钥对，后续需要转移在加密硬件中，避免被窃取
        save_path_public = f"{config_path}/chat_public_keys.zorns"
        save_path_private = f"{config_path}/chat_private_keys.zorns"
        if os.path.isfile(save_path_public) and os.path.isfile(save_path_private):
            print("从本地磁盘加载非对称密钥")
            # 使用先前的密钥加密储存在本地文件
            with open(save_path_public, mode='rb') as f:
                content_public = f.read()
            with open(save_path_private, mode='rb') as f:
                content_private = f.read()
            # keys暂时为空，后续从安全硬件中读取
            note, my_info_str_b = pkg.unpack(content_public, keys=[])
            note, private_keys_byte = pkg.unpack(content_private, keys=[])
            my_info_json = json.loads(my_info_str_b.decode())
            private_keys_json = json.loads(private_keys_byte.decode())
            self.private_bytes = base64.decode(private_keys_json['private_key'].encode())
            self.public_bytes = base64.decode(my_info_json['public_key'].encode())
            self.user_name = my_info_json['user_name']
        else:
            self.user_name = user_name
            self.private_bytes, self.public_bytes = encryption.generate_random_key()
            # print(self.private_bytes, self.public_bytes)
            private_key = base64.encode(self.private_bytes).decode()
            public_key = base64.encode(self.public_bytes).decode()
            # 保存到本地
            private_key_json = {'private_key': private_key}
            public_key_json = {'public_key': public_key, "user_name": self.user_name}
            private_key_json_str_b = json.dumps(private_key_json, ensure_ascii=False).encode()
            public_key_json_str_b = json.dumps(public_key_json, ensure_ascii=False).encode()
            # encryption_steps暂时为空，后续从安全硬件中读取
            e_private_key_data = pkg.pack(private_key_json_str_b, data_note=[{"type": "private_key"}],
                                          encryption_steps=[])
            e_public_key_data = pkg.pack(public_key_json_str_b, data_note=[{"type": "public_key"}], encryption_steps=[])
            with open(save_path_private, mode='wb') as f:
                f.write(e_private_key_data)
            with open(save_path_public, mode='wb') as f:
                f.write(e_public_key_data)

        # 检查本地对称密钥是否存在，不存在则创建，使用非对称密钥加密
        save_path = f"{config_path}/chat_keys.zorns"
        if os.path.isfile(save_path):
            print("从本地磁盘加载对称密钥")
            # 使用先前的密钥加密储存在本地文件
            with open(save_path, mode='rb') as f:
                content = f.read()
            # keys暂时为空，后续从安全硬件中读取
            note, keys_data = pkg.unpack(content, keys=[("X25519", self.private_bytes)])
            keys = json.loads(keys_data.decode())['key']
            self.key = base64.decode(keys.encode())
        else:
            self.key = encryption_.generate_random_key()
            # print(self.key_bytes)
            key = base64.encode(self.key).decode()
            # 保存到本地
            keys = {'key': key}
            keys_json = json.dumps(keys, ensure_ascii=False).encode()
            # encryption_steps暂时为空，后续从安全硬件中读取
            e_keys_data = pkg.pack(keys_json, data_note=[{"type": "Keys"}],
                                   encryption_steps=[("X25519", self.public_bytes)])
            with open(save_path, mode='wb') as f:
                f.write(e_keys_data)

        # 向服务器发送本地公钥哈希
        public_hash = Sha256Hash.compute(self.public_bytes)  # str
        send_content_json = {"type": "public_hush", "content": public_hash}
        send_content_data = json.dumps(send_content_json, ensure_ascii=False).encode()
        self.send(send_content_data)

        # 从本地文件获取未读聊天记录，若不存在则创建空，用对称密钥加密储存
        save_path = f"{config_path}/chat_new_message.zorns"
        if os.path.isfile(save_path):
            print("从本地磁盘加载未读聊天记录")
            with open(save_path, mode='rb') as f:
                content = f.read()
            note, data = pkg.unpack(content, keys=[("AES-GCM", self.key)])
            self.new_message = json.loads(data.decode())
        else:
            # 保存到本地
            """形如:[
                {"ID": "用户哈希", "content": "来自服务器的新消息", "time": "2026-12-6 14:58:53"}
            ]"""
            messages = []
            messages_json = json.dumps(messages, ensure_ascii=False).encode()
            # encryption_steps暂时为空，后续从安全硬件中读取
            e_messages_data = pkg.pack(messages_json, data_note=[{"type": "Keys"}],
                                       encryption_steps=[("AES-GCM", self.key)])
            with open(save_path, mode='wb') as f:
                f.write(e_messages_data)
            self.new_message = messages

        # 从本地文件获取联系人表，若不存在则创建空，用对称密钥加密储存
        save_path = f"{config_path}/chat_contact.zorns"
        if os.path.isfile(save_path):
            print("从本地磁盘加载联系人表")
            with open(save_path, mode='rb') as f:
                content = f.read()
            note, data = pkg.unpack(content, keys=[("AES-GCM", self.key)])
            self.contact = json.loads(data.decode())
        else:
            # 保存到本地
            """形如:test = {
                '用户哈希': {'name': '用户名', 'head': None, "key": user_key},
            }"""
            contact = {}
            contact_json = json.dumps(contact, ensure_ascii=False).encode()
            # encryption_steps暂时为空，后续从安全硬件中读取
            e_contact = pkg.pack(contact_json, data_note=[{"type": "Keys"}],
                                 encryption_steps=[("AES-GCM", self.key)])
            with open(save_path, mode='wb') as f:
                f.write(e_contact)
            self.contact = contact

        # 从本地文件获取聊天记录，若不存在则创建空，用对称密钥加密储存
        save_path = f"{config_path}/chat_historical_message.zorns"
        if os.path.isfile(save_path):
            print("从本地磁盘加载聊天记录")
            with open(save_path, mode='rb') as f:
                content = f.read()
            note, data = pkg.unpack(content, keys=[("AES-GCM", self.key)])
            self.historical_message = json.loads(data.decode())
        else:
            # 保存到本地
            """形如:test = {
                "用户哈希": [
                    {"ID": "self", "content": "我说的话", "time": "2026-12-3 14:50:32"},
                    {"ID": "用户哈希", "content": "对方说的话", "time": "2026-12-4 14:50:53"},
                ]
            }"""
            contact = {}
            contact_json = json.dumps(contact, ensure_ascii=False).encode()
            # encryption_steps暂时为空，后续从安全硬件中读取
            e_contact = pkg.pack(contact_json, data_note=[{"type": "Keys"}],
                                 encryption_steps=[("AES-GCM", self.key)])
            with open(save_path, mode='wb') as f:
                f.write(e_contact)
            self.historical_message = contact

        # 从本地文件获取图片映射，若不存在则创建空，用对称密钥加密储存
        save_path = f"{config_path}/chat_images_index.zorns"
        if os.path.isfile(save_path):
            print("从本地磁盘加载图片索引")  # 修正错误打印
            with open(save_path, mode='rb') as f:
                content = f.read()
            note, data = pkg.unpack(content, keys=[("AES-GCM", self.key)])
            self.imgs_index = json.loads(data.decode())
        else:
            contact = {}
            contact_json = json.dumps(contact, ensure_ascii=False).encode()
            e_contact = pkg.pack(contact_json, data_note=[{"type": "Keys"}],
                                 encryption_steps=[("AES-GCM", self.key)])
            with open(save_path, mode='wb') as f:
                f.write(e_contact)
            self.imgs_index = contact


        # 从本地文件获取文件映射，若不存在则创建空，用对称密钥加密储存
        save_path = f"{config_path}/chat_files_index.zorns"
        if os.path.isfile(save_path):
            print("从本地磁盘加载文件索引")
            with open(save_path, mode='rb') as f:
                content = f.read()
            note, data = pkg.unpack(content, keys=[("AES-GCM", self.key)])
            self.files_index = json.loads(data.decode())
        else:
            contact = {}
            contact_json = json.dumps(contact, ensure_ascii=False).encode()
            e_contact = pkg.pack(contact_json, data_note=[{"type": "Keys"}],
                                 encryption_steps=[("AES-GCM", self.key)])
            with open(save_path, mode='wb') as f:
                f.write(e_contact)
            self.files_index = contact

        # 读取当前头像上传到服务器，方便用户每次读取
        head_path = f"{config_path}/head.png"
        try:
            img = Image.open(head_path).convert("RGB")
        except FileNotFoundError:
            img = Image.new("RGB", (64, 64), col_dict['bg'])
            img.save(head_path)
        byte_buffer = BytesIO()
        img.save(byte_buffer, format="JPEG", quality=80)
        img_bytes = byte_buffer.getvalue()
        message_json = {"type": "user_head", "content": {"head": base64.encode(img_bytes).decode(), "name": self.user_name}, "contact_hash": [i for i in self.contact]}
        send_content_data = json.dumps(message_json, ensure_ascii=False).encode()
        self.send(send_content_data)

        # 新增：记录已打开的对话框
        self.open_dialogues = {}

    def save_files_index(self):
        """保存文件索引到本地加密文件"""
        save_path = f"{config_path}/chat_files_index.zorns"
        contact_json = json.dumps(self.files_index, ensure_ascii=False).encode()
        e_contact = pkg.pack(contact_json, data_note=[{"type": "Keys"}],
                             encryption_steps=[("AES-GCM", self.key)])
        with open(save_path, mode='wb') as f:
            f.write(e_contact)

    def save_file(self, file_bytes, timestamp, file_name):
        """保存文件到本地指定目录，更新文件索引"""
        file_save_path = os.path.join(file_path, file_name)
        with open(file_save_path, 'wb') as f:
            f.write(file_bytes)
        # 索引绑定时间戳 → 文件完整路径
        self.files_index[timestamp] = file_save_path
        self.save_files_index()
        return timestamp

    def send_file(self, target_hash, target_key, file_base64, timestamp, time, file_name):
        # 生成临时对称密钥（与文本/图片逻辑完全一致）
        key = encryption_.generate_random_key()
        public_key_base64 = self.contact[target_hash]['key']
        public_key = base64.decode(public_key_base64.encode())
        public_hash = Sha256Hash.compute(public_key)

        # 非对称加密临时密钥
        e_key_byte = encryption.encrypt(key, public_key)
        e_key_base64 = base64.encode(e_key_byte).decode()

        # 对称加密文件数据
        file_bytes = base64.decode(file_base64.encode())
        e_file_bytes = encryption_.encrypt(file_bytes, key)
        e_file_base64 = base64.encode(e_file_bytes).decode()

        # 封装文件消息 type=send_file，新增file_name字段
        message_json = {
            "type": "send_file",
            "content": {
                "target_hash": public_hash,
                "file": e_file_base64,
                "key": e_key_base64,
                "time": time,
                "from": Sha256Hash.compute(self.public_bytes),
                "timestamp": timestamp,
                "file_name": file_name
            }
        }
        message_data = json.dumps(message_json, ensure_ascii=False).encode()
        self.send(message_data)

    def get_files(self, timestamp):
        return self.files_index.get(timestamp)

    def save_imgs_index(self):
        """保存图片索引到本地加密文件"""
        save_path = f"{config_path}/chat_images_index.zorns"
        contact_json = json.dumps(self.imgs_index, ensure_ascii=False).encode()
        e_contact = pkg.pack(contact_json, data_note=[{"type": "Keys"}],
                             encryption_steps=[("AES-GCM", self.key)])
        with open(save_path, mode='wb') as f:
            f.write(e_contact)

    def send_image(self, target_hash, target_key, img_base64, timestamp, time):
        # 生成临时对称密钥（与文本消息逻辑完全一致）
        key = encryption_.generate_random_key()
        public_key_base64 = self.contact[target_hash]['key']
        public_key = base64.decode(public_key_base64.encode())
        public_hash = Sha256Hash.compute(public_key)

        # 公钥加密临时密钥
        e_key_byte = encryption.encrypt(key, public_key)
        e_key_base64 = base64.encode(e_key_byte).decode()

        # 对称加密图片数据
        img_bytes = base64.decode(img_base64.encode())
        e_img_bytes = encryption_.encrypt(img_bytes, key)
        e_img_base64 = base64.encode(e_img_bytes).decode()

        # 封装图片消息（type修改为send_image）
        message_json = {
            "type": "send_image",
            "content": {
                "target_hash": public_hash,
                "img": e_img_base64,
                "key": e_key_base64,
                "time": time,
                "from": Sha256Hash.compute(self.public_bytes),
                "timestamp": timestamp
            }
        }
        message_data = json.dumps(message_json, ensure_ascii=False).encode()
        self.send(message_data)

    def bind_main_win(self, win_instance):
        """绑定主窗口实例，用于消息刷新"""
        self.main_win = win_instance

    def save_new_message(self):
        save_path = f"{config_path}/chat_new_message.zorns"
        messages_json = json.dumps(self.new_message, ensure_ascii=False).encode()
        e_messages_data = pkg.pack(messages_json, data_note=[{"type": "Keys"}],
                                   encryption_steps=[("AES-GCM", self.key)])
        with open(save_path, mode='wb') as f:
            f.write(e_messages_data)

    # 新增：保存历史聊天记录到文件
    def save_historical_message(self):
        save_path = f"{config_path}/chat_historical_message.zorns"
        contact_json = json.dumps(self.historical_message, ensure_ascii=False).encode()
        e_contact = pkg.pack(contact_json, data_note=[{"type": "Keys"}],
                             encryption_steps=[("AES-GCM", self.key)])
        with open(save_path, mode='wb') as f:
            f.write(e_contact)

    def set_new_username(self, new_username):
        save_path_public = f"{config_path}/chat_public_keys.zorns"
        self.user_name = new_username
        public_key = base64.encode(self.public_bytes).decode()
        public_key = {'public_key': public_key, "user_name": self.user_name}
        public_key_json = json.dumps(public_key, ensure_ascii=False).encode()
        e_public_key_data = pkg.pack(public_key_json, data_note=[{"type": "public_key"}], encryption_steps=[])
        with open(save_path_public, mode='wb') as f:
            f.write(e_public_key_data)

    def add_contact(self, user_key, name="UnKnow", head=None):
        key_byte = base64.decode(user_key.encode())
        public_key_hash = Sha256Hash.compute(key_byte)  # str
        self.contact[public_key_hash] = {'name': name, 'head': head, "key": user_key}

        save_path = f"{config_path}/chat_contact.zorns"
        contact_json = json.dumps(self.contact, ensure_ascii=False).encode()
        e_contact = pkg.pack(contact_json, data_note=[{"type": "Keys"}],
                             encryption_steps=[("AES-GCM", self.key)])
        with open(save_path, mode='wb') as f:
            f.write(e_contact)

    # ========== 关键修改：增强handle_message逻辑 ==========
    def handle_message(self, msg: bytes):
        """消息处理：输出前100字节，可自定义扩展"""
        try:
            json_data = json.loads(msg)
            # print(f"[客户端] 收到：{json_data}")
            data_type = json_data['type']
            content = json_data['content']
            if data_type == "send_message":
                target_hash = content['target_hash']
                text_base64 = content['text']
                key_base64 = content['key']
                from_key = content['from']
                text = base64.decode(text_base64.encode())
                key = base64.decode(key_base64.encode())
                send_time = content['time']

                public_hash = Sha256Hash.compute(self.public_bytes)  # str
                if target_hash == public_hash:
                    # 检查发送方是否在联系人列表中（避免KeyError）
                    if from_key not in self.contact:
                        print(f"警告：收到未知联系人 {from_key} 的消息")
                        return
                    # 解密消息
                    d_key = encryption.decrypt(key, self.private_bytes)
                    d_text = encryption_.decrypt(text, d_key).decode()

                    # 新消息分发逻辑
                    if from_key in self.open_dialogues:
                        # 对话框已打开：推送至界面并更新历史
                        dialogue_win = self.open_dialogues[from_key]
                        dialogue_win.receive_new_message(d_text, send_time, from_key)

                        if from_key not in self.historical_message:
                            self.historical_message[from_key] = []
                        self.historical_message[from_key].append({
                            "ID": from_key,
                            "content": d_text,
                            "time": send_time
                        })
                        self.save_historical_message()
                    else:
                        # 对话框未打开：加入未读并保存
                        self.new_message.append({"ID": from_key, "content": d_text, "time": send_time})
                        self.save_new_message()

                    print(
                        f"----------------------\n>>> 来自 {self.contact[from_key]['name']} 消息内容: {d_text}\n时间: {send_time} --------------")

                    # 收到新消息后立即刷新主窗口联系人列表
                    if self.main_win:
                        self.main_win._contact()
            elif data_type == "send_image":
                target_hash = content['target_hash']
                img_base64 = content['img']
                key_base64 = content['key']
                from_key = content['from']
                send_time = content['time']
                img_timestamp = content['timestamp']

                public_hash = Sha256Hash.compute(self.public_bytes)
                if target_hash == public_hash:
                    if from_key not in self.contact:
                        print(f"警告：收到未知联系人 {from_key} 的图片")
                        return

                    # 解密密钥 + 图片数据
                    key = base64.decode(key_base64.encode())
                    d_key = encryption.decrypt(key, self.private_bytes)
                    img_encrypted = base64.decode(img_base64.encode())
                    img_raw_bytes = encryption_.decrypt(img_encrypted, d_key)

                    # 需求5：保存图片到imgs_path，时间戳为文件名（JPEG）
                    img_file_name = f"{img_timestamp}.jpg"
                    img_save_path = os.path.join(imgs_path, img_file_name)
                    with open(img_save_path, 'wb') as f:
                        f.write(img_raw_bytes)

                    # 更新图片索引：绑定时间戳→文件路径
                    self.imgs_index[img_timestamp] = img_save_path
                    self.save_imgs_index()  # 需求7：持久化索引

                    # 图片占位符（与发送方格式完全一致）
                    img_placeholder = f"🖼_{img_timestamp}"

                    # 消息分发（与文本逻辑一致）
                    if from_key in self.open_dialogues:
                        dialogue_win = self.open_dialogues[from_key]
                        dialogue_win.receive_new_message(img_placeholder, send_time, from_key)

                        if from_key not in self.historical_message:
                            self.historical_message[from_key] = []
                        self.historical_message[from_key].append({
                            "ID": from_key,
                            "content": img_placeholder,
                            "time": send_time
                        })
                        self.save_historical_message()
                    else:
                        self.new_message.append({"ID": from_key, "content": img_placeholder, "time": send_time})
                        self.save_new_message()

                    print(
                        f"----------------------\n>>> 来自 {self.contact[from_key]['name']} 图片已保存: {img_save_path}\n时间: {send_time} --------------")
                    if self.main_win:
                        self.main_win._contact()
            elif data_type == "send_file":
                target_hash = content['target_hash']
                file_base64 = content['file']
                key_base64 = content['key']
                from_key = content['from']
                send_time = content['time']
                file_timestamp = content['timestamp']
                file_name = content['file_name']

                public_hash = Sha256Hash.compute(self.public_bytes)
                if target_hash == public_hash:
                    if from_key not in self.contact:
                        print(f"警告：收到未知联系人 {from_key} 的文件")
                        return

                    # 解密密钥 + 文件数据
                    key = base64.decode(key_base64.encode())
                    d_key = encryption.decrypt(key, self.private_bytes)
                    file_encrypted = base64.decode(file_base64.encode())
                    file_raw_bytes = encryption_.decrypt(file_encrypted, d_key)

                    # 保存文件到file_path，使用消息中的文件名
                    self.save_file(file_raw_bytes, file_timestamp, file_name)

                    # 文件占位符
                    file_placeholder = f"📄_{file_timestamp}"

                    # 写入聊天记录/未读消息
                    if from_key in self.open_dialogues:
                        dialogue_win = self.open_dialogues[from_key]
                        dialogue_win.receive_new_message(file_placeholder, send_time, from_key)

                        if from_key not in self.historical_message:
                            self.historical_message[from_key] = []
                        self.historical_message[from_key].append({
                            "ID": from_key,
                            "content": file_placeholder,
                            "time": send_time
                        })
                        self.save_historical_message()
                    else:
                        self.new_message.append({"ID": from_key, "content": file_placeholder, "time": send_time})
                        self.save_new_message()

                    print(
                        f"----------------------\n>>> 来自 {self.contact[from_key]['name']} 文件已保存: {self.files_index[file_timestamp]}\n时间: {send_time} --------------")
                    if self.main_win:
                        self.main_win._contact()
            elif data_type == "user_info":
                for from_key, user_info in content.items():
                    self.contact[from_key]['head'] = user_info['head']
                    self.contact[from_key]['name'] = user_info['name']

                contact_json = json.dumps(self.contact, ensure_ascii=False).encode()
                # encryption_steps暂时为空，后续从安全硬件中读取
                e_contact = pkg.pack(contact_json, data_note=[{"type": "Keys"}],
                                     encryption_steps=[("AES-GCM", self.key)])
                save_path = f"{config_path}/chat_contact.zorns"
                with open(save_path, mode='wb') as f:
                    f.write(e_contact)
        except Exception as e:
            print(f"消息处理失败：{e}")

    # 新增：合并未读消息到历史消息并清空未读
    def merge_new_to_historical(self, user_id):
        """打开对话框时，将该用户未读消息合并到历史消息并清空"""
        new_dialogue = self.get_new_dialogue(user_id)
        if not new_dialogue:
            return
        # 获取历史消息
        historical = self.historical_message.get(user_id, [])
        # 合并并按时间排序
        merged = historical + new_dialogue
        merged_sorted = sorted(merged, key=lambda x: self._timestr_to_timestamp(x['time']))
        self.historical_message[user_id] = merged_sorted
        # 清空该用户未读消息
        self.new_message = [item for item in self.new_message if item['ID'] != user_id]
        # 保存到本地
        self.save_historical_message()
        self.save_new_message()

    def send_img(self, img_bytes, timestamp):
        # 核心修复：保存图片到本地imgs_path，索引存储文件路径
        img_file_name = f"{timestamp}.jpg"
        img_save_path = os.path.join(imgs_path, img_file_name)
        with open(img_save_path, 'wb') as f:
            f.write(img_bytes)
        # 索引绑定时间戳 → 本地文件路径
        self.imgs_index[timestamp] = img_save_path
        self.save_imgs_index()
        return timestamp

    def get_show_config(self):
        contact_list = self.get_contact("ALL")
        all_historical_dialogue = self.get_historical_dialogue("ALL")
        all_new_dialogue = self.get_new_dialogue("ALL")
        temp_list = []
        for user_id, config in contact_list.items():
            read_mark = False
            # 提取字段
            name = config['name']
            head = config['head']
            user_key = config['key']
            # 获取最后一条对话（合并未读+历史，确保时间基准完整）
            last_dialogue = all_historical_dialogue.get(user_id, [])
            new_dialogue = [item for item in all_new_dialogue if item["ID"] == user_id]
            all_dialogue = last_dialogue + new_dialogue  # 合并未读和历史消息

            if not all_dialogue:
                last_timestamp = 0.0
                last_time = ''
                last_content = ''
            else:
                # 修复：按时间正序排序后取最后一条（最新）
                all_dialogue_sorted = sorted(all_dialogue, key=lambda x: self._timestr_to_timestamp(x['time']))
                show_dialogue_config = all_dialogue_sorted[-1]
                last_time = show_dialogue_config['time']
                last_content = show_dialogue_config['content']
                last_timestamp = self._timestr_to_timestamp(last_time)
                # 未读标记：只要有未读消息就显示
                read_mark = len(new_dialogue) > 0

            temp_list.append((user_id, read_mark, name, head, last_time, last_content, last_timestamp, user_key))

        # 修复：按时间戳降序排序（最新消息在前），无需反转
        temp_list.sort(key=lambda x: x[6], reverse=True)

        final_list = []
        for item in temp_list:
            final_list.append((item[0], item[1], item[2], item[3], item[4], item[5], item[7]))

        return final_list

    def _timestr_to_timestamp(self, time_str):
        time_struct = time.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        return time.mktime(time_struct)

    def get_new_dialogue(self, user_id):
        new_dialogue = self.new_message

        if user_id == 'ALL':
            return new_dialogue
        else:
            return [item for item in new_dialogue if item['ID'] == user_id]

    def get_historical_dialogue(self, user_id):
        historical_dialogue = self.historical_message
        if user_id == 'ALL':
            return historical_dialogue
        else:
            return historical_dialogue.get(user_id)

    def get_contact(self, user_id):
        test = self.contact

        if user_id == 'ALL':
            return test
        else:
            return test.get(user_id)

    def get_imgs(self, timestamp):
        imgs = self.imgs_index
        return imgs.get(timestamp)

    def send_message(self, target_hash, target_key, text, time):
        # 生成密钥
        key = encryption_.generate_random_key()
        # 密钥用对方公钥加密
        public_key_base64 = self.contact[target_hash]['key']
        public_key = base64.decode(public_key_base64.encode())
        public_hash = Sha256Hash.compute(public_key)

        public_key = base64.decode(public_key_base64.encode())
        e_key_byte = encryption.encrypt(key, public_key)
        e_key_base64 = base64.encode(e_key_byte).decode()

        text_bytes = encryption_.encrypt(text.encode(), key)
        e_text = base64.encode(text_bytes).decode()
        message_json = {"type": "send_message",
                        "content": {"target_hash": public_hash, "text": e_text, "key": e_key_base64, "time": time,
                                    "from": Sha256Hash.compute(self.public_bytes)}}
        message_data = json.dumps(message_json, ensure_ascii=False).encode()
        self.send(message_data)

class DialogueWin:
    def __init__(self, userid, user_key, server, dialogue_content, username):
        self.server = server
        self.userid = userid
        self.username = username
        self.user_key = user_key
        contact = self.server.get_contact(userid)

        self.last_message_id = None
        self.last_message_ts = 0

        self.server = server
        self.win = ui.Toplevel(
            title=contact['name'],
            # 顶端菜单
            menu_config={},
            page_config=['Dialogue'],
            w=378, h=527
        )

        # 绑定窗口关闭事件
        self.win.root.protocol("WM_DELETE_WINDOW", self._on_close)

        tag_config = [
            {"tagName": "UN_s", "font": ("Fusion Pixel 12px Mono zh_hans", 11, "bold"),
             "foreground": col_dict['text'], "background": col_dict['bg'], "justify": "right"},
            {"tagName": "P_s", "font": ("Fusion Pixel 12px Mono zh_hans", 11,),
             "foreground": "white", "background": col_dict['bg'], "justify": "right"},
            {"tagName": "T_s", "font": ("Fusion Pixel 12px Mono zh_hans", 9,),
             "foreground": col_dict['light'], "background": col_dict['bg'], "justify": "right"},
            {"tagName": "Img_s", "font": ("Fusion Pixel 12px Mono zh_hans", 10, "bold"),
             "foreground": '#5862ff', "background": col_dict['bg'], "justify": "right"},
            {"tagName": "File_s", "font": ("Fusion Pixel 12px Mono zh_hans", 10, "bold"),
             "foreground": '#7ade87', "background": col_dict['bg'], "justify": "right"},

            {"tagName": "UN", "font": ("Fusion Pixel 12px Mono zh_hans", 11, "bold"),
             "foreground": col_dict['text'], "background": col_dict['bg'], "justify": "left"},
            {"tagName": "P", "font": ("Fusion Pixel 12px Mono zh_hans", 11,),
             "foreground": "white", "background": col_dict['bg'], "justify": "left"},
            {"tagName": "T", "font": ("Fusion Pixel 12px Mono zh_hans", 9,),
             "foreground": col_dict['light'], "background": col_dict['bg'], "justify": "left"},
            {"tagName": "Img", "font": ("Fusion Pixel 12px Mono zh_hans", 10, "bold"),
             "foreground": '#5862ff', "background": col_dict['bg'], "justify": "left"},
            {"tagName": "File", "font": ("Fusion Pixel 12px Mono zh_hans", 10, "bold"),
             "foreground": '#7ade87', "background": col_dict['bg'], "justify": "left"},
        ]
        self.text = ui.Text(
            self.win.screen_frames['Dialogue'],
            family="Fusion Pixel 12px Mono zh_hans",
            spacing1=3,  # 段前
            spacing2=2,  # 自动换行间距
            spacing3=2,  # 段后
            width=48, height=16,
            tag_config=tag_config
        )
        self.text.place(x=5, y=5)
        self.text.text.bind("<Key>", self._handle_key)
        self.text.text.tag_bind("Img_s", "<Button-1>", self._open_img)
        self.text.text.tag_bind("Img", "<Button-1>", self._open_img)
        self.text.text.tag_bind("File_s", "<Button-1>", self._open_file)
        self.text.text.tag_bind("File", "<Button-1>", self._open_file)

        # 确保消息按时间正序显示（已在调用处排序，此处直接遍历）
        for item in dialogue_content[-100:]:
            current_id = item['ID']
            content = item['content']
            timestr = item['time']
            # 转换时间字符串为时间戳
            current_ts = time.mktime(time.strptime(timestr, "%Y-%m-%d %H:%M:%S"))

            # 判断条件：发送者不同 或 时间间隔超过60秒 → 显示用户名+时间
            show_header = (current_id != self.last_message_id) or (current_ts - self.last_message_ts > 60)

            if current_id == "self":
                if show_header:
                    self.text.insert('end', f"{timestr}", 'T_s')
                    self.text.insert('end', f" >>> Me\n", 'UN_s')
                # 显示内容（文本/图片/文件）
                if "🖼" in content:
                    self.text.insert('end', f"[{content}]\n", 'Img_s')
                elif "📄" in content:
                    self.text.insert('end', f"[{content}]\n", 'File_s')
                else:
                    self.text.insert('end', f"{content}\n", 'P_s')
            else:
                user_name = self.server.get_contact(current_id)['name']
                if show_header:
                    self.text.insert('end', f">>> {user_name} ", 'UN')
                    self.text.insert('end', f"{timestr}\n", 'T')
                # 显示内容（文本/图片/文件）
                if "🖼" in content:
                    self.text.insert('end', f"[{content}]\n", 'Img')
                elif "📄" in content:
                    self.text.insert('end', f"[{content}]\n", 'File')
                else:
                    self.text.insert('end', f"{content}\n", 'P')

            # 更新上一条消息记录
            self.last_message_id = current_id
            self.last_message_ts = current_ts

        self.text.text.see('end')

        self.img_b = ui.Button(self.win.screen_frames['Dialogue'], text='🖼', font_size=8, command=self._send_img)
        self.img_b.place(x=5, y=305)

        # 发送文件的按钮
        self.file_b = ui.Button(self.win.screen_frames['Dialogue'], text='📄', font_size=8, command=self._send_file)
        self.file_b.place(x=25, y=305)

        self.message_text = ui.Text(
            self.win.screen_frames['Dialogue'],
            family="Fusion Pixel 12px Mono zh_hans",
            spacing1=2,  # 段前
            spacing2=1,  # 自动换行间距
            spacing3=1,  # 段后
            width=48, height=6,
            tag_config=tag_config,
            font_size=10
        )
        self.message_text.place(x=5, y=326)

        self.send_b = ui.Button(self.message_text.text, text='send', command=self._send_message, bg=col_dict['bg'])
        self.send_b.place(x=280, y=70)


    def _send_file(self):
        file_path_select = filedialog.askopenfilename(
            title="请选择文件",
            initialdir=script_dir,
        )
        if not file_path_select:
            return

        # 提取文件名，读取文件字节（无压缩）
        file_name = os.path.basename(file_path_select)
        with open(file_path_select, 'rb') as f:
            file_bytes = f.read()

        # 生成唯一时间戳
        timestamp = str(time.time())
        timestr = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        current_ts = time.mktime(time.strptime(timestr, "%Y-%m-%d %H:%M:%S"))
        # 发送端判断：连续消息不显示头部
        show_header = ("self" != self.last_message_id) or (current_ts - self.last_message_ts > 60)

        # 本地保存文件 + 更新索引
        self.server.save_file(file_bytes, timestamp, file_name)
        file_placeholder = f"📄_{timestamp}"

        # 选择性显示头部（时间+用户名）
        if show_header:
            self.text.insert('end', f"{timestr}", 'T_s')
            self.text.insert('end', f" >>> Me\n", 'UN_s')
        # 显示文件内容
        self.text.insert('end', f"[{file_placeholder}]\n", 'File_s')

        # 写入历史聊天记录并持久化
        if self.userid not in self.server.historical_message:
            self.server.historical_message[self.userid] = []
        self.server.historical_message[self.userid].append({
            "ID": "self",
            "content": file_placeholder,
            "time": timestr
        })
        self.server.save_historical_message()

        # Base64编码并发送加密文件消息
        file_base64_str = base64.encode(file_bytes).decode()
        self.server.send_file(
            target_hash=self.userid,
            target_key=self.user_key,
            file_base64=file_base64_str,
            timestamp=timestamp,
            time=timestr,
            file_name=file_name
        )
        # 更新最后消息状态
        self.last_message_id = "self"
        self.last_message_ts = current_ts

    def receive_new_message(self, content, timestr, from_user_id):
        current_ts = time.mktime(time.strptime(timestr, "%Y-%m-%d %H:%M:%S"))
        # 判断是否显示头部
        show_header = (from_user_id != self.last_message_id) or (current_ts - self.last_message_ts > 60)

        user_name = self.server.get_contact(from_user_id)['name']
        if show_header:
            self.text.insert('end', f">>> {user_name} ", 'UN')
            self.text.insert('end', f"{timestr}\n", 'T')

        # 自动识别占位符：图片/文件/文本
        if "🖼" in content:
            self.text.insert('end', f"[{content}]\n", 'Img')
        elif "📄" in content:
            self.text.insert('end', f"[{content}]\n", 'File')
        else:
            self.text.insert('end', f"{content}\n", 'P')

        # 更新上一条消息记录
        self.last_message_id = from_user_id
        self.last_message_ts = current_ts

        self.text.text.see('end')
        self.win.root.update_idletasks()
        self.win.root.update()

    # 新增：窗口关闭清理
    def _on_close(self):
        if self.userid in self.server.open_dialogues:
            del self.server.open_dialogues[self.userid]
        self.win._close_win()

    def _send_img(self):
        file_path = filedialog.askopenfilename(
            title="请选择文件",
            initialdir=script_dir,
            filetypes=[("图片文件", "*.png;*.jpg;*.jpeg")]
        )
        if not file_path:
            return

        # JPEG压缩
        img = Image.open(file_path).convert("RGB")
        byte_buffer = BytesIO()
        img.save(byte_buffer, format="JPEG", quality=80)
        img_bytes = byte_buffer.getvalue()
        timestamp = str(time.time())
        timestr = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        current_ts = time.mktime(time.strptime(timestr, "%Y-%m-%d %H:%M:%S"))
        # 发送端判断：连续消息不显示头部
        show_header = ("self" != self.last_message_id) or (current_ts - self.last_message_ts > 60)

        # 写入本地文件+更新索引
        self.server.send_img(img_bytes, timestamp)
        img_placeholder = f"🖼_{timestamp}"

        # 选择性显示头部（时间+用户名）
        if show_header:
            self.text.insert('end', f"{timestr}", 'T_s')
            self.text.insert('end', f" >>> Me\n", 'UN_s')
        # 显示图片内容
        self.text.insert('end', f"[{img_placeholder}]\n", 'Img_s')

        # 写入历史聊天记录
        if self.userid not in self.server.historical_message:
            self.server.historical_message[self.userid] = []
        self.server.historical_message[self.userid].append({
            "ID": "self",
            "content": img_placeholder,
            "time": timestr
        })
        self.server.save_historical_message()

        # 发送加密图片消息
        img_base64_str = base64.encode(img_bytes).decode()
        self.server.send_image(
            target_hash=self.userid,
            target_key=self.user_key,
            img_base64=img_base64_str,
            timestamp=timestamp,
            time=timestr
        )
        # 更新最后消息状态
        self.last_message_id = "self"
        self.last_message_ts = current_ts

    def _open_img(self, event):
        text_widget = self.text.text
        click_index = text_widget.index(f"@{event.x},{event.y}")
        line_number = click_index.split(".")[0]
        full_line_text = text_widget.get(f"{line_number}.0", f"{line_number}.end")

        # 匹配图片时间戳
        pattern = r'_(\d+\.\d+)'
        match = re.search(pattern, full_line_text)
        if not match:
            return

        target_str = match.group(1)
        # 从索引获取本地文件路径
        img_path = self.server.get_imgs(target_str)

        # 校验文件
        if not img_path or not os.path.exists(img_path):
            print("图片文件不存在")
            return

        # 核心修复：直接传入 文件路径 给ImgShowWin（适配你的PixelUI组件）
        self.img_win = ImgShowWin(img_path)

    def _open_file(self, event):
        text_widget = self.text.text
        click_index = text_widget.index(f"@{event.x},{event.y}")
        line_number = click_index.split(".")[0]
        full_line_text = text_widget.get(f"{line_number}.0", f"{line_number}.end")

        # 匹配文件时间戳
        pattern = r'_(\d+\.\d+)'
        match = re.search(pattern, full_line_text)
        if not match:
            return

        target_str = match.group(1)
        # 获取文件完整路径
        file_path_local = self.server.get_files(target_str)

        # 校验文件
        if not file_path_local or not os.path.exists(file_path_local):
            print("文件不存在")
            return

        # 调用系统文件管理器，定位到目标文件
        import subprocess
        if os.name == 'nt':
            # Windows系统
            subprocess.run(f'explorer /select,"{file_path_local}"', shell=True)
        else:
            # macOS/Linux系统
            subprocess.run(['open', '-R', file_path_local] if sys.platform == 'darwin' else ['xdg-open',
                                                                                             os.path.dirname(
                                                                                                 file_path_local)])

    def _handle_key(self, e):
        self.text.text.focus_set()
        self.text.text.master.focus_set()  # 把焦点转移到父容器，光标移出Text

    # 修改：发送消息后保存历史
    def _send_message(self):
        content = self.message_text.get(0.0, 'end').strip()
        if not content:
            return
        self.message_text.delete(0.0, 'end')

        timestr = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        current_ts = time.mktime(time.strptime(timestr, "%Y-%m-%d %H:%M:%S"))
        # 发送端判断：连续消息不显示头部
        show_header = ("self" != self.last_message_id) or (current_ts - self.last_message_ts > 60)

        # 选择性显示头部（时间+用户名）
        if show_header:
            self.text.insert('end', f"{timestr}", 'T_s')
            self.text.insert('end', f" >>> Me\n", 'UN_s')
        # 显示消息内容
        self.text.insert('end', f"{content}\n", 'P_s')

        self.text.text.see('end')

        # 保存到历史记录
        if self.userid not in self.server.historical_message:
            self.server.historical_message[self.userid] = []
        self.server.historical_message[self.userid].append({
            "ID": "self",
            "content": content,
            "time": timestr
        })
        self.server.save_historical_message()

        self.server.send_message(target_hash=self.userid, target_key=self.user_key, text=content, time=timestr)
        # 更新最后消息状态
        self.last_message_id = "self"
        self.last_message_ts = current_ts
        print(content)

class UserFrame(ui.Module):
    def __init__(self, root, server,
                 user_show_config):
        super().__init__()
        self.server = server

        self.user_id, read_mark, name, head, last_time, last_content, self.user_key = user_show_config
        self.username = name
        if last_content:
            last_content = last_content[:16]

        self.main_frame = tk.Frame(root, width=290, height=50, bg=col_dict['bg'])
        self.main_frame.bind("<Double-Button-1>", self._open_dialogue)  # 左键双击

        self.user_head = ui.ImgLabel(self.main_frame, bg=col_dict['main'], img=head, size=(40, 40))
        self.user_head.place(x=5, y=5)
        self.user_head.label.bind("<Double-Button-1>", self._open_dialogue)  # 左键双击

        self.new_message_mark = tk.Frame(self.user_head.label, width=5, height=5, bg='red')
        if read_mark:
            self.new_message_mark.place(x=35, y=0)

        self.user_name = ui.Label(self.main_frame, text=self.username, font_size=8)
        self.user_name.place(x=50, y=5)

        self.time_label = ui.Label(self.main_frame, text=last_time, font_size=6, bg=col_dict['bg'],
                                   fg=col_dict['light'])
        self.time_label.place(x=290, y=5)
        w, h = ui.get_frame_size(self.main_frame, self.time_label.main_frame)
        self.time_label.place(x=285 - w, y=5)

        self.content_show = ui.Label(self.main_frame, text=f"{last_content}", font_size=10, bg=col_dict['bg'],
                                     fg=col_dict['main'])
        self.content_show.place(x=50, y=27)
        self.content_show.bind("<Double-Button-1>", self._open_dialogue)  # 左键双击

        self.user_dialogues = {}

    # ========== 关键修改：补全_open_dialogue逻辑 ==========
    def _open_dialogue(self, e):
        historical_dialogue = self.server.get_historical_dialogue(self.user_id)
        get_new_dialogue = self.server.get_new_dialogue(self.user_id)

        if historical_dialogue is None:
            historical_dialogue = []
        if get_new_dialogue is None:
            get_new_dialogue = []

        # 1. 创建对话框实例
        self.user_dialogues[self.user_id] = DialogueWin(
            self.user_id, self.user_key, self.server,
            historical_dialogue + get_new_dialogue, self.username
        )
        # 2. 注册到server的open_dialogues（关键：让handle_message能识别已打开的对话框）
        self.server.open_dialogues[self.user_id] = self.user_dialogues[self.user_id]

        # 3. 合并未读消息到历史消息，并清空未读（打开对话框后清除未读标记）
        if get_new_dialogue:
            if self.user_id not in self.server.historical_message:
                self.server.historical_message[self.user_id] = []
            # 追加未读消息到历史
            self.server.historical_message[self.user_id].extend(get_new_dialogue)
            # 清空该用户的未读消息
            self.server.new_message = [msg for msg in self.server.new_message if msg["ID"] != self.user_id]
            # 保存修改
            self.server.save_new_message()
            self.server.save_historical_message()

        # 刷新联系人列表（清除未读标记）
        top_root = self.main_frame.winfo_toplevel()
        if hasattr(top_root, 'master_win'):
            win_instance = top_root.master_win
            win_instance._contact()  # 调用Win类的刷新方法，清除未读标记

class ImgShowWin:
    def __init__(self, img, title='image_show', zoom=True, size=(320, 320)):
        self.zoom = zoom
        self.width, self.height = size

        self.win = ui.Toplevel(
            title=title, w=self.width, h=self.height, menu_config=None, page_config=None
        )

        w, h = ui.get_frame_size(self.win.root, self.win.screen_frame)
        self.img_l = ui.ImgLabel(self.win.screen_frame, img=img, bg=col_dict['bg'], size=(w - 10, h - 10))
        self.img_l.place(x=5, y=5)

class Win:
    def __init__(self, server):
        self.QR_win = None

        self.server = server
        # 新增：绑定主窗口到server，让server能触发刷新
        self.server.bind_main_win(self)

        self.win = ui.Win(
            title='EncryptChat',
            # 顶端菜单
            menu_config={
                "Contact": {"MyKey": self._show_my_key, "OtherKey": self._add_the_key},
            },
            page_config=['Contact', 'Setup'],
            w=320, h=530
        )

        self.win.root.master_win = self  # 利用你说的win.root是tk.Tk()实例

        self.user_list = self.server.get_contact("ALL")
        self.show_index = 0
        self.max_show = 8

        self.user_frames = []
        self._contact()
        self._setup()

    # 新增：刷新联系人列表
    def refresh_contact(self):
        self._contact()

    def _setup(self):
        def save_username(e):
            self.server.set_new_username(self.user_name_e.get().strip())
            print(f">>> 新用户名:{self.server.user_name}")

        self.head_label = ui.ImgLabel(self.win.screen_frames['Setup'], img=f"{config_path}/head.png", size=(100, 100))
        self.head_label.label.bind("<Button-1>", self._update_head)  # 左键点击
        self.head_label.place(x=5, y=5)
        ui.Label(self.win.screen_frames['Setup'], text="My_Username").place(x=110, y=5)
        self.user_name_e = ui.Entry(self.win.screen_frames['Setup'], width=10)
        self.user_name_e.place(x=110, y=30)
        self.user_name_e.insert(0, self.server.user_name)
        self.user_name_e.entry.bind("<Button-1>", lambda e: self.user_name_e.entry.focus_set())  # 左键点击
        self.win.screen_frames['Setup'].bind("<Button-1>", lambda e: self.win.screen_frames['Setup'].focus_set())
        # self.user_name_e.entry.bind("<FocusIn>", lambda e: print("控件获得焦点"))  # 控件获得焦点
        self.user_name_e.entry.bind("<FocusOut>", save_username)  # 控件失去焦点

    def _update_head(self, e):
        file_path = filedialog.askopenfilename(
            title="请选择文件",
            initialdir=script_dir,
            filetypes=[("图片文件", "*.png;*.jpg;*.jpeg")]
        )
        img = Image.open(file_path)
        img.save(f"{config_path}/head.png")
        self.head_label.update(img)

    def _contact(self):
        for user_frame in self.user_frames:
            user_frame.destroy()

        y = 5
        user_info = self.server.get_show_config()

        self.user_frames = []
        for i in range(self.max_show):
            index = i + self.show_index
            if index > len(user_info) - 1:
                break
            user_show_config = user_info[index]

            # 修复：server=server → self.server（原参数未定义）
            user_frame = UserFrame(self.win.screen_frames['Contact'],
                                   user_show_config=user_show_config, server=self.server)
            user_frame.bind("<MouseWheel>", self._mouse_wheel)  # Windows/macOS滚轮
            user_frame.place(x=5, y=y)
            self.user_frames.append(user_frame)
            y += 55

    def _mouse_wheel(self, e):
        user_info = self.server.get_show_config()
        if e.delta > 0:
            if self.show_index > 0:
                self.show_index -= 1
                self._contact()
        else:
            if self.show_index < len(user_info) - self.max_show:
                self.show_index += 1
                self._contact()

    def _show_my_key(self):
        public_key = self.server.public_bytes
        public_key_base64 = base64.encode(public_key).decode()
        qr_img = generate_qr(f"{public_key_base64}|{user_name}",
                             fill_color='black', back_color=col_dict['bg']
                             )

        if self.QR_win:
            self.QR_win.win._close_win()
        # 需要额外的信息，比如头像和用户名
        self.QR_win = ImgShowWin(qr_img, title="MyQR")

    def _add_the_key(self):
        self.screenshot = Screenshot()

        while self.screenshot.target_img is None:
            time.sleep(0.01)
            self.win.root.update()

        target_img = self.screenshot.target_img
        if not target_img:  # 取消截图时返回
            return

        try:
            de_public_key, username = decode_qr(target_img).split('|')
            self.server.add_contact(de_public_key, name=username)
        except:
            MessageBox(title="Error", message="No QR code detected.", mode='error')

        self.screenshot = None

    def mainloop(self):
        self.win.mainloop()

class Screenshot:
    def __init__(self):
        self.screen = ThreadSafeScreenshotManager()

        self.win = tk.Toplevel()
        self.win.attributes('-topmost', True)
        self.win.overrideredirect(True)
        self.img = self.screen.capture(0)
        brightness_enhancer = ImageEnhance.Brightness(self.img)
        self.img = brightness_enhancer.enhance(0.9)
        brightness_enhancer = ImageEnhance.Brightness(self.img)
        self.img_ = brightness_enhancer.enhance(0.6)
        self.photo = ImageTk.PhotoImage(self.img)
        self.img_label = tk.Label(self.win, image=self.photo)
        self.img_label.bind("<Double-Button-1>", self.close)  # 左键双击
        self.img_label.bind("<ButtonPress-1>", self.mark)  # 左键按下
        self.img_label.bind("<ButtonRelease-1>", self.cut)  # 左键释放
        self.img_label.bind("<B1-Motion>", self.move)  # 左键拖动
        self.img_label.pack()

        self.x0, self.y0, self.x1, self.y1 = 0, 0, 0, 0
        self.target_img = None

    def close(self, e):
        self.win.destroy()
        self.target_img = False

    def move(self, e):
        x, y = e.x, e.y
        self.x1, self.y1 = x, y

        x0, y0 = min(self.x0, self.x1), min(self.y0, self.y1)
        x1, y1 = max(self.x0, self.x1), max(self.y0, self.y1)

        target_img = self.img.crop((x0, y0, x1, y1))
        img_0 = self.img_.convert('RGB')
        img_0.paste(target_img, (x0, y0))
        self.photo = ImageTk.PhotoImage(img_0)
        self.img_label.configure(image=self.photo)

    def mark(self, e):
        x, y = e.x, e.y
        self.x0, self.y0 = x, y

    def cut(self, e):
        x, y = e.x, e.y
        self.x1, self.y1 = x, y

        x0, y0 = min(self.x0, self.x1), min(self.y0, self.y1)
        x1, y1 = max(self.x0, self.x1), max(self.y0, self.y1)

        self.target_img = self.img.crop((x0, y0, x1, y1))
        self.win.destroy()

if __name__ == '__main__':
    # 打包
    pkg = Pkg.ZN()
    # 编码
    base64 = Base64()
    # 非对称加密
    encryption = X25519Cipher()
    # 对称加密
    encryption_ = AesGcmCipher()

    # 哈希
    sha256hash = Sha256Hash()

    server = ServerFun()
    try:
        server.start()

    except:
        message = MessageBox(title="Error", message="Server not started.", mode='error', only=True)
        while message.only:
            time.sleep(0.1)
            message._root.update()
        exit()

    win = Win(server)
    win.mainloop()

