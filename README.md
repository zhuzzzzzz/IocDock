# IocManager

IOC项目管理工具, 用于生成并管理所有基于容器框架运行的IOC项目.

### 一般使用帮助

#### 更新IOC项目管理工具

在需要进行版本更新时, 按如下操作.
> 1. 执行 ```git remote update```, ```git pull origin master``` 更新并拉取git项目的最新代码.
> 2. 阅读根目录 ```auto-update.sh``` 中说明文档部分( Instructions部分).
> 3. 按说明文档, 执行 ```. auto-update.sh``` 命令完成脚本更新.

#### 一般工作流程

当需要创建IOC项目并希望其正确运行在容器中时, 按如下操作:

> 1. 使用命令新建IOC项目, 并将IOC项目所需的所有源文件添加至新建项目的"src/"目录

> 2. 编辑IOC项目的配置文件, 确定IOC项目将运行在哪个主机, 将使用的镜像及镜像内的可执行IOC, 设置DB部分中的load字段,
     确定IOC项目的.db文件加载项, 确定IOC项目的其他配置

> 3. 如要使用ASYN, STREAM或其他EPICS通信插件时, 首先确保已选择镜像中的可执行IOC支持相关功能. 然后使用命令行工具添加相关插件的配置模板,
     之后再进行配置.   
     ( ASYN, STREAM可直接添加已有的ASYN, STREAM模板, 其他插件则需要添加并编辑 RAW 模板)

> 4. 配置完成IOC项目后, 执行管理工具的IOC项目启动文件生成命令, 生成IOC项目运行所需的启动文件

> 5. 生成项目启动文件后, IOC项目需要执行导出命令, 将IOC项目的启动文件导出至mount目录

> 6. 运行前执行一遍运行检查命令, 以确保IOC项目得到正确配置. 妥当后, 前往容器工作的虚拟机指定目录, 启动 docker compose 项目

#### 项目生命周期管理

> IOC项目在执行创建、生成、导出操作后, 管理工具都会在"status[IOC]"字段更新当前状态.
> 此外, 在执行生成、导出操作后管理工具自动备份当前IOC项目的配置文件, 并更新"snapshot[IOC]"字段.
> 当管理工具检测到配置文件被修改, 导致与备份的配置文件不一致时, 将会给出相应提示.
>
> 项目周期管理的目标是使所有IOC项目处于 "exported" 和 "logged" 状态.

### 工具使用帮助

#### 创建并设置IOC项目的配置文件

通过命令行方式创建IOC项目, 添加设置或手动修改IOC项目的配置文件, 配置好IOC.    
如下列出管理工具命令的大致使用方式, 详细使用方式见管理工具的命令行帮助.

> - 使用```create```命令, 创建IOC项目并进行简单配置. 如下为可执行的创建命令, 选项可叠加设置:     
    ```./IocManager.py create IOC [IOC2 IOC3 ...]``` 直接创建单个或多个IOC项目      
    ```./IocManager.py create IOC [IOC2 IOC3 ...] -s xxx -o xxx=xxx``` 创建时设置某些字段  
    ```./IocManager.py create IOC [IOC2 IOC3 ...] -f xxx``` 导入已有配置文件创建   
    ```./IocManager.py create IOC [IOC2 IOC3 ...] --caputlog/--status-ioc/--status-os/--autosave```
    指定使用的模块创建   
    ```./IocManager.py create IOC [IOC2 IOC3 ...] --add-asyn/--add-stream [--port-type "tcp/ip"/"serial"]```
    创建ASYN或STREAM模板并设置端口类型   
    ```./IocManager.py create IOC [IOC2 IOC3 ...] --add-raw``` 创建时设置添加原始命令模板

>
> - 将IOC项目所需的源文件从指定目录添加至IOC项目的"src/"目录. 必要时可多次运行此命令.
    当前支持自动识别添加的文件名称后缀为 ```.db``` ```.proto``` ```.im```.    
    ```./IocManager.py exec IOC [IOC2 IOC3 ...] -a --src-path xxx```
> - 也可直接手动将所有文件复制至"src/"目录. 指定```-a```且不指定```--src-path```,
    脚本默认将自动识别添加项目自身"src/"目录内的源文件   
    ```./IocManager.py exec IOC [IOC2 IOC3 ...] -a```


