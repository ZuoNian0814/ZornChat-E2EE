"""
一、服务器准备：
    1. 生成固定 HMAC-SHA512 密钥，用以生成身份指纹，帮助用户验证服务器身份
    2. 支持密钥轮换，更换后自动通知所有在线用户，离线用户下次登录触发重新激活身份
    3. 指纹记录最后使用时间，支持管理员手动清理闲置指纹与套接字映射关系
    4. 用户上线时提交公钥哈希，服务器构建公钥哈希 - 套接字映射表
    5. 服务器仅存储用户公钥哈希、身份指纹、临时离线消息队列，不储存任何聊天记录、联系人关系
    6. 服务器对所有离线消息加密存储，设置 7 天自动过期清理，防止数据泄露

二、用户安装：
    1. 生成 AES-256 主密钥，存储至系统安全存储（Keychain/WinVault/TPM），替代环境变量避免泄露
    2. 主密钥用于本地所有文件加密解密，支持更换密钥，更换后自动遍历重加密所有本地文件
    3. 安装时禁用明文存储任何密钥，所有密钥文件均加密保护

三、用户注册：
    1. 使用 X25519 生成非对称密钥对（私钥、公钥），私钥加密存储于本地安全区域
    2. 对公钥生成 SHA-256 哈希，发送至服务器存储，作为用户唯一身份标识
    3. 用户本地生成公钥指纹，直接与对方验证，脱离服务器防止中间人攻击
    4. 服务器使用自身密钥 + 用户公钥哈希生成身份指纹，用于消息转发校验
    5. 支持重新生成密钥对，自动吊销旧密钥，服务器同步更新映射，防止私钥泄露

四、用户添加联系人：
    1. 公钥进行 Base64 编码后生成二维码，作为唯一身份凭证
    2. 双方互相扫描二维码，本地验证公钥指纹后添加为联系人
    3. 公钥解码后加密存储至本地文件，未添加联系人的用户消息将被软件屏蔽
    4. 屏蔽非联系人消息时提示「陌生用户发送消息，非本地联系人」，修正公钥泄露错误提示
    5. 服务器不提供任何添加联系人功能，仅通过线下二维码渠道添加

五、用户对话：
    1. 每次对话随机生成 AES-256-GCM 对称密钥，用于加密消息数据
    2. 使用对方公钥通过 X25519+ECIES 加密该随机对称密钥，保证前向保密
    3. 打包消息为 {'id_hash': 接收方公钥哈希，'my_hash': 发送方公钥哈希，'data': 加密数据，'key': 加密后的对称密钥，'nonce': 随机数，'tag': 校验标签} 的 JSON 数据
    4. 消息直接发送至服务器，禁止加密前压缩，修复侧信道攻击漏洞
    5. 服务器解析双方哈希，校验指纹合法性，无指纹则拦截并告警中间人攻击
    6. 服务器通过映射表转发消息，接收方离线则存入加密队列，在线直接套接字转发
    7. 接收方接收数据后，使用私钥解密得到对称密钥，通过 AES-GCM 验证并解密数据
    8. 按对方公钥哈希分类，未读消息加密存入本地文件，所有读写操作均加密解密
    9. 打开对话框时加载消息，未读消息标记为已读，统一存储在加密文件中
    10. 图片和文件支持另存为未加密版本，原始加密文件自动存储于本地，聊天记录关联文件索引

六、安全验证
    1. 用户本地直接展示公钥指纹，双方线下二维码核对，彻底防御中间人攻击
    2. 支持通过官方邮箱验证公钥哈希，服务器仅做匹配校验，不参与指纹生成
    3. 消息自带防重放序号、时间戳，过期消息自动丢弃
    4. 接收方自动校验消息完整性，篡改消息直接拦截并告警

七、加密 / 哈希 / 压缩算法
    1. 服务器指纹生成 - HmacSha512Hash：HMAC-SHA512 带密钥消息认证码，高安全接口签名
    2. 用户密钥对 - X25519Cipher：椭圆曲线密钥交换，现代顶级安全标准，搭配 ECIES 加密
    3. 数据加密密钥（唯一标准算法，无冗余多层加密）
     - AesGcmCipher：AEAD 认证加密，工业标准、防篡改、防重放、高性能，通信 / 本地存储唯一首选
    4. 传输压缩：禁用加密前压缩，防止 CRIME/BREACH 侧信道攻击
    5. 储存压缩（用户固定选择，禁止频繁切换降低性能开销）
     - zstd：Zstandard 算法，压缩率与速度平衡，本地存储默认方案

八、储存方式（后续优化为行分割文本文件，降低内存占用）
    1. 历史图片使用「时间戳」为文件名加密储存在本地磁盘～/images 中，「🖼_时间戳」为键的字典加密存储，关联聊天记录
    2. 历史文件使用「时间戳」为文件名加密储存在本地磁盘～/files 中，「📄_时间戳」为键的字典加密存储，关联聊天记录
    3. 聊天记录使用 {对方公钥哈希: [
        {"ID": 公钥哈希，"content": 消息内容（支持🖼_时间戳 /📄_时间戳关联）, "time": 2026-12-6 14:58:53}
    ]} 格式，全程加密存储
"""
import json
import queue
from io import BytesIO
from PIL import Image
import time, os
from Tool.EnDecode import Base64
from SocketModuleV2 import SocketServer
import PackageAnalys as Pkg

