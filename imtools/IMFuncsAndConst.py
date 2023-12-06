import datetime
import json
import os
import shutil

CONFIG_FILE = 'ioc.ini'
REPOSITORY_TOP = 'ioc-repository'
CONTAINER_TOP_PATH = os.path.join('/', 'opt', 'EPICS')
CONTAINER_IOC_PATH = os.path.join(CONTAINER_TOP_PATH, 'IOC')
CONTAINER_IOC_RUN_PATH = os.path.join(CONTAINER_TOP_PATH, 'RUN')

DEFAULT_IOC = 'ST-IOC'
# asyn, stream device needs to be set separately for different hosts.
MODULES_PROVIDED = ['autosave', 'caputlog', 'ioc-status', 'os-status']
DEFAULT_MODULES = 'caputlog, ioc-status'

TIME_LOG_PATH = os.path.join(os.getcwd(), 'imtools', '.time')


def try_makedirs(d, verbose=False):
    verbose = False
    try:
        os.makedirs(d)
    except OSError as e:
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
    except OSError as e:
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
    else:
        if verbose:
            print(f'dir_remove: "{dir_path}" removed.')


def file_copy(src, dest, mode='r', verbose=False):
    if not os.path.exists(src):
        print(f'file_copy: failed, "{src}" source file not found.')
        return False
    try:
        shutil.copy(src, dest)
    except FileNotFoundError:
        print(f'file_copy: failed, "{src}" source file not found.')
        return False
    except PermissionError:
        # read-only files could not be copied(re-write), so first remove it.
        if verbose:
            print(f'file_copy: destination "{dest}" exists, first remove it.')
        file_remove(dest, verbose)
        file_copy(src, dest, mode, verbose)
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


def condition_parse(condition: str, max_split=None):
    # set max_split to control how many parts to split the condition.
    if max_split:
        # if set, split once at most.
        c_s = condition.strip().split(sep='=', maxsplit=1)
    else:
        # if not set, split as much as the number of '='.
        c_s = condition.strip().split(sep='=')
    # print(c_s)
    if len(c_s) == 2 and len(c_s[0]) > 0:
        key = c_s[0].strip()
        value = c_s[1].strip()
        # print(key, value)
        # a standard format of value, for example "ramper.db,name = xxx1" will be changed to "ramper.db, name=xxx1"
        value = ' '.join(filter(None, value.split(' ')))
        value = value.replace(', ', ',')
        value = value.replace(' ,', ',')
        value = value.replace(' =', '=')
        value = value.replace('= ', '=')
        value = value.replace(',', ', ')
        return key, value
    else:
        return None, None


# codes for monitoring change time for ioc.ini.
def read_time_log():
    log_file_path = TIME_LOG_PATH
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, 'r') as file:
                time_log = json.load(file)
        except Exception as e:
            print(f'read_time_log: failed to open log file, {e}.')
            time_log = {}
            # should make a copy of .time file here?
    else:
        time_log = {}
    return time_log


def log_time(name: str):
    log_file_path = TIME_LOG_PATH
    check_file_path = os.path.join(os.getcwd(), REPOSITORY_TOP, name, 'ioc.ini')
    time_log = read_time_log()
    if os.path.exists(check_file_path):
        modified_time = os.path.getmtime(check_file_path)
        modified_time = str(datetime.datetime.fromtimestamp(modified_time))
        time_log[name] = modified_time
        with open(log_file_path, 'w') as file:
            json.dump(time_log, file, indent=4)
    else:
        print(f'log_time: failed, file to log modification time "{check_file_path}" not exist.')


def delete_time_log(name: str):
    log_file_path = TIME_LOG_PATH
    time_log = read_time_log()
    if name in time_log.keys():
        time_log.pop(name)
    with open(log_file_path, 'w') as file:
        json.dump(time_log, file, indent=4)


def check_time_log(name: str):
    time_log = read_time_log()
    check_file_path = os.path.join(os.getcwd(), REPOSITORY_TOP, name, 'ioc.ini')
    if os.path.exists(check_file_path):
        modified_time = os.path.getmtime(check_file_path)
        modified_time = str(datetime.datetime.fromtimestamp(modified_time))
        if name not in time_log.keys():
            log_time(name)
            time_log = read_time_log()
        if modified_time == time_log[name]:
            return True
        else:
            return False
    else:
        print(f'check_time_log: failed, ioc.ini file for IOC "{name}" not exist.')
        return False
