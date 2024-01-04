import os
import re
import shutil

###
CONFIG_FILE_NAME = 'ioc.ini'
REPOSITORY_DIR = 'ioc-repository'
MOUNT_DIR = 'ioc-for-docker'
LOG_DIR = 'ioc-log'

###
CONTAINER_TOP_PATH = os.path.join('/', 'opt', 'EPICS')
CONTAINER_IOC_PATH = os.path.join(CONTAINER_TOP_PATH, 'IOC')
CONTAINER_IOC_RUN_PATH = os.path.join(CONTAINER_TOP_PATH, 'RUN')

DEFAULT_IOC = 'ST-IOC'
# asyn, stream device needs to be set separately for different hosts.
MODULES_PROVIDED = ['autosave', 'caputlog', 'status-ioc', 'status-os']
DEFAULT_MODULES = 'autosave, caputlog, status-ioc'
PORT_SUPPORT = ('tcp/ip', 'serial')

# source file format.
DB_SUFFIX = ('.db',)
PROTO_SUFFIX = ('.proto',)
OTHER_SUFFIX = ('.others',)

###
BACKUP_PATH = os.path.join(os.getcwd(), 'imtools', '.log')


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
    # if destination file exists, first remove it.
    if os.path.exists(dest):
        if verbose:
            print(f'file_copy: destination "{dest}" exists, first remove it.')
        file_remove(dest, verbose)
    # if destination dir no exists, first create it.
    dest_dir = os.path.dirname(dest)
    if not os.path.isdir(dest_dir):
        if verbose:
            print(f'file_copy: destination directory "{dest_dir}" not exists, first create it.')
        try_makedirs(dest_dir, verbose)
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


def condition_parse(condition: str, split_once=None):
    # set max_split to control how many parts to split the condition.
    if split_once:
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
        return key, value
    else:
        return None, None


def format_normalize(raw_str: str):
    # a standard format of value, for example "ramper.db,name = xxx1" will be changed to "ramper.db, name=xxx1"
    # space char will be reduced to 1.
    raw_str = ' '.join(filter(None, raw_str.split(' ')))
    raw_str = raw_str.replace(', ', ',')
    raw_str = raw_str.replace(' ,', ',')
    raw_str = raw_str.replace(' =', '=')
    raw_str = raw_str.replace('= ', '=')
    raw_str = raw_str.replace(' :', ':')
    raw_str = raw_str.replace(': ', ':')
    raw_str = raw_str.replace(',', ', ')
    return raw_str


def db_file_interpret(db_file, macro_substitutions):
    msl = []
    for item in macro_substitutions.split(','):
        key, val = condition_parse(item, True)
        if key:
            msl.append((f'$({key})', val))
        else:
            print(f'db_file_interpret, invalid macro_substitutions string "{macro_substitutions}".')
            return None
    print(msl)

    if not os.path.isfile(db_file):
        print(f'db_file_interpret, "{db_file}" to interpret not exists.')
        return None
    with open(db_file, 'r') as f:
        lines = f.readlines()
    name_pattern = r'\'([^\']*)\'|\"([^\"]*)\"'
    pv_list = []
    for line in lines:
        if line.strip().startswith('record'):
            match = re.search(name_pattern, line)
            name_string = 'unmatched record name'
            if match.group(1):
                name_string = match.group(1).strip("'")
            elif match.group(2):
                name_string = match.group(2).strip('"')
            else:
                pass
            for ms in msl:
                name_string = name_string.replace(ms[0], ms[1])
            pv_list.append(name_string)
    print(pv_list)
    return pv_list


#########################################################
# codes for monitoring untracked changes of ioc.ini.
def add_log_file(name, verbose):
    file_path = os.path.join(os.getcwd(), REPOSITORY_DIR, name, CONFIG_FILE_NAME)
    log_path = os.path.join(BACKUP_PATH, name)
    if os.path.isfile(file_path):
        if file_copy(file_path, log_path, 'r', verbose):
            if verbose:
                print(f'log_file: ioc.ini file of "{name}" logged successfully.')
            else:
                if verbose:
                    print(f'log_file: failed, ioc.ini file of "{name}" logged failed.')
    else:
        if verbose:
            print(f'log_file: failed, source file to log "{file_path}" is not exist.')


def delete_log_file(name, verbose):
    log_path = os.path.join(BACKUP_PATH, name)
    if os.path.isfile(log_path):
        file_remove(log_path, verbose)
    else:
        if verbose:
            print(f'delete_log_file: failed, delete file "{log_path}" not exist.')


def check_log_file(name, verbose):
    file_path = os.path.join(os.getcwd(), REPOSITORY_DIR, name, CONFIG_FILE_NAME)
    log_path = os.path.join(BACKUP_PATH, name)
    if not os.path.isfile(log_path):
        if verbose:
            print(f'check_log_file: no log file found for {name}, create a new one.')
        add_log_file(name, verbose)
        return True
    else:
        with open(file_path, 'r') as f1, open(log_path, 'r') as f2:
            lines1 = f1.readlines()
            lines2 = f2.readlines()
            return lines1 == lines2


if __name__ == '__main__':
    db_file_interpret('/home/zhu/docker/repository/ioc-repository/test/src/ramper.db',
                      "name=test, P= , R=:asyn, PORT=xxx, ADDR=xxx, IMAX=xxx, OMAX=xxx")