> - 创建IOC项目后如需要进一步配置IOC项目, 使用```set```命令. 如设置.db文件的加载项及宏替换, 指定协议文件,
    其他需要额外指定的启动命令, 等等. 如下选项可叠加设置:          
    ```./IocManager.py set IOC [IOC2 IOC3 ...] -s xxx -o xxx=xxx``` 单独设置某些字段  
    ```./IocManager.py set IOC [IOC2 IOC3 ...] -f xxx``` 导入配置文件覆盖设置    
    ```./IocManager.py set IOC [IOC2 IOC3 ...] --caputlog/--status-ioc/--status-os/--autosave``` 设置使用的模块   
    ```./IocManager.py set IOC [IOC2 IOC3 ...] --add-asyn/--add-stream [--port-type "tcp/ip"/"serial"]```
    设置ASYN或STREAM模板并设置端口类型   
    ```./IocManager.py set IOC [IOC2 IOC3 ...] --add-raw``` 设置添加原始命令模板

> - 也可打开IOC项目的ioc.ini文件直接手动编辑配置文件, 编辑时注意文件格式.

#### 生成IOC项目的运行文件

对已创建并配置完成的IOC项目, 需要生成IOC项目的运行文件及IOC启动文件, 执行如下步骤.
执行此操作后, 工具将自动备份当前IOC项目的配置文件并更新IOC的项目状态属性用以进行项目周期管理.

- 对指定的IOC项目生成运行文件及启动文件   
  ```./IocManager.py exec IOC [IOC2 IOC3 ...] -s```

#### 导出IOC项目的运行文件

对已生成运行文件的IOC项目, 需要将其导出至mount目录, 以便可以使用容器平台运行, 执行如下步骤.
执行此操作后, 工具将自动备份当前IOC项目的配置文件并更新IOC的项目状态属性.

- 导出IOC项目运行文件至mount目录.    
  默认不覆盖, 即, 当IOC项目已存在于monut目录时, 只更新部分运行文件(
  IOC运行中一些插件模块记录产生的日志文件或配置文件将被保留). 也可以设置覆盖导入( 指定```--force-overwrite```,
  此时导出目录中的插件模块配置文件等将被初始化至项目刚生成运行文件时的状态).    
  ```./IocManager.py exec IOC [IOC2 IOC3 ...] -e [--mount-path xxx] [--force-overwrite]```

#### 为导出的IOC项目生成 docker compose 文件

- 为导出目录中存在的虚拟机文件夹生成docker compose文件. 需要指定iocLogserver所使用的base镜像. 指定```--hosts```
  来指定主机名称, 当需要为所有主机都执行生成操作时, 可将参数设置为```"allprojects"```.   
  ```./IocManager.py exec -c --hosts allprojects [--mount-path xxx] --base-image xxx```

#### 运行部署的IOC项目

略, 详见部署文档.

#### IOC项目文件的备份及恢复

默认情况下, 创建生成的IOC项目存放于本地仓库目录"ioc-repository/". 在生成IOC运行文件之后, IOC项目就已经具备了运行所需的全部文件,
但为了管理方便, 还需将其导出至统一的mount目录下运行, 导出操作仅是文件目录的复制操作.

导出后可选择进行备份操作, 将当前本地仓库的所有IOC项目打包压缩为tgz文件. 备份时可选择两种模式, ```"src"```:
仅备份IOC项目源文件及配置文件; ```"all"```: 备份包括运行时插件模块产生的文件在内的所有IOC文件.

- 备份时默认将先进行IOC项目的运行检查, 确保IOC项目是最新的且是正常可运行的, 通过后方能继续备份.
  也可手动执行命令先进行运行检查   
  ```./IocManager.py exec --run-check```


- 执行备份操作, 指定将备份文件存储位置及备份模式, 工具将自动在目标位置生成带有时间戳的备份文件   
  ```./IocManager.py exec -b --backup-path xxx [--backup-mode "src"/"all"]```


- 执行命令进行备份文件的恢复, 指定需要恢复的备份文件及恢复模式( 是否覆盖写入),
  将使备份文件内的IOC项目文件恢复至本地仓库目录   
  ```./IocManager.py exec -r --backup-file xxx [--force-overwrite]```

#### 管理IOC项目

- 列出所有IOC项目. 若要列出时显示IOC项目的全部配置信息, 使用```-i```选项.   
  ```./IocManager.py list [-i]```


- 按行列出IOC项目并显示状态信息, 使用```-r```选项.   
  ```./IocManager.py list -r```


- 根据条件筛选, 列出所有符合条件的IOC项目. 可以同时指定多个条件, 进行与逻辑筛选.     
  ```./IocManager.py list condition [condition2 condition3 ...] [-i] [-r]```


