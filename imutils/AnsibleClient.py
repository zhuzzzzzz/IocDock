import json
import socket
import struct

from imutils.AnsibleUtil import ansible_create_file, ansible_touch_dir
from imutils.IMConfig import SOCKET_PATH, NODE_IP_FILE


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


def client_check_connection():
    connection = False
    socket_path = SOCKET_PATH
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(socket_path)
    except Exception as e:
        print(f"Exception occurred while trying to connect socket server: {e}")
    else:
        connection = True
    finally:
        sock.close()
    return connection


def ansible_socket_client(req_to_send, verbose=True):
    response = {}
    socket_path = SOCKET_PATH
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(socket_path)
        send_message(sock, req_to_send)
        response = receive_message(sock)
        if response and response != 'invalid request':
            response = json.loads(response)
    except Exception as e:
        if verbose:
            print(f"Exception occurred while running socket clinet: {e}")
    finally:
        sock.close()
    return response


def set_up_ip_file():
    node_info = ansible_socket_client("node info")
    for node_name, node_info in node_info.items():
        ansible_create_file(NODE_IP_FILE, f'NODE_IP={node_info["ip"]}', node_name)


def set_up_dir():
    node_info = ansible_socket_client("node info")
    for node_name, node_info in node_info.items():
        if node_info.get('labels', None):
            for key, value in node_info.get('labels').items():
                if key == 'alertmanager' and value == 'true':
                    ansible_touch_dir('alertManager-data', node_name)
                elif key == 'grafana' and value == 'true':
                    pass
                elif key == 'loki' and value == 'true':
                    pass
                elif key == 'prometheus' and value == 'true':
                    pass
                elif key == 'registry' and value == 'true':
                    pass


if __name__ == "__main__":
    # if client_check_connection():
    #     print(ansible_socket_client("ioc info"))
    # print(ansible_socket_client("service info"))
    # print(ansible_socket_client("node info"))
    set_up_ip_file()
