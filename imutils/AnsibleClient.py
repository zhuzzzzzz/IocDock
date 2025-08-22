import json
import socket
import struct


def send_message(sock, message):
    if isinstance(message, str):
        message = message.encode('utf-8')
    header = struct.pack('<I', len(message))
    sock.sendall(header + message)


def receive_exact_len(sock, mlen, timeout=10):
    original_timeout = sock.gettimeout()
    if timeout is not None:
        sock.settimeout(timeout)
    data = b''
    try:
        while len(data) < mlen:
            tmp = sock.recv(min(4096, mlen - len(data)))
            if not tmp:
                return None
            data += tmp
        return data
    except socket.timeout as e:
        # 超时异常
        print(f"receive_exact_len: {e}")
        return None
    finally:
        if timeout is not None:
            sock.settimeout(original_timeout)


def receive_message(sock, header_len=4):
    header = receive_exact_len(sock, header_len)
    if header:
        data = receive_exact_len(sock, struct.unpack('<i', header)[0])
        if data:
            return data.decode()
        else:
            return None
    else:
        return None


def ansible_socket_client(req):
    response = {}
    socket_path = "/tmp/IocDock.sock"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(socket_path)
        send_message(sock, req)
        response = receive_message(sock)
        if response and response != 'invalid request':
            response = json.loads(response)
    except Exception as e:
        print(f"Exception occurred while running socket clinet: {e}")
    finally:
        sock.close()
    return response


if __name__ == "__main__":
    print(ansible_socket_client("ioc info"))
