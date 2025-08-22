import socket
import sys


def unix_socket_client(socket_path: str):
    """UNIX套接字客户端"""
    try:
        # 创建UNIX套接字
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        # 连接到服务器
        sock.connect(socket_path)
        print(f"已连接到 {socket_path}")


        try:
            while True:
                # 获取用户输入
                message = input("输入消息 (或输入 'quit' 退出): ")
                if not message:
                    continue

                # 发送消息
                sock.sendall(message.encode())

                if message.strip().lower() == "quit":
                    break

                # 接收响应
                response = sock.recv(4096).decode()
                print(f"服务器响应: {response.strip()}")

        except KeyboardInterrupt:
            print("\n强制退出客户端")
        finally:
            sock.close()
            print("连接已关闭")

    except ConnectionRefusedError:
        print(f"无法连接到 {socket_path} - 服务器可能未运行")
    except FileNotFoundError:
        print(f"套接字文件 {socket_path} 不存在")
    except Exception as e:
        print(f"客户端错误: {e}")
    finally:
        sys.exit(0)


if __name__ == "__main__":
    SOCKET_PATH = "/tmp/python_unix_socket_server.sock"
    unix_socket_client(SOCKET_PATH)