# IocManager

IOC项目管理工具.

### 一般使用帮助

#### 更新IOC脚本工具

> 在需要进行版本更新时, 按如下操作即可.
>> - 执行```git pull origin master```拉取git仓库的项目最新代码
>> - 阅读根目录```auto-update.sh```中的说明文档(Instructions部分)
>> - 按说明文档, 执行```. auto-update.sh```命令完成脚本更新

### 工具使用帮助

#### 创建并设置IOC项目

通过命令行方式创建IOC项目, 添加设置或手动修改IOC项目的配置文件, 配置好IOC. 命令的详细使用方式见脚本命令行帮助.

- 创建IOC项目并进行简单配置   
  ```./IocManager.py create IOC [IOC2 IOC3 ...]``` 直接创建单个或多个IOC项目      
  ```./IocManager.py create IOC [IOC2 IOC3 ...] -s xxx -o xxx=xxx``` 创建时设置某些字段  
  ```./IocManager.py create IOC [IOC2 IOC3 ...] -f xxx``` 导入配置文件创建   
  ```./IocManager.py create IOC [IOC2 IOC3 ...] --caputlog/--status-ioc/--status-os/--autosave``` 指定使用的模块创建   
  ```./IocManager.py create IOC [IOC2 IOC3 ...] --add-asyn/--add-stream [--port-type "tcp/ip"/"serial"]```
  创建ASYN或STREAM模板并设置端口类型   
  ```./IocManager.py create IOC [IOC2 IOC3 ...] --add-raw``` 创建时设置添加原始命令模板


- 将IOC项目所需的源文件从指定目录添加至IOC项目的src/目录, 必要时可多次运行此命令.
  当前支持自动识别添加的文件名称后缀为 ```.db``` ```.proto``` ```.im``` .   
  ```./IocManager.py exec IOC [IOC2 IOC3 ...] -a --src-path xxx```
- 也可直接手动将所有文件复制至src/目录, 指定```-a```且不指定```--src-path```时, 脚本将自动识别添加src/目录内的源文件   
  ```./IocManager.py exec IOC [IOC2 IOC3 ...] -a```


- 进一步配置IOC项目, 如 .db文件的加载项及宏替换, 指定协议文件等等          
  ```./IocManager.py set IOC [IOC2 IOC3 ...] -s xxx -o xxx=xxx``` 单独设置某些字段  
  ```./IocManager.py set IOC [IOC2 IOC3 ...] -f xxx``` 导入配置文件覆盖设置    
  ```./IocManager.py set IOC [IOC2 IOC3 ...] --caputlog/--status-ioc/--status-os/--autosave``` 设置使用的模块   
  ```./IocManager.py set IOC [IOC2 IOC3 ...] --add-asyn/--add-stream [--port-type "tcp/ip"/"serial"]```
  设置ASYN或STREAM模板并设置端口类型   
  ```./IocManager.py set IOC [IOC2 IOC3 ...] --add-raw``` 设置添加原始命令模板


- 也可打开IOC项目的ioc.ini文件直接手动编辑配置文件

#### 生成IOC项目的运行文件

对已创建并配置完成的IOC项目, 需要生成IOC项目的运行文件及IOC启动文件. 执行如下步骤.

- 生成IOC项目的运行文件及启动文件   
  ```./IocManager.py exec IOC [IOC2 IOC3 ...] -s```

#### 导出IOC项目运行文件

对已生成运行文件的IOC项目, 需要将其导出至mount目录, 以便可以使用容器平台运行. 执行如下步骤.

- 导出IOC项目运行文件至mount目录. 默认不覆盖, 即, 当IOC项目已存在于monut目录时, 只更新部分运行文件(
  IOC运行的一些插件模块的配置文件将被保留). 也可以设置覆盖导入(指定 ```--force-overwrite```,
  此时插件模块的配置文件将被初始化).    
  ```./IocManager.py exec IOC [IOC2 IOC3 ...] -e [--mount-path xxx] [--force-overwrite]```

#### 为导出的IOC项目生成 docker compose 文件

- 为导出目录的所有主机文件夹生成docker compose文件. 需要指定iocLogserver所使用的base镜像.    
  ```./IocManager.py exec -c --mount-path xxx --base-image xxx```

#### 运行部署的IOC项目

略, 详见部署文档.

#### IOC项目文件的备份及恢复

创建生成的IOC项目存放于本地仓库目录ioc-repository/. 在生成IOC运行文件之后, IOC项目就已经具备了运行所需的全部文件,
但为了管理方便, 还需将其导出至统一的mount目录下运行, 导出操作仅是文件目录的复制操作. 此后可选择备份,
可以将当前本地仓库的所有IOC项目打包压缩为tgz文件. 备份时可选择两种模式, "src": 仅备份IOC项目源文件及配置文件; "all":
备份包括运行时插件模块产生的文件在内的所有IOC文件.

