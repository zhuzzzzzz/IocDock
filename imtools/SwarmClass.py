import os
import yaml
import subprocess
from tabulate import tabulate

from imtools.IMFuncsAndConst import (CONTAINER_IOC_RUN_PATH, LOG_FILE_DIR, MOUNT_DIR, INIT_SERVICE_FILE, SWARM_DIR,
                                     CONFIG_FILE_NAME, IOC_SERVICE_FILE, PREFIX_STACK_NAME, REPOSITORY_DIR,
                                     relative_and_absolute_path_to_abs, try_makedirs, get_manager_path, )


class SwarmManager:
    def __init__(self):
        repository_path = os.path.join(get_manager_path(), REPOSITORY_DIR)
        self.services = {item: SwarmService(item) for item in os.listdir(repository_path)}

    def show_info(self):
        raw_print = [["IOC", "Service", "Status", ], ]
        for item in self.services.values():
            if item.is_available:
                raw_print.append([item.ioc_name, item.service_name, item.current_state])
        print(tabulate(raw_print, headers="firstrow", tablefmt='plain'))
        print('')

    @staticmethod
    def gen_global_compose_file(base_image, mount_dir):
        yaml_data = {
            'services': {},
            'networks': {},
        }
        # add iocLogServer service for host.
        temp_yaml = {
            'image': base_image,
            'tty': True,
            'networks': ['hostnet'],
            'volumes': [
                {
                    'type': 'bind',
                    'source': f'./{os.path.join(LOG_FILE_DIR)}',
                    'target': f'{os.path.join(CONTAINER_IOC_RUN_PATH, LOG_FILE_DIR)}',
                },
                {
                    'type': 'bind',
                    'source': '/etc/localtime',
                    'target': '/etc/localtime',
                    'read_only': True
                },  # set correct timezone for linux kernel
            ],
            'entrypoint': [
                'bash',
                '-c',
                f'. ~/.bash_aliases; '
                f'export EPICS_IOC_LOG_FILE_NAME='
                f'{os.path.join(CONTAINER_IOC_RUN_PATH, LOG_FILE_DIR, "$$(hostname).ioc.log")}; '
                f'echo run iocLogServer; iocLogServer'
            ],
            # 'environment': {
            #     'EPICS_IOC_LOG_FILE_NAME':
            #         f'{os.path.join(CONTAINER_IOC_RUN_PATH, LOG_FILE_DIR, f"$$(hostname).ioc.log")}',
            # },
            'deploy': {
                'mode': 'global',
                'restart_policy':
                    {
                        'window': '10s',
                    },
                'update_config':
                    {
                        'parallelism': 1,
                        'delay': '10s',
                        'failure_action': 'rollback',
                    }
            }
        }
        yaml_data['services'].update({f'srv-log': temp_yaml})
        # add other global services for host here.

        # add network for each stack.
        temp_yaml = {
            'external': True,
            'name': 'host',
        }
        yaml_data['networks'].update({f'hostnet': temp_yaml})

        mount_path = relative_and_absolute_path_to_abs(mount_dir, '.')
        top_path = os.path.join(mount_path, MOUNT_DIR, 'swarm')
        # make directory for iocLogServer
        try_makedirs(os.path.join(top_path, LOG_FILE_DIR))
        # write yaml file
        file_path = os.path.join(top_path, INIT_SERVICE_FILE)
        with open(file_path, 'w') as file:
            yaml.dump(yaml_data, file, default_flow_style=False)

    @staticmethod
    def get_deployed_services():
        result = subprocess.run(
            ['docker', 'service', 'ls', '-f', f'label=com.docker.stack.namespace={PREFIX_STACK_NAME}', '--format',
             '{{.Name}}'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output_list = result.stdout.splitlines()
        return output_list

    @staticmethod
    def show_deployed_services():
        os.system(f'docker stack ps -f "desired-state=running" {PREFIX_STACK_NAME}')

    @staticmethod
    def show_deployed_info():
        os.system(f'docker stack ps {PREFIX_STACK_NAME}')

    @staticmethod
    def show_deployed_machines():
        os.system('docker node ls')

    @staticmethod
    def show_join_tokens():
        os.system('docker swarm join-token manager')
        os.system('docker swarm join-token worker')


class SwarmService:
    def __init__(self, ioc_name):
        self.ioc_name = ioc_name
        self.ioc_path = os.path.join(get_manager_path(), '..', MOUNT_DIR, SWARM_DIR, self.ioc_name)
        self.service_name = f'{PREFIX_STACK_NAME}_srv-{ioc_name}'

    def __repr__(self):
        return f'SwarmService("{self.ioc_name}")'

    @property
    def is_available(self, verbose=False):
        if os.path.isfile(os.path.join(self.ioc_path, CONFIG_FILE_NAME)):
            if os.path.isfile(os.path.join(self.ioc_path, IOC_SERVICE_FILE)):
                flag = True
            else:
                flag = False
                if verbose:
                    print(f'SwarmService("{self.ioc_name}").is_available: File "{IOC_SERVICE_FILE}" not exists.')
        else:
            flag = False
            if verbose:
                print(f'SwarmService("{self.ioc_name}").is_available: File "{CONFIG_FILE_NAME}" not exists.')
        return flag

    @property
    def is_deployed(self):
        if self.service_name in SwarmManager.get_deployed_services():
            return True
        else:
            return False

    @property
    def current_state(self):
        if self.is_deployed:
            result = subprocess.run(
                ['docker', 'service', 'ps', '-f', f'desired-state=Running', '--format', '{{.CurrentState}}',
                 self.service_name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.stdout
        else:
            if self.is_available:
                return 'Available but not deployed'
            else:
                return 'Not Available'

    def deploy(self):
        if self.is_available:
            if self.is_deployed:
                print(f'SwarmService("{self.ioc_name}").deploy_service: Service has already been deployed.')
            else:
                print(f'SwarmService("{self.ioc_name}").deploy_service: Service deploying ... ')
                command = (f'cd {self.ioc_path}; '
                           f'docker stack deploy --compose-file {IOC_SERVICE_FILE} {PREFIX_STACK_NAME}')
                os.system(command)

        else:
            print(f'SwarmService("{self.ioc_name}").deploy_service: Failed to deploy, service is not available.')

    def remove(self):
        if self.is_deployed:
            print(f'SwarmService("{self.ioc_name}").remove_service: Removing this service.')
            os.system(f'docker service rm {self.service_name}')
        else:
            print(f'SwarmService("{self.ioc_name}").remove_service: Failed to remove, service is not deployed.')

    def show_info(self):
        if self.is_deployed:
            os.system(f'docker service inspect {self.service_name} --pretty')
        else:
            print(f'No info for "{self.ioc_name}" as it has not been deployed yet.')

    def show_ps(self):
        if self.is_deployed:
            os.system(f'docker service ps {self.service_name}')
        else:
            print(f'No info for "{self.ioc_name}" as it has not been deployed yet.')

    def get_logs(self):
        if self.is_deployed:
            result = subprocess.run(['docker', 'service', 'logs', self.service_name, '--raw'],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            ans = f'Logs for "{self.ioc_name}":\t\n#################\n{result.stdout}#################\n{result.stderr}'
            return ans
        else:
            print(f'No logs for "{self.ioc_name}" as it has not been deployed yet.')


if __name__ == '__main__':
    # SwarmManager.gen_global_compose_file(base_image='base:beta-0.2.2', mount_dir='/home/zhu/docker/')
    # SwarmManager.show_deployed_services()
    # SwarmManager.show_join_tokens()
    # SwarmManager.show_deployed_info()
    # SwarmManager.show_deployed_machines()
    # print(SwarmManager.get_deployed_services())
    # s = SwarmService("worker-standard_1")
    # # print(s.get_logs())
    # s.show_ps()
    # s.show_info()
    # print(s.current_state)
    SwarmManager.show_deployed_info()