- 通过项目名称进行模糊匹配, 列出IOC项目. 如下将筛选列出所有名称中包含"abc"的IOC项目.    
  ```./IocManager.py list name=abc [-i] [-r]```


- 筛选所有具有指定字段设置的IOC项目. 如下将筛选并列出所有具有 "GHI" section 且其中"abc"字段属性值为"def"的IOC项目.   
  ```./IocManager.py list abc=def -s ghi```


- 从给定的IOC列表中筛选IOC项目. 如下将筛选并列出x1, x2, x3三个IOC项目中具有 "GHI" section 且其中"abc"字段属性值为"def"
  的IOC项目.   
  ```./IocManager.py list abc=def -s ghi -l x1 x2 x3```


- 嵌套筛选查找. 如下将从所有具有 "GHI" section 且其中"abc"字段的属性值为"def"的IOC项目中,
  筛选查找名称中包含"xyz"的IOC项目.   
  ```./IocManager.py list abc=def -s ghi | xargs ./IocManager.py list name=xyz -l```


- 删除IOC项目. 注意删除时可指定的选项.   
  ```./IocManager.py remove IOC [IOC2 IOC3 ...] [-r] [-f] ```


- 重命名IOC项目.   
  ```./IocManager.py rename old-name new-name [-v] ```

### IOC配置文件说明

> 可选的配置已在下方用```*```号标注, 未标注则均为必须设置项, 需要进行配置才能使IOC项目正常运行.
> 部分必须设置项会由脚本自动生成而无须手动设置.

> 部分配置项( ```load[DB]``` ```port_config[ASYN/STREAM]``` ```asyn_option[ASYN/STREAM]``` ```load[ASYN]```
> ```epics_env[SETTING]``` ```cmd_*[RAW]``` ```file_copy[RAW]```)支持多行设置, 即每行可看作一个单独的设置项.    
> 可在使用```./IocManager create```
> 或```./IocManager set``` 命令指定属性时使用分号```;```间隔来代表多行设置. 也可在直接编辑配置文件时通过换行及缩进来进行多行配置.

#### 通用配置设置

<pre>
[IOC]       ---------------------------- 用以存储IOC的通用配置信息
name:       ---------------------------- IOC项目名称
host:       ---------------------------- IOC项目将在哪个主机中运行
image:       --------------------------- IOC项目将使用哪个镜像运行
bin:       ----------------------------- IOC将使用镜像中的哪个可执行IOC运行
*module:       ------------------------- IOC将安装的模块. 目前支持四个自动安装模块: autosave, caputlog, status-ioc, status-os
*description:       -------------------- IOC的描述信息
*status:       ------------------------- IOC项目的配置状态. "created"(IOC项目未生成运行文件) 或 "generated"(IOC项目已生成运行文件) 或 "exported"(IOC项目已导出)
*snapshot:       ----------------------- IOC配置文件的备份状态. ""(配置文件未备份) 或 "logged"(配置文件已备份且与备份文件一致) 或 "changed"(配置文件与备份文件不一致)

[DB]       ----------------------------- 用以存储IOC加载db文件的配置信息
file:       ---------------------------- db文件列表
load:       ---------------------------- 设置带宏替换的db文件加载项. 格式: *.db, A=abc, B=def    
            ---------------------------- 设置不使用宏替换的db文件加载项. 格式: *.db

[SETTING]       ------------------------ 用以存储IOC的附加配置信息
report_info:       --------------------- 设置IOC启动时是否报告当前IOC的PV信息等. "true" 或 "false"
caputlog_json:       ------------------- 设置caPutLog是否使用JSON格式. "true"(使用json格式) 或 "false"(使用文本格式)
*epics_env:       ---------------------- 设置EPICS环境变量. 格式: "xxx"="xxx"
                  ---------------------- 分行设置多个EPICS环境变量.
</pre>

#### 配置规范和命名规范

```name[IOC]```: IOC名称, 决定IOC被分配的运行容器名称, 要符合容器的命名规范, 可以使用小写或下划线、数字(
参考下方host字段). 应尽量避免与host字段相同.

```host[IOC]```: 主机名称, 指IOC将被分配至哪个主机中运行, 应与被分配主机的操作系统主机名称一致.
其中主机名称的命名方式必须符合正则表达式```"^[a-z0-9][a-z0-9_-]*$"```.

```image[IOC]```: 镜像名称, 指当前将使用的镜像, 需要从镜像仓库中选择一个适合的镜像版本.

