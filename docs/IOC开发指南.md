# IocDock

## IOC 项目的开发与部署

### 详细工作流程参考

当需要创建 IOC 项目并希望其正确运行在容器中时, 按如下顺序进行操作:

1. 新建 IOC 项目, 将所需的所有源文件添加至新建项目的 "src/" 目录.
2. 编辑 IOC 项目的配置文件设置参数. 如确定 IOC 项目将运行在哪个主机, 将使用的镜像及镜像内的可执行 IOC; 设置 DB 部分 load
   字段,
   确定 IOC 项目的 db 文件加载项; 确定 IOC 项目的其他配置等等.
3. 如要使用 ASYN, STREAM 或其他 EPICS 硬件通信模块来开发 IOC 时, 首先确保已选择容器镜像中的可执行 IOC 支持相关模块,
   然后在配置文件中添加 "RAW" 部分进行相关模块的 st.cmd 启动加载项配置
   *(需要添加并编辑 "RAW" 模板. ASYN, STREAM可直接添加已有的基于 "ASYN" 或 "STREAM" 配置的 "RAW" 模板)*
4. 配置完成 IOC 项目后, 执行管理工具提供的命令生成 IOC 项目启动文件.
5. 生成项目启动文件后, 需要执行导出命令, 将 IOC 项目的启动文件导出至 mount 目录.
6. 导出后, 需在 mount 目录为其生成容器部署文件
7. 生成容器部署文件后, IOC 的状态将更新为 Available, 即表示其已经可由系统管理执行部署

### IOC配置文件说明

可选配置将在下方用```*```号标注, 未标注则均为必须设置项, 需要进行配置才能使IOC项目正常运行.

部分配置项支持多行设置, 即每行可看作一个单独的设置项设置多个同类项.
可在使用```IocManager create```或```IocManager set``` 命令指定属性时使用分号```;```间隔来代表多行设置,
也可在直接编辑配置文件时通过换行及缩进的方式来进行多行配置.

#### 通用配置

下方列出了每个IOC项目显示的属性项, 参考其中各项说明说明进行配置.

<pre>

-----------------------------------------------------------------------------------------------------------------------

# 此部分由单独文件存储, 独立于IOC配置文件, 无需配置, 由系统维护

[STATE]       -------------------------- 用以存储IOC的状态信息的部分
state: normal       -------------------- IOC项目状态
state_info:       ---------------------- IOC项目状态的详细信息
status: exported       ----------------- 仓库中IOC项目的阶段性状态
snapshot: tracked       ---------------- IOC项目的快照状态
is_exported: true       ---------------- IOC项目是否已导出至运行目录

-----------------------------------------------------------------------------------------------------------------------

# IOC配置文件内容, 部分项由系统维护, 按需配置

[IOC]       ---------------------------- IOC通用配置信息
name:       ---------------------------- IOC项目名称(无需配置, 请使用rename子命令进行IOC项目更名)
host:       ---------------------------- IOC项目的编排模式. 当前仅支持设置为swarm
image:       --------------------------- IOC项目将使用哪个镜像运行
bin:       ----------------------------- IOC将使用镜像中的哪个可执行IOC运行
module*:       ------------------------- IOC将自动安装的模块. 目前支持四个模块: autosave, caputlog, status-ioc, status-os
description*:       -------------------- IOC的描述信息

[SRC]       ---------------------------- IOC项目源文件信息(无需设置, 此部分所有属性由系统维护自动更新)
db_file:       ------------------------- 当前存在的db文件列表. 使用"--add-src-file"命令后将自动更新此列表
protocol_file:       ------------------- 当前存在的协议文件列表.  
others_file:       --------------------- 当前存在的其他以.im为后缀文件的列表.  

[DB]       ----------------------------- IOC加载项信息
load:       ---------------------------- 设置带宏替换的db文件加载项. 格式: "*.db, A=abc, B=def"
            ---------------------------- 设置不使用宏替换的db文件加载项. 格式: "*.db"
            ---------------------------- 分行设置多个db文件加载项.

[SETTING]       ------------------------ IOC附加配置信息
report_info:       --------------------- 设置IOC启动时是否报告当前IOC的PV信息等. "true" 或 "false"
caputlog_json:       ------------------- 设置caPutLog是否使用JSON格式. "true"(使用json格式) 或 "false"(使用文本格式)
epics_env*:       ---------------------- 设置EPICS环境变量. 格式: "xxx"="xxx"
                  ---------------------- 分行设置多个EPICS环境变量.

[DEPLOY]       ------------------------- IOC容器部署配置信息
labels*:       ------------------------- 为IOC容器服务打上标签. 格式: "key=value"
               ------------------------- 分行设置多个标签
