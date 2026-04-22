#### 构建基于 EPICS base 运行环境的容器镜像

docker build -t base:dev .
或
docker build -t base:beta .
docker build -t base:prod .

#### 准备

0. 准备EPICS base安装包(.tar.gz格式)
1. 设置Dockerfile中变量BASE, 使其对应EPICS base的安装包名称

#### 测试

1. 检查系统环境变量(EPICS_BASE, EPICS_HOST_ARCH, PATH)
2. 检查softIoc命令是否正常运行(iocsh中libreadline是否可用)
3. 检查makeBaseApp.pl等命令是否正常运行
4. 运行第三方包命令(ip addr, ping, ...)
5. 检查vi是否正常使用(方向键, 删除键等)

### 版本说明

#### base:1.0.0

以 EPICS-7.0.8.1 为基础的 base 容器镜像

#### base:1.0.1

修复 ~/.vimrc 文件换行字符不转义的问题