```bin[IOC]```: 镜像中可执行的IOC名称, 镜像中可能安装有不同IOC, 不同的IOC可能安装有不同的插件, 因此需要从镜像中正确选择一个可执行IOC.

```epics_env[SETTING]```: IOC shell使用的环境变量, 可以根据官方文档按需进行设置.

#### 特殊配置设置

以下配置均为模板, 实际使用中根据需求调整设置. 对部分可以有重复项的设置( 如load, cmd, file_copy, port_config等)
可以按前述, 用分号或换行缩进的方式进行设置.

- 基于网络的ASYN配置模板, 设置项将直接添加至IOC启动脚本文件中

<pre>
[ASYN]
port_type: tcp/ip
port_config: drvAsynIPPortConfigure("L0","192.168.0.23:4001",0,0,0)
load: dbLoadRecords("db/asynRecord.db","P=xxx,R=:asyn,PORT=xxx,ADDR=xxx,IMAX=xxx,OMAX=xxx")
</pre>

- 基于串口的ASYN配置模板, 设置项将直接添加至IOC启动脚本文件中

<pre>
[ASYN]
port_type: serial
port_config: drvAsynSerialPortConfigure("L0","/dev/tty.PL2303-000013FA",0,0,0)
asyn_option: asynSetOption("L0", -1, "baud", "9600")
  asynSetOption("L0", -1, "bits", "8")
  asynSetOption("L0", -1, "parity", "none")
  asynSetOption("L0", -1, "stop", "1")
  asynSetOption("L0", -1, "clocal", "Y")
  asynSetOption("L0", -1, "crtscts", "Y")
load: dbLoadRecords("db/asynRecord.db","P=xxx,R=:asyn,PORT=xxx,ADDR=xxx,IMAX=xxx,OMAX=xxx")
</pre>

- 基于网络的StreamDevice配置模板, 设置项将直接添加至IOC启动脚本文件中. 多个协议文件以逗号分隔.

<pre>
[STREAM]
port_type: tcp/ip
port_config: drvAsynIPPortConfigure("L0","192.168.0.23:4001",0,0,0)
protocol_file: x.proto, xx.proto
</pre>

- 基于串口的StreamDevice配置模板, 设置项将直接添加至IOC启动脚本文件中

<pre>
[STREAM]
port_type: serial
port_config: drvAsynSerialPortConfigure("L0","/dev/tty.PL2303-000013FA",0,0,0)
asyn_option: asynSetOption("L0", -1, "baud", "9600")
  asynSetOption("L0", -1, "bits", "8")
  asynSetOption("L0", -1, "parity", "none")
  asynSetOption("L0", -1, "stop", "1")
  asynSetOption("L0", -1, "clocal", "Y")
  asynSetOption("L0", -1, "crtscts", "Y")
protocol_file: xxx.proto
</pre>

- 开放的IOC启动文件原始命令设置接口. 支持st.cmd文件命令的自定义设置以及文件的复制操作, 在执行IOC项目运行文件的生成时,
  会将命令直接添加至st.cmd脚本, 会将文件从本地计算机的某位置复制到IOC项目的运行文件夹中. 之后再执行脚本的导出命令将IOC导出即可.

> 注: 使用file_copy_字段的格式: "path to src file" : "path to dest file" [: "mode"].   
> "mode"不设置时默认为"r", 表示只读复制. 可设置目的文件的权限为"rwx"的任意组合, 同Linux操作系统.

<pre>
[RAW]
*cmd_before_dbload: 
*cmd_at_dbload: 
*cmd_after_iocinit: 
*file_copy: 
</pre>

### 项目目录结构

<pre>
├── auto-test-for-IocManager.sh*       ----------------------- IOC管理工具脚本的测试脚本
├── auto-update.sh*       ------------------------------------ IOC管理工具脚本的升级脚本
├── imtools/       ------------------------------------------- 存放其他工具脚本及其他程序文件的目录
│   ├── command-completion.sh       -------------------------- 命令补全脚本
│   ├── docker-manager/       -------------------------------- 操作系统的docker环境配置工具目录
│   │   ├── certs/       ------------------------------------- 存放证书生成脚本及TLS证书
│   │   ├── compose-agent.yaml       ------------------------- portainer agent的docker compose文件
│   │   ├── compose.yaml       ------------------------------- docker manager的docker compose文件
│   │   ├── README.md        
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
├── README.md        
└── ToDoAndDone.md        
</pre>




更新日志及功能说明
------------------------------------------------------------------------

beta v0.4.0   
======= 2024/05/29 =======

1. config文件option支持同属性的多行配置
2. IOC项目支持重命名命令












