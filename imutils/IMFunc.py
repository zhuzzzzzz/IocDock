import os
import re
import sys
import filecmp
import datetime
import shutil
import socket
import logging
import subprocess
from logging.handlers import RotatingFileHandler
from imutils.IMConfig import OPERATION_LOG_FILE_PATH
from imutils.IMError import IMFileTypeError


def check_ioc_name(name):
    """
    Check whether the given IOC name is safe to be used as a path component.

    An IOC name is used as a directory name and is also passed to shell commands,
    so characters that are special to the shell or to path resolution have to be
    rejected here.

    :param name: IOC name to be checked.
    :return: Boolean value about whether the name is valid.
    """
    if not isinstance(name, str) or not re.fullmatch(
        r"[A-Za-z0-9_][A-Za-z0-9_.-]*", name
    ):
        print(
            f'check_ioc_name: Failed. Invalid IOC name "{name}", a name should start '
            f'with a letter, a digit or "_", and can only contain letters, digits, '
            f'and the characters "_.-".'
        )
        return False
    return True


def try_makedirs(d, verbose=False):
    """
    Try to create a new directory at given path if not already exists.

    :param d: given path.
    :param verbose: verbosity.
    :return: Boolean value about whether the directory was successfully created.
    """
    try:
        os.makedirs(d)
    except FileExistsError:
        if verbose:
            print(f'try_makedirs("{d}"): Skipped, already exists.')
        return False
    except Exception as e:
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


def file_copy(src, dest, mode="r", verbose=False):
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
        print(f"file_copy: Failed, {e}.")
        return False
    else:
        mode_number = 0o000
        if "r" in mode or "R" in mode:
            mode_number += 0o444
        if "w" in mode or "W" in mode:
            mode_number += 0o220
        if "x" in mode or "X" in mode:
            mode_number += 0o110
        if mode_number != 0o000:
            os.chmod(res, mode_number)
        else:
            os.chmod(res, 0o664)
        if verbose:
            print(
                f'file_copy: Success, {"replace" if replace_flag else "copy"} file '
                f'from "{src}" to "{res}" and set mode="{"DEFAULT" if mode_number == 0o000 else mode}".'
            )
        return True


def dir_copy(source_folder, destination_folder, verbose=False):
    if os.path.isdir(destination_folder):
        dir_remove(destination_folder, verbose=False)
    try:
        shutil.copytree(source_folder, destination_folder)
    except Exception as e:
        print(f"dir_copy: Failed, {e}")
        return False
    else:
        if verbose:
            print(
                f'dir_copy: Success, copy dir from "{source_folder}" to "{destination_folder}".'
            )
        return True


def _scan_tree(root):
    """
    Collect all files and symbolic links under the given directory recursively.

    Directories themselves are not collected, so that an empty directory existing
    only on one side is not a difference, which is how git behaves.

    :param root: path to the directory to be scanned.
    :return: a dict mapping relative path to a comparable feature tuple.
    :raise IMFileTypeError: an entry whose content can not be compared was found.
    :raise OSError: the tree could not be read. This also happens when another
                    process removes an entry while the tree is being scanned, as
                    an entry is stat'ed after it was listed.
    """
    entries = {}
    stack = [("", root)]
    while stack:
        rel_dir, abs_dir = stack.pop()
        with os.scandir(abs_dir) as it:
            for entry in it:
                rel_path = os.path.join(rel_dir, entry.name)
                # a symbolic link has to be tested first. It is a blob to git no
                # matter what it points to, and neither is_dir() nor is_file()
                # below answers True for it while links are not followed, so a
                # link tested later would end up in the unsupported branch.
                if entry.is_symlink():
                    # git stores a symbolic link as its target string, so the
                    # target is the whole content there is to compare for a link.
                    entries[rel_path] = ("link", os.readlink(entry.path))
                elif entry.is_dir(follow_symlinks=False):
                    stack.append((rel_path, entry.path))
                elif entry.is_file(follow_symlinks=False):
                    # git only tracks the executable bit of the owner in a file mode,
                    # the other permission bits are not a difference to git.
                    entries[rel_path] = (
                        "file",
                        bool(entry.stat(follow_symlinks=False).st_mode & 0o100),
                    )
                else:
                    raise IMFileTypeError(
                        f'"{entry.path}" is neither a regular file, a directory nor '
                        f"a symbolic link, its content can not be compared"
                    )
    return entries


