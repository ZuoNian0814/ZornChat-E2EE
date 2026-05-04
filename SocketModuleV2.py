import socket
import threading
import queue
import struct
import time
import uuid

# ==================== 全局常量定义（仅需修改这里即可统一调整包头长度） ====================
HEADER_LENGTH = 8  # 包头占用字节数：4字节 = 32位整数
HEADER_FORMAT = '>Q'  # 对应32位无符号大端整数
"""
用途	HEADER_FORMAT	HEADER_LENGTH	整数位数	最大支持数据长度
1 字节长度头（极小包）	>B	1	8 位	255 字节
2 字节长度头（小包）	>H	2	16 位	65KB
4 字节长度头（通用）	>I	4	32 位	4GB
8 字节长度头（超大包）	>Q	8	64 位	无限（1.8 亿 TB）
"""
MAX_PACKET_SIZE = 5 * 1024 ** 2  # 单包最大长度1MB

# ==================== 通用工具函数 ====================
def pack_data(data: bytes) -> bytes:
    """打包：固定长度包头+数据，解决粘包"""
    header = struct.pack(HEADER_FORMAT, len(data))
    return header + data

# ==================== 服务器类 ====================
class SocketServer:
    def __init__(self, ip: str = '127.0.0.1', port: int = 10276):
        self.ip = ip
        self.port = int(port)
        # 核心：key=唯一客户端ID(UUID)，value={socket, ip}
        # 无任何IP依赖，纯唯一ID管理
        self.clients = {}
        self.server_socket = None
        self.running = False
        # 队列：全部使用 客户端ID 通信
        self.send_queue = queue.Queue()
        self.recv_queue = queue.Queue()

    def start(self):
        """启动服务器（接口不变）"""
        if self.running:
            return
        self.running = True

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.ip, self.port))
        self.server_socket.listen()

        threading.Thread(target=self._run_server, daemon=True).start()
        threading.Thread(target=self._send_thread, daemon=True).start()
        threading.Thread(target=self._handle_thread, daemon=True).start()
        print(f"[服务器] 启动 | IP:{self.ip} 端口:{self.port}")

    def _run_server(self):
        """监听连接，为每个客户端生成终身唯一ID"""
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                client_ip = addr[0]
                # 生成全局唯一ID（核心！同一IP无限生成不重复）
                client_id = str(uuid.uuid4())
                self.clients[client_id] = {"socket": conn, "ip": client_ip}
                print(f"[服务器] 新连接 | ID:{client_id} | IP:{client_ip}")
                # 启动专属接收线程（仅传唯一ID）
                threading.Thread(target=self._recv_client, args=(conn, client_id), daemon=True).start()
            except (socket.error, OSError):
                break

    def _recv_client(self, client_socket: socket.socket, client_id: str):
        """客户端接收线程：仅用唯一ID标识"""
        while self.running:
            try:
                header = self._recvall(client_socket, HEADER_LENGTH)
                if not header: break
                data_len = struct.unpack(HEADER_FORMAT, header)[0]
                data = self._recvall(client_socket, data_len)
                if not data: break
                # 接收队列：只存 唯一ID + 数据
                self.recv_queue.put((client_id, data))
            except Exception:
                break
        self._remove_client(client_id)

    def _send_thread(self):
        """发送线程：从队列取【唯一ID】发送数据"""
        while self.running:
            try:
                # 队列格式：(客户端ID, 数据)
                client_id, data = self.send_queue.get(timeout=1)
                if client_id not in self.clients: continue
                packed_data = pack_data(data)
                self.clients[client_id]["socket"].sendall(packed_data)
            except queue.Empty:
                continue
            except Exception:
                self._remove_client(client_id)

    def _handle_thread(self):
        """处理线程：回调【唯一ID】，精准区分客户端"""
        while self.running:
            try:
                client_id, data = self.recv_queue.get(timeout=1)
                # 核心回调：用唯一ID标识客户端
                self.handle_message(client_id, data)
            except queue.Empty:
                continue

    def _recvall(self, sock: socket.socket, length: int) -> bytes | None:
        data = b""
        while len(data) < length:
            chunk = sock.recv(min(length - len(data), MAX_PACKET_SIZE))
            if not chunk: return None
            data += chunk
        return data

    def _remove_client(self, client_id: str):
        """清理客户端（唯一ID）"""
        if client_id in self.clients:
            info = self.clients[client_id]
            try: info["socket"].close()
            except: pass
            ip = info["ip"]
            del self.clients[client_id]
            print(f"[服务器] 断开 | ID:{client_id} | IP:{ip}")

    # ===================== 核心对外接口（唯一ID） =====================
    def send_to(self, client_id: str, data: bytes):
        """
        向【指定唯一ID】的客户端发消息
        （同一主机的多个客户端，ID不同，精准发送）
        """
        if client_id in self.clients:
            self.send_queue.put((client_id, data))

    def handle_message(self, client_id: str, msg: bytes):
        """
        消息回调：参数=【客户端唯一ID】+ 数据
        你可以精准知道是哪个客户端发的消息
        """
        print(f"[服务器] 客户端{client_id} 消息：{msg[:100]}")

    def close(self):
        """关闭服务器（接口不变）"""
        if not self.running: return
        self.running = False
        for cid in list(self.clients.keys()):
            self._remove_client(cid)
        try:
            if self.server_socket: self.server_socket.close()
        except: pass
        print("[服务器] 已关闭")

