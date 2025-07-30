import os
import sys
import datetime
import shutil
import socket
import filecmp
import logging
from logging.handlers import RotatingFileHandler

from imutils.IMConfig import OPERATION_LOG_FILE_PATH


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
            print(f'try_makedirs("{d}"): Failed, {e}.')
        return False
    else:
        if verbose:
            print(f'try_makedirs("{d}"): Success.')
        return True


def file_remove(file_path, verbose=False):
    try:
        os.remove(file_path)
    except Exception as e:
        print(f'file_remove("{file_path}"): Failed, {e}.')
    else:
        if verbose:
            print(f'file_remove("{file_path}"): Success.')


def dir_remove(dir_path, verbose=False):
    try:
        shutil.rmtree(dir_path)
    except Exception as e:
        print(f'dir_remove("{dir_path}"): Failed, {e}.')
    else:
        if verbose:
            print(f'dir_remove("{dir_path}"): Success.')


def file_copy(src, dest, mode='r', verbose=False):
    """
    copy the file src to the file or directory dst.
    If dst specifies a directory, it must exist, the file will be copied into dst using the base filename from src.
    If dst specifies a directory not exist, dest will be considered as a file.
    If dst specifies a file that already exists, it will be replaced.

    :param src:
    :param dest:
    :param mode: a combination of "r", "w", "x" to set the file mode of current user
    :param verbose:
    :return: whether the execution was successful or not
    """
    if not os.path.isfile(src):
        print(f'file_copy: Failed, source "{src}" not found or is not file.')
        return False
    replace_flag = False
    # remove first if destination file exists(for some read-only files can not be replaced).
    if os.path.isfile(dest):
        if verbose:
            replace_flag = True
        file_remove(dest, verbose=False)
    elif os.path.isdir(dest):
        if os.path.isfile(os.path.join(dest, os.path.basename(src))):
            if verbose:
                replace_flag = True
            file_remove(os.path.join(dest, os.path.basename(src)), verbose=False)
    #
    try:
        res = shutil.copy(src, dest)
    except Exception as e:
        print(f'file_copy: Failed, {e}.')
        return False
    else:
        mode_number = 0o000
        if 'r' in mode or 'R' in mode:
            mode_number += 0o444
        if 'w' in mode or 'W' in mode:
            mode_number += 0o220
        if 'x' in mode or 'X' in mode:
            mode_number += 0o110
        if mode_number != 0o000:
            os.chmod(res, mode_number)
        else:
            os.chmod(res, 0o664)
        if verbose:
            print(f'file_copy: Success, {"replace" if replace_flag else "copy"} file '
                  f'from "{src}" to "{res}" and set mode="{"DEFAULT" if mode_number == 0o000 else mode}".')
        return True


def dir_copy(source_folder, destination_folder, verbose=False):
    if os.path.isdir(destination_folder):
        dir_remove(destination_folder, verbose=False)
    try:
        shutil.copytree(source_folder, destination_folder)
    except Exception as e:
        print(f'dir_copy: Failed, {e}')
        return False
    else:
        if verbose:
            print(f'dir_copy: Success, copy dir from "{source_folder}" to "{destination_folder}".')
        return True


def relative_and_absolute_path_to_abs(input_path, default_path=None):
    """
    return an absolute path or a relative path against current work path in normalized format.
    If no input_path was given use default_path.

    :param input_path:
    :param default_path:
    :return:
    """
    if not default_path:
        default_path = os.getcwd()
    if not input_path:
        input_path = default_path
    if not os.path.isabs(input_path):
        output_path = os.path.join(os.getcwd(), input_path)
    else:
        output_path = input_path
    return os.path.normpath(output_path)


def condition_parse(condition: str, split_once: bool = False):
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
    file_path = OPERATION_LOG_FILE_PATH
    if not os.path.isfile(file_path):
        with open(file_path, 'w'):
            pass

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
    file_copy('/home/zhu/docker/IocDock/README.md', '/home/zhu/abc', mode='r', verbose=True)