def path_compare(path_a, path_b, print_diff=False, verbose=False):
    """
    Compare two files or two directories by content and tell whether they are
    identical, as a replacement of the command "git diff --no-index --quiet".

    What counts as a difference follows what git reports: file content, the
    executable bit of the owner, the target of a symbolic link, and the set of
    existing files. Other permission bits, ownership, timestamps and directories
    holding no file are not differences. Unlike git, the result does not depend on
    any git configuration such as "core.fileMode".

    A path that can not be read is reported as a difference rather than raised,
    just as the git command did by returning a non-zero exit code. This covers the
    case that another process rewrites one of the given directories while the
    comparison is running, which happens whenever dir_copy() replaces a directory
    being polled.

    :param path_a: path to the first file or directory.
    :param path_b: path to the second file or directory.
    :param print_diff: whether to show a readable diff of the two paths, which is
                       done by running git, as reproducing its output here is not
                       the purpose of this function.
    :param verbose: verbosity.
    :return: Boolean value about whether the two paths hold identical content,
             True when there is no difference between them.
    """
    if print_diff:
        # the list form is used instead of os.system(), otherwise the paths are
        # pasted into a shell command line unquoted. "--no-index" implies
        # "--exit-code", so the return code tells whether a difference was found.
        command = ["git", "diff", "--no-index", path_a, path_b]
        if verbose:
            print(" ".join(command))
        try:
            return subprocess.run(command).returncode == 0
        except OSError as e:
            print(f'path_compare("{path_a}", "{path_b}"): Failed to run git, {e}.')
            return False
    try:
        if os.path.isdir(path_a) and os.path.isdir(path_b):
            entries_a = _scan_tree(path_a)
            entries_b = _scan_tree(path_b)
            if entries_a != entries_b:
                # this single comparison already covers the set of paths, the type
                # of every entry, the executable bit of every file and the target
                # of every symbolic link, as a link's target string is its whole
                # content to git.
                result = False
            else:
                # only regular files are left to be read, their content is the one
                # thing the feature tuples above do not hold. Symbolic links must
                # stay out of here, filecmp.cmp() would follow them and compare the
                # content of what they point to, which git does not do.
                result = all(
                    filecmp.cmp(
                        os.path.join(path_a, rel),
                        os.path.join(path_b, rel),
                        shallow=False,
                    )
                    for rel, feature in entries_a.items()
                    if feature[0] == "file"
                )
        elif os.path.isfile(path_a) and os.path.isfile(path_b):
            result = os.stat(path_a).st_mode & 0o100 == os.stat(
                path_b
            ).st_mode & 0o100 and filecmp.cmp(path_a, path_b, shallow=False)
        else:
            # one of them does not exist, or one is a file while another is a directory.
            result = False
    except IMFileTypeError as e:
        # a file that can not be compared is a problem of the project itself and
        # will not go away by itself, always report it.
        print(f'path_compare("{path_a}", "{path_b}"): Failed, {e.message}.')
        return False
    except OSError as e:
        # not readable, or removed by another process during the comparison. The
        # git command reported this as a difference and printed nothing, keep both:
        # a directory being rewritten by another process would otherwise make the
        # polling server write to the log every round.
        if verbose:
            print(f'path_compare("{path_a}", "{path_b}"): Failed, {e}.')
        return False
    else:
        if verbose:
            print(
                f'path_compare("{path_a}", "{path_b}"): '
                f'{"identical" if result else "different"}.'
            )
        return result


def relative_path_to_abs(input_path):
    """
    return an absolute path in normalized format against current work path of an absolute path or a relative path.

    :param input_path:
    :return:
    """
    if not os.path.isabs(input_path):
        output_path = os.path.join(os.getcwd(), input_path)
    else:
        output_path = input_path
    return os.path.normpath(output_path)


