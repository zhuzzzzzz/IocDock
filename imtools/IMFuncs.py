import os
import sys
import datetime
import shutil
import socket
import filecmp
import logging
from logging.handlers import RotatingFileHandler

from .IMConsts import get_manager_path, TOOLS_DIR, OPERATION_LOG_PATH, OPERATION_LOG_FILE


def try_makedirs(d, verbose=False):
    """
    Try to create a new directory at given path if not already exists.

    :param d: given path.
    :param verbose: verbosity.
    :return: Boolean value about whether the directory was successfully created.
    """
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
        if os.path.isdir(dest):
            dest = os.path.join(dest, os.path.basename(src))
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
        # if not set, split as many times as the number of '='.
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
    # return a standard format of value, for example "ramper.db,name = xxx1" will get "ramper.db, name=xxx1" as return.
    raw_str = raw_str.replace(';', '\n')
    raw_str = '\n'.join(filter(None, raw_str.split('\n')))  # number of return char will be reduced to 1.
    if raw_str.count('\n') >= 1:
        raw_str = '\n' + raw_str
    raw_str = ' '.join(filter(None, raw_str.split(' ')))  # number of space char will be reduced to 1.
    raw_str = raw_str.replace(', ', ',')
    raw_str = raw_str.replace(' ,', ',')
    raw_str = raw_str.replace(' =', '=')
    raw_str = raw_str.replace('= ', '=')
    raw_str = raw_str.replace(' :', ':')
    raw_str = raw_str.replace(': ', ':')
    raw_str = raw_str.replace(',', ', ')
    return raw_str


def dircmp_compare(dcmp, print_info=False):
    diff_flag = False
    res_str = f'diff {dcmp.left} {dcmp.right}\n'
    if dcmp.diff_files:
        diff_flag = True
        res_str += 'changed files: '
        for item in dcmp.diff_files:
            res_str += f'"{item}", '
        else:
            res_str = res_str.rstrip(', ')
            res_str += '.\n'
    if dcmp.left_only:
        diff_flag = True
        res_str += 'missing files and directories: '
        for item in dcmp.left_only:
            res_str += f'"{item}", '
        else:
            res_str = res_str.rstrip(', ')
            res_str += '.\n'
    if dcmp.right_only:
        diff_flag = True
        res_str += 'untracked files and directories: '
        for item in dcmp.right_only:
            res_str += f'"{item}", '
        else:
            res_str = res_str.rstrip(', ')
            res_str += '.\n'
    if print_info:
        print(res_str)
    for sub_dcmp in dcmp.subdirs.values():
        if dircmp_compare(sub_dcmp, print_info):
            diff_flag = True

    return diff_flag


def dir_compare(snapshot_dir, source_dir, print_info=False):
    compare_res = filecmp.dircmp(snapshot_dir, source_dir)
    return dircmp_compare(compare_res, print_info=print_info)
    # print('==============')
    # compare_res.report_full_closure()


#########################################################
def operation_log():
    # 生成日志内容
    log_time = datetime.datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    log_command = ' '.join(sys.argv)
    log_user = os.getenv("USER")
    log_host = socket.gethostname()
    log_id = f"{log_user}@{log_host}"
    log_str = '\t'.join([log_time, log_id, log_command]) + '\n'  # 自带换行符

    # 获取日志文件路径
    file_path = os.path.join(get_manager_path(), TOOLS_DIR, OPERATION_LOG_PATH, OPERATION_LOG_FILE)

    # 配置日志记录器
    logger = logging.getLogger('operation_logger')

    # 防止重复添加handler
    if not logger.handlers:
        # 设置循环日志处理器
        handler = RotatingFileHandler(
            filename=file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB滚动
            encoding='utf-8'
        )
        # 保持原始日志格式（仅记录纯消息）
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    # 记录日志
    logger.info(log_str)


if __name__ == '__main__':
    a = dir_compare('/home/zhu/docker/repository-IOC/imtools/ioc-snapshot/worker_test_1_1',
                    '/home/zhu/docker/repository-IOC/ioc-repository/worker_test_1_1', return_info=False)
    print()