# ==================== 客户端类 ====================
class SocketClient:
    def __init__(self, server_ip: str, server_port: int):
        self.server_ip = server_ip
        self.server_port = int(server_port)
        self.client_socket = None
        self.running = False
        # 线程安全队列
        self.send_queue = queue.Queue()
        self.recv_queue = queue.Queue()

    def start(self):
        """启动客户端（独立线程，不阻塞主进程）"""
        if self.running:
            return
        self.running = True

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((self.server_ip, self.server_port))

        # 启动核心守护线程
        threading.Thread(target=self._recv_thread, daemon=True).start()
        threading.Thread(target=self._send_thread, daemon=True).start()
        threading.Thread(target=self._handle_thread, daemon=True).start()
        print(f"[客户端] 连接服务器成功 | {self.server_ip}:{self.server_port}")

    def _recv_thread(self):
        """独立接收线程：接收服务器数据"""
        while self.running:
            try:
                header = self._recvall(HEADER_LENGTH)
                if not header:
                    break
                data_len = struct.unpack(HEADER_FORMAT, header)[0]
                data = self._recvall(data_len)
                if not data:
                    break
                self.recv_queue.put(data)
            except Exception:
                break
        self.close()

    def _send_thread(self):
        """异步发送线程：循环处理发送队列"""
        while self.running:
            try:
                data = self.send_queue.get(timeout=1)
                packed_data = pack_data(data)
                self.client_socket.sendall(packed_data)
            except queue.Empty:
                continue
            except Exception:
                break
        self.close()

    def _handle_thread(self):
        """消息处理线程：从队列取数据并执行handle_message"""
        while self.running:
            try:
                data = self.recv_queue.get(timeout=1)
                self.handle_message(data)
            except queue.Empty:
                continue

    def _recvall(self, length: int) -> bytes | None:
        """循环接收指定长度的字节数据"""
        data = b""
        while len(data) < length:
            chunk = self.client_socket.recv(min(length - len(data), MAX_PACKET_SIZE))
            if not chunk:
                return None
            data += chunk
        return data

    def send(self, data: bytes):
        """向服务器发送数据（仅入队列，异步发送）"""
        self.send_queue.put(data)

    def handle_message(self, msg: bytes):
        """消息处理：输出前100字节，可自定义扩展"""
        print(f"[客户端] 收到消息（前100字节）：{msg[:100]}")

    def close(self):
        """断开连接，释放资源"""
        if not self.running:
            return
        self.running = False
        try:
            self.client_socket.close()
        except:
            pass
        print("[客户端] 已断开连接")

# ==================== 测试示例 ====================
if __name__ == '__main__':
    # 启动服务器
    server = SocketServer()
    server.start()
    time.sleep(1)

    # 启动客户端
    client = SocketClient("127.0.0.1", 10276)
    client.start()
    time.sleep(1)

    # 交互测试
    while True:
        try:
            msg = input("输入消息（输入e退出）：")
            if msg == 'e':
                server.close()
                client.close()
                break
            client.send(msg.encode())
            time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n程序退出")
            server.close()
            client.close()
            break