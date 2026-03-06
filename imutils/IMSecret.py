import os
import sys
import getpass
import tempfile
import atexit


def enter_password():
    password = getpass.getpass("Password: ")
    confirm_password = getpass.getpass("Confirm Password: ")
    if password != confirm_password:
        print("Passwords do not match!")
        return None
    return password


class PasswordFileManager:
    def __init__(
        self,
        password=None,
        prompt="请输入密码：",
        confirm=False,
        confirm_prompt="请确认密码：",
        prefix="IocDockPasswd_",
        suffix=".txt",
        dir=None,
        verbose=False,
    ):
        """
        初始化密码文件管理器实例

        Args:
            password: 如果提供则直接使用，否则从用户输入获取
            prompt: 密码输入提示
            confirm: 是否需要确认密码
            confirm_prompt: 确认密码提示
            prefix: 临时文件名前缀
            suffix: 临时文件名后缀
            dir: 临时文件目录
            verbose: 是否输出详细信息
        """
        self.password_file = None
        self.verbose = verbose

        # 获取密码
        if password is None:
            password = getpass.getpass(prompt)

            if confirm:
                confirm_password = getpass.getpass(confirm_prompt)
                if password != confirm_password:
                    raise ValueError("两次输入的密码不匹配！")

        # 创建临时文件
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=dir)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(password)
            if os.name != "nt":
                os.chmod(path, 0o600)
            self.password_file = path
            if verbose:
                print(f"✓ 密码文件已创建：{path}")
        except Exception:
            try:
                os.close(fd)
            except Exception:
                pass
            try:
                os.unlink(path)
            except Exception:
                pass
            raise

        # 注册程序退出自动清理
        atexit.register(self.cleanup)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        退出运行时上下文，清理临时文件

        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪对象
        """
        self.cleanup()
        # 返回 False 表示不抑制异常
        return False

    def cleanup(self):
        if self.password_file:
            try:
                os.unlink(self.password_file)
                if self.verbose:
                    print(f"✓ 已清理临时文件：{self.password_file}")
            except FileNotFoundError:
                pass
            except Exception as e:
                if self.verbose:
                    print(f"✗ 清理失败 {self.password_file}: {e}", file=sys.stderr)
            finally:
                self.password_file = None


if __name__ == "__main__":
    # 创建密码文件管理器实例
    with PasswordFileManager(
        verbose=True,
    ) as pfm:
        print(f"密码文件路径：{pfm.password_file}")
        # 在这里可以使用 pfm.password_file 进行相关操作
        input("按回车键退出并清理密码文件...")
