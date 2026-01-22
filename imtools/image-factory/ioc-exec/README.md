### 构建IOC运行环境的容器镜像:

docker build -t ioc-exec:dev .   
或   
docker build -t ioc-exec:beta .   
docker build -t ioc-exec:prod .   


### 准备

0. 准备EPICS base镜像, 设置Dockerfile中RELEASE_VERSION变量, 确定镜像版本号

1. 安装EPICS supports

	0) 此阶段所有工作在"SUPPORT"目录内完成, 请预先将所有需要安装模块的项目文件解压至"SUPPORT"目录
	1) 检查并配置各模块项目内的"/configure/RELEASE"文件, 注释掉不需要的路径变量或模块依赖关系
	2) 为确保编译成功, 部分模块需要单独修改文件配置(例如asyn模块需在CONFIG_SITE中设置TIRPC=YES)
	3) 运行脚本"automake.sh pack"讲所有模块的项目文件打包
	4) 编辑脚本"automake.sh", 设置变量"modules_to_install", 按顺序设置需要安装哪些模块
	5) 编辑脚本"checkDependency.sh", 设置变量"module_dict"确定需要安装的模块的依赖关系; 设置变量"path_name"确定依赖模块的路径名称及其在Makefile中的包名称
	6) 运行脚本"automake.sh"安装目录内模块(通过Dockerfile构建镜像时自动完成)

2. 编译IOC可执行文件

	0) 所有工作在"IOC"目录内完成
	1) 编辑脚本"ioc-generator.py", 设置IOC的基本信息以及需要为IOC安装的模块(若设置了sequencer, 则需要先将seq SNL文件拷贝至 IOC/src/seq 目录下)
	2) 运行脚本"ioc-generator.py", 完成IOC可执行文件的创建以及编译(Dockerfile内自动完成)


### 测试
============== ioc-exec ==============   

0. 安装编译环境

	apt update   
	apt install -y build-essential libreadline-dev python3 zip

1. 检查各个模块是否能够成功安装

	cd SUPPORT; ./test-for-automake.sh

2. 测试IOC是否能够正常创建编译

	cd IOC/ioc-tools; ./test-for-ioc-generator.sh

3. 测试IOC项目能否启动且功能正常(含有system命令, iocsh中libreadline是否可用)

	cd "IOC启动目录"; ./st.cmd
	

