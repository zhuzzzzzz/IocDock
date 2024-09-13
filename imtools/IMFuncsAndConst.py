import configparser
import datetime
import os
import shutil
import socket
import sys


def get_manager_path():
    repository_path = os.environ.get("MANAGER_PATH", default='')
    if repository_path:
        if os.path.isdir(repository_path):
            return repository_path
        else:
            print(f'get_manager_path() failed, $MANAGER_PATH is not a valid directory.')
            exit(1)
    else:
        print(f'get_repository_path() failed, $MANAGER_PATH is not defined.')
        exit(1)
        # return os.getcwd()


#
# directory name or file name definition for IocManager.
TOOLS_DIR = 'imtools'
OPERATION_LOG_FILE = '.OperationLogs'

SNAPSHOT_PATH = os.path.join(get_manager_path(), TOOLS_DIR,
                             'ioc-snapshot')  # path for newest snapshot file of ioc.ini
CONFIG_FILE_NAME = 'ioc.ini'
REPOSITORY_DIR = 'ioc-repository'
MOUNT_DIR = 'ioc-for-docker'  # default directory for docker mounting
IOC_BACKUP_DIR = 'ioc-backup'  # version backup directory for ioc.ini file and other run-time log files
SWARM_BACKUP_DIR = 'swarm-backup'  # version backup directory for swarm

# source file format used by IOC.get_src_file()
DB_SUFFIX = ('.db',)
PROTO_SUFFIX = ('.proto',)
OTHER_SUFFIX = ('.im',)

#
# IOC settings.
DEFAULT_IOC = 'ST-IOC'
MODULES_PROVIDED = ['autosave', 'caputlog', 'status-ioc', 'status-os']
# asyn, stream device needs to be set separately for different hosts, so they are not supported by default.
DEFAULT_MODULES = 'autosave, caputlog, status-ioc'
PORT_SUPPORT = ('tcp/ip', 'serial')

#
# path definition in running container.
CONTAINER_TOP_PATH = os.path.join('/', 'opt', 'EPICS')
CONTAINER_IOC_PATH = os.path.join(CONTAINER_TOP_PATH, 'IOC')
CONTAINER_IOC_RUN_PATH = os.path.join(CONTAINER_TOP_PATH, 'RUN')

LOG_FILE_DIR = 'iocLog'  # directory for running iocLogServer in docker

#
# swarm orchestration settings.
SWARM_DIR = 'swarm'
IOC_SERVICE_FILE = 'compose-swarm.yaml'
GLOBAL_SERVICE_FILE = 'compose-swarm-init.yaml'
PREFIX_STACK_NAME = 'dals'


def try_makedirs(d, verbose=False):
    verbose = False
    try:
        os.makedirs(d)
    except Exception as e:
        if verbose:
            print(f'try_makedirs("{d}") failed, {e}.')
        return False
    else:
        if verbose:
            print(f'try_makedirs("{d}") Success.')
        return True


def file_remove(file_path, verbose=False):
    try:
        os.remove(file_path)
    except Exception as e:
        print(f'file_remove: "{file_path}" removed failed, {e}.')
    else:
        if verbose:
            print(f'file_remove: "{file_path}" removed.')


def dir_remove(dir_path, verbose=False):
    try:
        shutil.rmtree(dir_path)
    except shutil.Error as e:
        print(f'dir_remove: "{dir_path}" removed failed, {e}.')
    except FileNotFoundError as e:
        print(f'dir_remove: "{dir_path}" removed failed, {e}.')
    except Exception as e:
        print(f'dir_remove: "{dir_path}" removed failed, {e}.')
    else:
        if verbose:
            print(f'dir_remove: "{dir_path}" removed.')


# be careful of that whether the input path is relative or absolute
def file_copy(src, dest, mode='r', verbose=False):
    if not os.path.exists(src):
        print(f'file_copy: failed, "{src}" source file not found.')
        return False
    # if destination file exists, remove it.
    if os.path.exists(dest):
        if verbose:
            print(f'file_copy: destination "{dest}" exists, first remove it.')
        file_remove(dest, verbose)
    # if destination dir no exists, create it.
    dest_dir = os.path.dirname(dest)
    if not os.path.isdir(dest_dir):
        if verbose:
            print(f'file_copy: destination directory "{dest_dir}" not exists, first create it.')
        try_makedirs(dest_dir, verbose)
    #
    try:
        shutil.copy(src, dest)
    except PermissionError as e:
        print(f'file_copy: failed, {e}.')
        return False
    except Exception as e:
        print(f'file_copy: failed, {e}.')
        return False
    else:
        if verbose:
            print(f'file_copy: success, copy file from "{src}" to "{dest}.')
        mode_number = 0o000
        if 'r' in mode or 'R' in mode:
            mode_number += 0o444
            if verbose:
                print(f'file_copy: set "{dest}" as readable.')
        if 'w' in mode or 'W' in mode:
            mode_number += 0o220
            if verbose:
                print(f'file_copy: set "{dest}" as writable.')
        if 'x' in mode or 'X' in mode:
            mode_number += 0o110
            if verbose:
                print(f'file_copy: set "{dest}" as executable.')
        if mode_number != 0o000:
            os.chmod(dest, mode_number)
        return True


