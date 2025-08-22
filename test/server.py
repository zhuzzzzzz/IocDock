import socket
import os
import sys
import threading
import time
from datetime import datetime


class UnixSocketServer:
    """UNIX 套接字服务器实现"""

    def __init__(self, socket_path: str):
        """
        :param socket_path: UNIX 套接字文件路径
        """
        self.socket_path = socket_path
        self.server_socket = None
        self.clients = {}
        self.running = True
        self.lock = threading.Lock()

    def cleanup_socket(self):
        """确保套接字文件不存在"""
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except Exception as e:
            print(f"清理套接字文件时出错: {e}")
            sys.exit(1)

    def handle_client(self, client_socket, client_address):
        """处理客户端连接"""
        client_id = f"client_{len(self.clients) + 1}"

        with self.lock:
            self.clients[client_socket] = {
                'id': client_id,
                'address': client_address,
                'connected_at': datetime.now(),
                'message_count': 0
            }

        print(f"[{datetime.now().strftime('%H:%M:%S')}] New client: {client_id}")

        try:
            # 发送欢迎消息
            client_socket.sendall(f"欢迎连接服务器! 你的ID: {client_id}\n".encode())

            while self.running:
                try:
                    # 接收数据 (最大4KB)
                    data = client_socket.recv(4096)
                    if not data:
                        # 客户端断开连接
                        break

                    message = data.decode().strip()
                    print(f"[{client_id}] 收到消息: {message}")

                    with self.lock:
                        self.clients[client_socket]['message_count'] += 1
                        self.clients[client_socket]['last_active'] = datetime.now()

                    # 处理命令
                    if message == "time":
                        # 返回当前时间
                        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        response = f"服务器时间: {current_time}\n"
                        client_socket.sendall(response.encode())
                    elif message == "stats":
                        # 返回服务器统计信息
                        with self.lock:
                            total_clients = len(self.clients)
                            response = f"在线客户端: {total_clients}\n"
                            client_socket.sendall(response.encode())
                    elif message == "quit":
                        # 断开连接
                        client_socket.sendall("再见!\n".encode())
                        break
                    else:
                        # 回显消息
                        client_socket.sendall(f"ECHO: {message}\n".encode())

                except ConnectionResetError:
                    break
                except Exception as e:
                    print(f"处理 {client_id} 时出错: {e}")
                    break

        finally:
            # 清理客户端
            with self.lock:
                if client_socket in self.clients:
                    del self.clients[client_socket]
            client_socket.close()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {client_id} 已断开连接")

    def accept_clients(self):
        """接受客户端连接并处理"""
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 接受来自 {client_address} 的连接")

                # 启动新的线程处理客户端
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()

            except OSError as e:
                if not self.running:
                    print("服务器正在关闭...")
                    break
                print(f"接受客户端时出错: {e}")
            except Exception as e:
                print(f"意外错误: {e}")
                self.stop()

    def console_interface(self):
        """服务器控制台接口"""
        print("服务器命令: status | stop | clients | quit")
        while self.running:
            try:
                command = input("服务器命令> ").strip().lower()

                if command == "status":
                    print(f"服务器状态: {'运行中' if self.running else '已停止'}")

                elif command == "stop":
                    print("正在停止服务器...")
                    self.stop()

                elif command == "clients":
                    with self.lock:
                        if not self.clients:
                            print("没有连接的客户端")
                        else:
                            print("当前连接的客户端:")
                            for sock, info in self.clients.items():
                                print(
                                    f"- ID: {info['id']}, 连接时间: {info['connected_at']}, 消息数: {info['message_count']}")

                elif command == "quit":
                    self.stop()

                else:
                    print(f"未知命令: {command}")

            except KeyboardInterrupt:
                print("\n使用 'stop' 命令停止服务器")

    def start(self):
        """启动服务器"""
        try:
            # 清理现有的套接字文件
            self.cleanup_socket()

            # 创建UNIX套接字
            self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

            # 绑定到套接字文件路径
            self.server_socket.bind(self.socket_path)

            # 设置权限 (可选)
            os.chmod(self.socket_path, 0o777)

            # 开始监听
            self.server_socket.listen(5)
            print(f"UNIX套接字服务器启动在 {self.socket_path}")
            print("按Ctrl+C进入控制台")

            # 启动控制台界面线程
            console_thread = threading.Thread(target=self.console_interface, daemon=True)
            console_thread.start()

            # 主接受循环
            self.accept_clients()

        except Exception as e:
            print(f"启动服务器失败: {e}")
            self.cleanup_socket()
            sys.exit(1)

    def stop(self):
        """停止服务器"""
        self.running = False

        # 关闭所有客户端连接
        with self.lock:
            for client_socket in list(self.clients.keys()):
                try:
                    client_socket.close()
                except:
                    pass
            self.clients.clear()

        # 关闭服务器套接字
        if self.server_socket:
            # 尝试在单独的线程中关闭套接字以解除阻塞
            threading.Thread(target=self.server_socket.close, daemon=True).start()

        # 清理套接字文件
        self.cleanup_socket()

        print("服务器已停止")
        sys.exit(0)


if __name__ == "__main__":
    # 配置套接字路径
    SOCKET_PATH = "/tmp/python_unix_socket_server.sock"

    server = UnixSocketServer(SOCKET_PATH)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()