base64 = Base64()
server_config_path = f'server_config'
os.makedirs(server_config_path, exist_ok=True)

class Server(SocketServer):
    def __init__(self,
             ip: str='127.0.0.1',
             port: int=10276
         ):
        super().__init__(ip, port)

        # 离线未读消息储存在服务器磁盘中，等待用户取出
        self.all_new_message = {
            "473485df7d25491f8fa138f6538f49351aaed1b634c5c863d86d3f0571085aef": [{"ID": "444555", "content": "来自服务器的新消息", "time": "2026-12-6 14:58:53"}]
        }
        self.save_path = f"{server_config_path}/offline_new_message.zorn"
        if os.path.isfile(self.save_path):
            print("从本地磁盘加载未读聊天记录")
            with open(self.save_path, mode='rb') as f:
                content = f.read()
            note, data = pkg.unpack(content)
            self.all_new_message = json.loads(data.decode())
        else:
            # 保存到本地
            """形如:{
                "目标哈希": [{
                    'target_hash': '目标哈希',
                    'text': '文本内容',
                    'key': '解密密钥',
                    'time': '2026-04-29 22:36:47',
                    'from': '来源哈希'}
                }]
            }"""
            messages = {}
            messages_json = json.dumps(messages, ensure_ascii=False).encode()
            e_messages_data = pkg.pack(messages_json, data_note=[{"type": "new_message"}])
            with open(self.save_path, mode='wb') as f:
                f.write(e_messages_data)
            self.all_new_message = messages

        self.save_path = f"{server_config_path}/user_info.zorn"
        if os.path.isfile(self.save_path):
            print("从本地磁盘加载未读聊天记录")
            with open(self.save_path, mode='rb') as f:
                content = f.read()
            note, data = pkg.unpack(content)
            self.user_info = json.loads(data.decode())
        else:
            # 保存到本地
            """形如:{
                "目标哈希": {"name": 用户名, "head": 图像base64}
            }"""
            messages = {}
            messages_json = json.dumps(messages, ensure_ascii=False).encode()
            e_messages_data = pkg.pack(messages_json, data_note=[{"type": "new_message"}])
            with open(self.save_path, mode='wb') as f:
                f.write(e_messages_data)
            self.user_info = messages

        # 在线哈希/套接字映射字典，不在线的消息本地临时储存
        self.socket_dict = {}

    def handle_message(self, client_id: str, msg: bytes):
        """消息处理：输出前100字节，可自定义扩展"""
        # print(f"[服务器] 来自{client_ip}消息（前100字节）：{msg[:150]}")
        json_data = json.loads(msg)
        print(f"[服务器] 来自{client_id}：{msg[:100]}")
        data_type = json_data['type']
        content = json_data['content']
        if data_type == "public_hush":
            print(f"[后端] 绑定公钥哈希与套接字")
            self.socket_dict[content] = client_id
            self.socket_dict[client_id] = content
            # 遍历离线未读消息，全部发送给客户端
            new_message = self.all_new_message.get(content)
            if new_message:
                for item in new_message:
                    send_str = json.dumps(item, ensure_ascii=False).encode()
                    self.send_to(self.socket_dict[content], send_str)
                # 清空未读消息队列
                self.all_new_message[content] = []

                messages_json = json.dumps(self.all_new_message, ensure_ascii=False).encode()
                # encryption_steps暂时为空，后续从安全硬件中读取
                e_messages_data = pkg.pack(messages_json, data_note=[{"type": "new_message"}])
                with open(self.save_path, mode='wb') as f:
                    f.write(e_messages_data)
        elif data_type == "command":
            args = json_data.get('args')
        elif data_type == "user_head":
            self.user_info[self.socket_dict[client_id]] = content
            messages_json = json.dumps(self.user_info, ensure_ascii=False).encode()
            e_messages_data = pkg.pack(messages_json, data_note=[{"type": "new_message"}])
            with open(self.save_path, mode='wb') as f:
                f.write(e_messages_data)
            contacts = json_data["contact_hash"]
            user_info = {user_hash: self.user_info[user_hash] for user_hash in contacts if user_hash in self.user_info}
            message_json = {"type": "user_info", "content": user_info}
            send_str = json.dumps(message_json, ensure_ascii=False).encode()
            self.send_to(client_id, send_str)
            print(f"[后端] 发送用户联系人的头像：{contacts}")
        elif data_type == "send_message":
            # 转发消息
            target_hash = content['target_hash']
            # 添加来源字段
            json_data['content']['from'] = self.socket_dict[client_id]
            # 在线则直接转发
            if target_hash in self.socket_dict:
                send_str = json.dumps(json_data, ensure_ascii=False).encode()
                self.send_to(self.socket_dict[target_hash], send_str)
            else:   # 不在线储存本地
                print(f">>> 用户{target_hash}不在线，储存离线消息")
                if target_hash not in self.all_new_message:
                    self.all_new_message[target_hash] = [json_data]
                else:
                    self.all_new_message[target_hash].append(json_data)

                messages_json = json.dumps(self.all_new_message, ensure_ascii=False).encode()
                e_messages_data = pkg.pack(messages_json, data_note=[{"type": "new_message"}])
                with open(self.save_path, mode='wb') as f:
                    f.write(e_messages_data)
        elif data_type == "send_image":
            # 转发消息
            target_hash = content['target_hash']
            # 添加来源字段
            json_data['content']['from'] = self.socket_dict[client_id]
            # 在线则直接转发
            if target_hash in self.socket_dict:
                send_str = json.dumps(json_data, ensure_ascii=False).encode()
                self.send_to(self.socket_dict[target_hash], send_str)
            else:   # 不在线储存本地
                print(f">>> 用户{target_hash}不在线，储存离线消息")
                if target_hash not in self.all_new_message:
                    self.all_new_message[target_hash] = [json_data]
                else:
                    self.all_new_message[target_hash].append(json_data)

                messages_json = json.dumps(self.all_new_message, ensure_ascii=False).encode()
                e_messages_data = pkg.pack(messages_json, data_note=[{"type": "new_message"}])
                with open(self.save_path, mode='wb') as f:
                    f.write(e_messages_data)
        elif data_type == "send_file":
            # 转发消息
            target_hash = content['target_hash']
            # 添加来源字段
            json_data['content']['from'] = self.socket_dict[client_id]
            # 在线则直接转发
            if target_hash in self.socket_dict:
                send_str = json.dumps(json_data, ensure_ascii=False).encode()
                self.send_to(self.socket_dict[target_hash], send_str)
            else:   # 不在线储存本地
                print(f">>> 用户{target_hash}不在线，储存离线消息")
                if target_hash not in self.all_new_message:
                    self.all_new_message[target_hash] = [json_data]
                else:
                    self.all_new_message[target_hash].append(json_data)

                messages_json = json.dumps(self.all_new_message, ensure_ascii=False).encode()
                e_messages_data = pkg.pack(messages_json, data_note=[{"type": "new_message"}])
                with open(self.save_path, mode='wb') as f:
                    f.write(e_messages_data)

    def _remove_client(self, client_id: str):
        """清理客户端（唯一ID）"""
        if client_id in self.clients:
            info = self.clients[client_id]
            try: info["socket"].close()
            except: pass
            ip = info["ip"]
            del self.clients[client_id]
            print(f"[服务器] 断开 | ID:{client_id} | IP:{ip}")

            content = self.socket_dict[client_id]
            del self.socket_dict[client_id]
            del self.socket_dict[content]

if __name__ == '__main__':
    # 打包
    pkg = Pkg.ZN()

    server = Server()
    server.start()

    while server.running:
        time.sleep(0.1)