- 备份时将默认先进行IOC项目的运行检查, 确保IOC项目是最新的且是正常可运行的   
  ```./IocManager.py exec --run-check```


- 进行备份, 指定将备份文件存储在某个位置及备份模式, 这将自动在目标位置生成带有时间戳的备份文件   
  ```./IocManager.py exec -b --backup-path xxx [--backup-mode "src"/"all"]```


- 执行命令进行备份文件的恢复, 指定需要恢复的备份文件及恢复模式(是否覆盖写入),
  将使备份文件内的IOC项目文件恢复至本地仓库目录   
  ```./IocManager.py exec -r --backup-file xxx [--force-overwrite]```

#### 管理IOC项目

- 列出所有IOC项目, 若要列出时显示IOC项目的全部配置信息, 使用"-i"选项   
  ```./IocManager.py list [-i]```


- 列出所有IOC项目, 按行列出时显示IOC项目的必要配置信息, 使用"-r"选项   
  ```./IocManager.py list -r```


- 根据筛选条件, 列出所有符合条件的IOC项目名称, 可以指定多个与逻辑同时筛选条件    
  ```./IocManager.py list condition [condition2 condition3 ...] [-i] [-r]```


- 通过名称模糊匹配, 列出IOC项目, 如下将查找所有名称中包含"abc"的IOC项目   
  ```./IocManager.py list name=abc [-i] [-r]```


- 查找具有指定字段设置的IOC项目, 如下将查找所有具有 "GHI" section 且其中abc字段属性值为def的IOC项目   
  ```./IocManager.py list abc=def -s ghi```


- 从给定的IOC列表中查找IOC项目, 如下将查找x1, x2, x3三个IOC项目中具有 "GHI" section 且其中abc字段属性值为def的IOC项目   
  ```./IocManager.py list abc=def -s ghi -l x1 x2 x3```


- 嵌套查找, 如下将从所有具有 "GHI" section 且其中abc字段的属性值为def的IOC项目中, 查找名称中包含xyz的IOC项目   
  ```./IocManager.py list abc=def -s ghi | xargs ./IocManager.py list name=xyz -l```


- 删除IOC项目   
  ```./IocManager.py remove IOC [IOC2 IOC3 ...] [-r] [-f] ```

### IOC配置文件说明

#### 通用配置设置

<pre>
[IOC]       ---------------------------- 默认section, 用以存储IOC的通用配置信息
name:       ---------------------------- IOC项目名称
host:       ---------------------------- IOC项目将在哪个主机中运行
image:       --------------------------- IOC项目将使用哪个镜像运行
bin:       ----------------------------- IOC将使用镜像中的哪个可执行IOC运行
module:       -------------------------- IOC将安装的模块. 目前支持四个自动安装模块: autosave, caputlog, status-ioc, status-os
description:       --------------------- IOC的描述信息
status:       -------------------------- IOC项目的配置状态. "created"(IOC项目未生成运行文件) 或 "generated"(IOC项目已生成运行文件) 或 "exported"(IOC项目已导出)
snapshot:       ------------------------ IOC配置文件的备份状态. ""(配置文件未备份) 或 "logged"(配置文件已备份且与备份文件一致) 或 "changed"(配置文件与备份文件不一致)

[DB]       ----------------------------- 默认section, 用以存储IOC加载db文件的配置信息
file:       ---------------------------- db文件列表
load_a:       -------------------------- 设置带宏替换加载项. 格式: *.db, A=abc, B=def. 注意带 "_(x)" 后缀的选项意为支持同时设置多个此类变量, 使用时需依序更改后缀字母, 下同.
load_b:       -------------------------- 设置不使用宏替换加载项. 格式: *.db

[SETTING]       ------------------------ 默认section, 用以存储IOC的附加配置信息
report_info:       --------------------- 设置IOC启动时报告当前IOC的PV信息. "true" 或 "false"
caputlog_json:       ------------------- 设置caPutLog模块使用JSON格式. "true"(使用json格式) 或 "false"(使用文本格式)
epics_env_a:       --------------------- 设置EPICS环境变量. 格式: "xxx"="xxx"
epics_env_b:       --------------------- 设置多个EPICS环境变量.
</pre>

#### 特殊配置设置

以下配置均为模板, 实际使用中根据需求调整设置. 对部分可以有重复项的设置(如 load_ , cmd_ , file_copy_ , port_config_ 等)
的后缀应使用英文字母进行排序区分.

- 基于网络的ASYN配置, 设置项将直接添加至IOC启动脚本文件中

<pre>
[ASYN]
port_type: tcp/ip
port_config_a: drvAsynIPPortConfigure("L0","192.168.0.23:4001",0,0,0)
load_a: dbLoadRecords("db/asynRecord.db","P=xxx,R=:asyn,PORT=xxx,ADDR=xxx,IMAX=xxx,OMAX=xxx")
</pre>

- 基于串口的ASYN配置, 设置项将直接添加至IOC启动脚本文件中

