import docker

from imutils.SocketClient import socket_client, client_check_connection
from imutils.AnsibleUtil import ansible_create_file, ansible_touch_dir
from imutils.IMConfig import NODE_IP_FILE


def set_up_file_and_dir_for_every_host():
    docker_client = docker.from_env()
    node_info = {}
    nodes = docker_client.nodes.list()
    for node in nodes:
        node_info[node.attrs['Description']['Hostname']] = {
            'ip': node.attrs['Status']['Addr'],
        }
    for node_name, node_info in node_info.items():
        ansible_create_file(NODE_IP_FILE, f'NODE_IP={node_info["ip"]}', node_name)
        ansible_touch_dir('alloy-data', node_name)
        ansible_touch_dir('IocDock-data', node_name)


def set_up_dir_according_to_labels():
    node_info = socket_client("node info")
    for node_name, node_info in node_info.items():
        if node_info.get('labels', None):
            for key, value in node_info.get('labels').items():
                if key == 'alertmanager' and value == 'true':
                    ansible_touch_dir('alertManager-data', node_name)
                elif key == 'grafana' and value == 'true':
                    ansible_touch_dir('grafana-data', node_name)
                elif key == 'loki' and value == 'true':
                    ansible_touch_dir('loki-data', node_name)
                elif key == 'prometheus' and value == 'true':
                    ansible_touch_dir('prometheus-data', node_name)
                elif key == 'registry' and value == 'true':
                    ansible_touch_dir('registry-data', node_name)


if __name__ == "__main__":
    if client_check_connection():
        print(socket_client("ioc info"))
    print(socket_client("service info"))
    print(socket_client("node info"))
    # set_up_file_and_dir_for_every_host()
    # set_up_dir_according_to_labels()