cpu-limit*:       ---------------------- 设置IOC的CPU占用上限. 示例: 0.8(代表0.8个CPU核心)
memory-limit*:       ------------------- 设置IOC的内存占用上限. 示例: 1G
cpu-reserve*:       -------------------- 设置IOC的CPU占用下限
memory-reserve*:       ----------------- 设置IOC的内存占用下限
constraints*:       -------------------- 设置IOC的部署约束条件. 尚未开发.

-----------------------------------------------------------------------------------------------------------------------

</pre>

```name[IOC]```: IOC名称, 决定IOC被分配的运行容器名称.
可以使用小写或下划线、数字(参考下方host字段). 应尽量避免与host字段相同. *要符合docker命名规范.*

```image[IOC]```: 镜像名称, 指当前将使用的镜像, 不同的镜像版本可能支持不同的EPICS插件, 需要从镜像仓库中选择一个适合的镜像版本.

```bin[IOC]```: 镜像中可执行的IOC名称, 镜像中可能安装有不同IOC, 不同的IOC可能安装有不同的插件, 因此需要从镜像中正确选择一个可执行IOC.

#### RAW模板配置

以下配置均为模板, 实际使用中根据需求调整设置. 对部分可以有重复多项的设置可以按前述, 用分号或换行缩进的方式进行设置.

##### 开放的 RAW 配置模板, 主要执行两点操作

1. IOC启动文件原始命令设置接口, 支持st.cmd文件命令的自定义设置
2. 系统文件的复制操作接口, 用于执行生成启动文件时的复制操作

*在执行IOC项目运行文件的生成时, 会将此处设置的原始命令直接添加至st.cmd脚本, 将文件从本地计算机的某位置复制到IOC项目的运行文件夹中.
例如在使用ASYN时会将"asynRecord.db"从工具的模板仓库复制至IOC项目目录; 使用STREAM时会将协议文件复制至IOC项目目录等.
使用其他未提供配置模板的EPICS插件时, 若需要添加相关IOC启动命令或进行文件复制处理时, 设置此字段.*

<pre>
[RAW]
cmd_before_dbload:       # 在加载db文件前的操作
cmd_at_dbload:       # 在加载db文件时的操作
cmd_after_iocinit:       # 在ioc初始化之后的操作
file_copy:       # 文件复制操作, 将某个文件复制到某个目录. 格式: "src_dir/file:dest_dir/file[:rwx]".
                 # 仅支持从仓库templates/或项目src/目录复制到项目project/目录下的文件复制操作.
</pre>

##### 基于 ASYN 的 RAW 配置模板, 设置项将作为文本直接添加至IOC启动脚本文件中

<pre>
[RAW]
cmd_before_dbload:
        drvAsynIPPortConfigure("L0", "192.168.0.23:4001", 0, 0, 0)
        drvAsynSerialPortConfigure("L0", "/dev/tty.PL2303-000013FA", 0, 0, 0)
        asynSetOption("L0", -1, "baud", "9600")
        asynSetOption("L0", -1, "bits", "8")
        asynSetOption("L0", -1, "parity", "none")
        asynSetOption("L0", -1, "stop", "1")
        asynSetOption("L0", -1, "clocal", "Y")
        asynSetOption("L0", -1, "crtscts", "Y")
cmd_at_dbload: dbLoadRecords("db/asynRecord.db", "P=xxx, R=:asyn, PORT=xxx, ADDR=xxx, IMAX=xxx, OMAX=xxx")
cmd_after_iocinit:
file_copy: templates/db/asynRecord.db:src/asynRecord.db:wr
</pre>

##### 基于 StreamDevice 的 RAW 配置模板, 设置项将作为文本直接添加至IOC启动脚本文件中. 多个协议文件以逗号分隔

<pre>
[RAW]
cmd_before_dbload:
        epicsEnvSet("STREAM_PROTOCOL_PATH", /opt/EPICS/RUN/b/startup)
        drvAsynIPPortConfigure("L0", "192.168.0.23:4001", 0, 0, 0)
        drvAsynSerialPortConfigure("L0", "/dev/tty.PL2303-000013FA", 0, 0, 0)
        asynSetOption("L0", -1, "baud", "9600")
        asynSetOption("L0", -1, "bits", "8")
        asynSetOption("L0", -1, "parity", "none")
        asynSetOption("L0", -1, "stop", "1")
        asynSetOption("L0", -1, "clocal", "Y")
        asynSetOption("L0", -1, "crtscts", "Y")
cmd_at_dbload:
cmd_after_iocinit:
file_copy: src/protocol_file.proto:startup/protocol_file.proto:r
</pre>