<pre>
[ASYN]
port_type: serial
port_config_a: drvAsynSerialPortConfigure("L0","/dev/tty.PL2303-000013FA",0,0,0)
asyn_option_a: asynSetOption("L0", -1, "baud", "9600")
asyn_option_b: asynSetOption("L0", -1, "bits", "8")
asyn_option_c: asynSetOption("L0", -1, "parity", "none")
asyn_option_d: asynSetOption("L0", -1, "stop", "1")
asyn_option_e: asynSetOption("L0", -1, "clocal", "Y")
asyn_option_f: asynSetOption("L0", -1, "crtscts", "Y")
load_a: dbLoadRecords("db/asynRecord.db","P=xxx,R=:asyn,PORT=xxx,ADDR=xxx,IMAX=xxx,OMAX=xxx")
</pre>

- 基于网络的StreamDevice配置, 设置项将直接添加至IOC启动脚本文件中. 多个协议文件以逗号分隔.

<pre>
[STREAM]
port_type: tcp/ip
port_config_a: drvAsynIPPortConfigure("L0","192.168.0.23:4001",0,0,0)
protocol_file: x.proto, xx.proto
</pre>

- 基于串口的StreamDevice配置, 设置项将直接添加至IOC启动脚本文件中

<pre>
[STREAM]
port_type: serial
port_config_a: drvAsynSerialPortConfigure("L0","/dev/tty.PL2303-000013FA",0,0,0)
asyn_option_a: asynSetOption("L0", -1, "baud", "9600")
asyn_option_b: asynSetOption("L0", -1, "bits", "8")
asyn_option_c: asynSetOption("L0", -1, "parity", "none")
asyn_option_d: asynSetOption("L0", -1, "stop", "1")
asyn_option_e: asynSetOption("L0", -1, "clocal", "Y")
asyn_option_f: asynSetOption("L0", -1, "crtscts", "Y")
protocol_file: xxx.proto
</pre>

- 开放的IOC启动文件原始命令设置接口. 支持st.cmd文件命令的自定义设置以及文件的复制操作, 在执行IOC项目运行文件的生成时,
  会将命令直接添加至st.cmd脚本, 会将文件从本地计算机的某位置复制到IOC项目的运行文件夹中. 之后再执行脚本的导出命令将IOC导出即可.

> 注: 使用file_copy_字段的格式: "path to src file" : "path to dest file" [: "mode"].   
> "mode"不设置时默认为"r", 表示只读复制. 可设置目的文件的权限为"rwx"的任意组合, 同Linux操作系统.

<pre>
[RAW]
cmd_before_dbload_a: 
cmd_at_dbload_a: 
cmd_after_iocinit_a: 
file_copy_a: 
</pre>

### 项目目录结构

<pre>
├── auto-test-for-IocManager.sh*       ----------------------- IOC管理工具脚本的测试脚本
├── auto-update.sh*       ------------------------------------ IOC管理工具脚本的升级脚本
├── imtools/       ------------------------------------------- 存放其他工具脚本及程序文件的目录
│   ├── command-completion.sh       -------------------------- 命令补全脚本
│   ├── docker-manager/       -------------------------------- 操作系统的docker环境配置工具目录
│   │   ├── certs/       ------------------------------------- 存放证书生成脚本及TLS证书
│   │   ├── compose-agent.yaml       ------------------------- portainer agent的docker compose文件
│   │   ├── compose.yaml       ------------------------------- docker manager的docker compose文件
│   │   ├── README.md       ---------------------------------- 当前工具的使用说明
│   │   ├── set-docker-environment.sh*       ----------------- 设置docker运行所需环境的脚本
│   │   ├── start-compose-agent.sh*       -------------------- 启动portainer agent的脚本
│   │   └── start-docker-manager.sh*       ------------------- 启动docker manager的脚本
│   ├── IMFuncsAndConst.py       ----------------------------- 管理工具的公共调用函数及公共变量
│   ├── install-command-completion.sh*       ----------------- 安装管理工具shell命令补全的脚本
│   ├── IocClass.py       ------------------------------------ 管理工具的IOC类定义
│   ├── ioc-snapshot/       ---------------------------------- 存放IOC项目配置文件快照的目录
│   └── template/       -------------------------------------- 存放模板文件的目录
│       ├── db/
│       ├── template.acf
│       └── test/
├── IocManager.py*       ------------------------------------- 管理工具的启动脚本
├── make-test-project.sh*       ------------------------------ 自动生成IOC项目测试用例的脚本
├── README.md       ------------------------------------------ 此文档
└── ToDoAndDone.md       ------------------------------------- 记录待开发或已开发功能的文档
</pre>




更新日志及功能说明
------------------------------------------------------------------------

beta v0.3.3   
======= 2024/05/24 =======

1. IOC项目导出优化
2. shell命令补全bug处理及使用逻辑优化, 另外也支持缩写命令的补全识别
3. 添加项目升级脚本