def dir_copy(source_folder, destination_folder, verbose=False):
    if os.path.exists(destination_folder):
        if verbose:
            print(f'dir_copy: destination folder "{destination_folder}" exists, first remove it.')
        dir_remove(destination_folder, verbose)
    try:
        shutil.copytree(source_folder, destination_folder)
    except shutil.Error as e:
        print(f'dir_copy: failed, {e}')
        return False
    else:
        if verbose:
            print(f'dir_copy: success, copy files from "{source_folder}" to "{destination_folder}".')
        return True


# return a normalized path or return a path relative to current work path if a relative path was given.
# use a default path if no input_path was given.
def relative_and_absolute_path_to_abs(input_path, default_path=None):
    if not default_path:
        default_path = ''
    if not input_path:
        input_path = default_path
    if not os.path.isabs(input_path):
        output_path = os.path.join(os.getcwd(), input_path)
    else:
        output_path = input_path
    output_path = os.path.normpath(output_path)
    return output_path


def condition_parse(condition: str, split_once=None):
    # set max_split to control how many parts to split the condition.
    if split_once:
        # if set, split once at most.
        c_s = condition.strip().split(sep='=', maxsplit=1)
    else:
        # if not set, split as much times as the number of '='.
        c_s = condition.strip().split(sep='=')
    # print(c_s)
    # condition should only be split one time
    if len(c_s) == 2 and len(c_s[0]) > 0:
        key = c_s[0].strip()
        value = c_s[1].strip()
        # print(key, value)
        return key, value
    else:
        return None, None


def multi_line_parse(input_str: str):
    lines = input_str.strip().split(sep='\n')
    res = []
    for item in lines:
        if item != '':
            res.append(item)
    return res


def format_normalize(raw_str: str):
    # a standard format of value, for example "ramper.db,name = xxx1" will be changed to "ramper.db, name=xxx1"
    raw_str = raw_str.replace(';', '\n')
    raw_str = '\n'.join(filter(None, raw_str.split('\n')))  # number of return char will be reduced to 1.
    raw_str = ' '.join(filter(None, raw_str.split(' ')))  # number of space char will be reduced to 1.
    raw_str = raw_str.replace(', ', ',')
    raw_str = raw_str.replace(' ,', ',')
    raw_str = raw_str.replace(' =', '=')
    raw_str = raw_str.replace('= ', '=')
    raw_str = raw_str.replace(' :', ':')
    raw_str = raw_str.replace(': ', ':')
    raw_str = raw_str.replace(',', ', ')
    return raw_str


#########################################################
# codes for monitoring untracked changes of ioc.ini.
def add_snapshot_file(name, verbose):
    file_path = os.path.join(get_manager_path(), REPOSITORY_DIR, name, CONFIG_FILE_NAME)
    log_path = os.path.join(SNAPSHOT_PATH, name)
    if os.path.isfile(file_path):
        conf = configparser.ConfigParser()
        if not conf.read(file_path):
            print(f'add_snapshot_file: Failed. Path "{file_path}" exists but not a valid configuration file.')
            return
        else:
            conf.set('IOC', 'snapshot', 'logged')
            with open(file_path, 'w') as f:
                conf.write(f)
        if file_copy(file_path, log_path, 'r', verbose):
            if verbose:
                print(f'add_snapshot_file: snapshot file of "{name}" successfully created.')
        else:
            if verbose:
                print(f'add_snapshot_file: failed, snapshot file of "{name}" created failed.')
    else:
        if verbose:
            print(f'add_snapshot_file: failed, source file "{file_path}" is not exist.')


def delete_snapshot_file(name, verbose):
    log_path = os.path.join(SNAPSHOT_PATH, name)
    if os.path.isfile(log_path):
        file_remove(log_path, verbose)
    else:
        if verbose:
            print(f'delete_snapshot_file: failed, file "{log_path}" to delete is not exist.')


def check_snapshot_file(name, verbose):
    file_path = os.path.join(get_manager_path(), REPOSITORY_DIR, name, CONFIG_FILE_NAME)
    log_path = os.path.join(SNAPSHOT_PATH, name)
    if not os.path.isfile(log_path):
        if verbose:
            print(f'check_snapshot_file: no snapshot file found for {name}, create a new one.')
        add_snapshot_file(name, verbose)
        return True
    else:
        with open(file_path, 'r') as f1, open(log_path, 'r') as f2:
            lines1 = f1.readlines()
            lines2 = f2.readlines()
            return lines1 == lines2


def operation_log():
    log_time = datetime.datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    log_command = ' '.join(sys.argv)
    log_user = os.getenv("USER")
    log_host = socket.gethostname()
    log_id = log_user + '@' + log_host
    log_str = '\t'.join([log_time, log_id, log_command])
    file_path = os.path.join(get_manager_path(), TOOLS_DIR, OPERATION_LOG_FILE)
    with open(file_path, 'a') as f:
        f.write(log_str + '\n')


if __name__ == '__main__':
    print(relative_and_absolute_path_to_abs(''))