def condition_parse(condition: str, split_once: bool = False):
    # set max_split to control how many parts to split the condition.
    if split_once:
        # if set, split once at most.
        c_s = condition.strip().split(sep="=", maxsplit=1)
    else:
        # if not set, split as many times as the number of '='.
        c_s = condition.strip().split(sep="=")
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
    lines = input_str.strip().split(sep="\n")
    res = []
    for item in lines:
        if item != "":
            res.append(item)
    return res


def format_normalize(raw_str: str):
    # return a standard format of value, for example "ramper.db,name = xxx1" will get "ramper.db, name=xxx1" as return.
    raw_str = raw_str.replace(";", "\n")
    raw_str = "\n".join(
        filter(None, raw_str.split("\n"))
    )  # number of return char will be reduced to 1.
    if raw_str.count("\n") >= 1:
        raw_str = "\n" + raw_str
    raw_str = " ".join(
        filter(None, raw_str.split(" "))
    )  # number of space char will be reduced to 1.
    raw_str = raw_str.replace(", ", ",")
    raw_str = raw_str.replace(" ,", ",")
    raw_str = raw_str.replace(" =", "=")
    raw_str = raw_str.replace("= ", "=")
    raw_str = raw_str.replace(" :", ":")
    raw_str = raw_str.replace(": ", ":")
    raw_str = raw_str.replace(",", ", ")
    return raw_str


def get_yaml_tool():
    from ruamel.yaml import YAML
    yaml = YAML()
    yaml.width = 4096
    yaml.preserve_quotes = True
    return yaml


def run_passthrough(cmd, cwd=None):
    """
    Run an external command whose arguments are passed through from the CLI.

    The command is given as a list so that the arguments are not pasted into a
    shell command line unquoted. A failure of the child process is reported as a
    message instead of a traceback, and its exit code is passed through as our
    own. Note that this function does not return in that case.

    :param cmd: Command to be run, given as a list of arguments.
    :param cwd: Directory to run the command in, None to use the current one.
    :return: CompletedProcess instance of the finished command.
    """
    try:
        return subprocess.run(cmd, cwd=cwd, check=True)
    except subprocess.CalledProcessError as e:
        return_code = e.returncode
        if return_code < 0:
            # the child was killed by a signal, report it the way a shell does.
            return_code = 128 - return_code
        print(f'Failed. Command "{cmd[0]}" exited with code "{return_code}".')
        sys.exit(return_code)
    except FileNotFoundError as e:
        # the missing path is the command itself, or the working directory. this
        # clause has to stay in front of the one below, as it catches a subclass.
        print(f'Failed. Could not run command "{cmd[0]}", {e}.')
        sys.exit(127)
    except OSError as e:
        # the command was found but could not be run, for example a file without
        # the executable bit (EACCES), a working directory that is not a
        # directory (ENOTDIR), or a file that is no valid executable (ENOEXEC).
        print(f'Failed. Could not run command "{cmd[0]}", {e}.')
        sys.exit(126)
    except KeyboardInterrupt:
        print("KeyboardInterrupt.")
        sys.exit(130)


#########################################################
def operation_log():
    # 生成日志内容
    log_time = datetime.datetime.now().strftime("%Y.%m.%d-%H:%M:%S")
    log_command = " ".join(sys.argv)
    log_user = os.getenv("SUDO_USER")
    if not log_user:
        log_user = os.getenv("USER")
    log_ssh = os.getenv("SSH_CONNECTION")
    log_str = (
        "  ".join(
            [log_time, f'ssh="{log_ssh}"', f'user="{log_user}"', f'cmd="{log_command}"']
        )
        + "\n"
    )

    # 获取日志文件路径
    file_path = OPERATION_LOG_FILE_PATH
    if not os.path.isfile(file_path):
        with open(file_path, "w"):
            pass

    # 配置日志记录器
    logger = logging.getLogger("operation_logger")

    # 防止重复添加handler
    if not logger.handlers:
        # 设置循环日志处理器
        handler = RotatingFileHandler(
            filename=file_path, maxBytes=1e6, backupCount=3, encoding="utf-8"
        )
        # handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    # 记录日志
    logger.info(log_str)


if __name__ == "__main__":
    file_copy(
        "/home/zhu/docker/IocDock/README.md", "/home/zhu/abc", mode="r", verbose=True
    )
