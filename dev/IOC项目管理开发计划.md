# IOC 项目管理开发计划

代码在方案全部确定后一次性生成。本文档只记录已讨论确定的内容,随讨论逐步补充。

## 一、项目与范围

IocDock 把 EPICS IOC 项目作为服务部署到 Docker Swarm 集群。核心代码放在 `core/` 目录。

当前讨论的范围是 **IOC 项目管理**:一个 IOC 项目在仓库里如何存放、配置、生成启动文件、部署到挂载目录,并被查询和维护。集群、镜像、服务等其他模块在后续章节补充。

## 二、IOC 项目管理需要完成的事情

| 编号 | 功能 | 说明 | 状态 |
|---|---|---|---|
| 1 | 项目目录结构 | 定义一个 IOC 项目的目录与文件布局,见第三节 | 已确定 |
| 2 | 配置文件 | `ioc.yaml` 的格式、读取、写入、校验,见第四节 | 格式已确定 |
| 3 | 状态文件 | `.state.json` 的格式、读写、并发,见第五节 | 已确定 |
| 4 | 创建 | 创建项目目录并写入默认配置;可选添加 asyn、stream、空白 build 模板;创建前检查名称合法且不重复 | 待讨论 |
| 5 | 查询与筛选 | 列出全部项目;按名称、状态字段(state、status、snapshot、is_exported)、配置字段筛选;显示状态与问题日志 | 待讨论 |
| 6 | 修改配置 | 命令行修改配置项;用编辑器直接编辑 `ioc.yaml` | 待讨论 |
| 7 | 重命名与删除 | 重命名同时改目录名与配置里的 `basic.name`;删除可选同时清除挂载目录与快照;删除前确认 | 待讨论 |
| 8 | 源文件管理 | 扫描 `src/` 目录,按后缀分类,维护 `src` 与 `src_files`;发现丢失的源文件,见第四节 | 方案已确定 |
| 9 | 配置检查 | 生成前校验配置,见下文 | 待讨论 |
| 10 | 生成启动文件 | 生成 `<name>.substitutions` 与 `st.cmd`,复制模块配置与 `build.file_copy` 指定的文件 | 待讨论 |
| 11 | 导出与部署一致性 | 把项目文件导出到挂载目录;比对挂载目录与仓库是否一致 | 待讨论 |
| 12 | 快照 | 创建、删除、从快照恢复配置与源文件;比对快照与当前内容是否一致 | 待讨论 |
| 13 | 备份与恢复 | 整个仓库备份为带时间戳的压缩包(仅配置与源文件,或全部);从备份恢复 | 待讨论 |
| 14 | 批量升级 | 配置格式或默认值更新后,批量重建全部项目并保留原有配置 | 待讨论 |
| 15 | 生成 swarm 编排文件 | 由项目配置生成 swarm 服务定义(镜像、资源、标签、放置约束、环境变量) | 待讨论 |

### 配置检查规则(功能 9)

- `basic.bin` 不能为空。
- `build.modules` 中的每一项必须是支持的模块:autosave、caputlog、status-ioc、status-os。
- `build.epics_env` 中的变量名不能为空。
- `build.file_copy` 每项的 `src` 必须以 `src/` 或 `templates/` 开头。
- `build.db_load` 中的 `file` 必须存在于 `src/` 目录。
- `basic.name` 与目录名一致。

### 项目生命周期与状态

`status` 取值随操作变化:创建后为 created,生成启动文件后为 generated,导出后为 exported,从备份恢复后为 restored。导出操作要求 `state` 为 normal 且 `status` 为 generated 或 exported。

## 三、项目目录结构

```text
<ioc 名称>/
├── ioc.yaml            # 配置文件,用户编辑
├── .state.json         # 状态文件,程序读写
├── .state.json.lock    # 状态文件的进程锁
├── src/                # 用户提供的源文件(.db、.proto、.im 等)
└── project/
    ├── settings/
    ├── logs/
    └── startup/
        ├── db/
        └── iocBoot/
```

目录名即 IOC 名称。

## 四、配置文件 `ioc.yaml`

### 格式

```yaml
# ===== 基本信息 =====
basic:
  name: ioc-demo                # 必须要有值 与目录名一致,加载时比对
  host: swarm                   # 必须要有值
  image: registry.iasf/ioc:1.0  # 必须要有值
  bin: ST-IOC                   # 容器内可执行 IOC 必须要有值
  description: ""     # 必须要有这个字段 值可以为空

# ===== src/ 目录文件(由程序维护,请勿手改,编辑 build.db_load 时可参考)=====
src:
  db_files:
    - ramper.db
  protocol_files:
    - device.proto
  other_files: []

# ===== 启动文件构建 =====
build:
  modules:                      # 可选值:autosave、caputlog、status-ioc、status-os 值可以为空
    - autosave 
    - caputlog
  db_load: # 必须要有值
    - file: ramper.db           # 必须在 src/ 下
      macros:                   # 映射保持书写顺序
        P: "xxx:"
        R: ramp
  raw_cmd:
    cmd_before_dbload: | # 值可以为空
      drvAsynIPPortConfigure("L0","192.168.0.23:4001",0,0,0) 
    cmd_at_dbload: | # 值可以为空
      dbLoadRecords("db/asynRecord.db","P=xxx,R=:asyn")
    cmd_after_iocinit: "" # 值可以为空
  file_copy: # 值可以为空
    - src: templates/db/asynRecord.db   # 源必须以 src/ 或 templates/ 开头
      dest: src/asynRecord.db           # 相对 project/ 目录
      mode: wr                          # r/w/x 组合,缺省 r
  epics_env: # 值可以为空
    EPICS_CA_MAX_ARRAY_BYTES: "20000000"

# ===== IOC 运行设置 =====
settings: # 必须要有值
  report_info: true
  caputlog_json: false

# ===== 部署(结构参考 compose 的 deploy)=====
deploy: 
  labels: # 值可以为空
    owner: zhu
  resources: # 值可以为空
    limits:
      cpus: "1"
      memory: 1G
    reservations:               # 空字符串表示不预留
      cpus: ""
      memory: ""
  placement: # 值可以为空
    constraints:
      - node.role==worker
```

### 字段说明

| 字段 | 创建时写入的值 | 说明 |
|---|---|---|
| basic.name | 目录名 | IOC 名称,加载时与目录名比对 |
| basic.host | swarm | `swarm` 表示集群部署,否则为主机名;决定挂载目录 `MOUNT_PATH/<host>/<name>`;空值按 swarm 处理 |
| basic.image | 空 | 镜像名,swarm 部署时必须非空 |
| basic.bin | ST-IOC | 容器内可执行 IOC,必填 |
| basic.description | 空 | 描述 |
| src.db_files / src.protocol_files / src.other_files | 空 | `src/` 下 `.db`、`.proto`、`.im` 文件,由程序维护 |
| build.modules | autosave, caputlog | 要安装的模块列表 |
| build.db_load | 空 | 每项含 `file` 与 `macros`,用于生成 `<name>.substitutions`;为空时无法生成 |
| build.raw_cmd.cmd_before_dbload | 空 | 加载 db 之前的 IOC shell 命令 |
| build.raw_cmd.cmd_at_dbload | 空 | 加载 db 处的命令 |
| build.raw_cmd.cmd_after_iocinit | 空 | iocInit 之后的命令 |
| build.file_copy | 空 | 在生成启动文件时复制的文件,源只能来自 `src/` 或 `templates/`,目标相对 `project/` |
| build.epics_env | 空 | 生成 `epicsEnvSet` 语句 |
| settings.report_info | true | 为 true 时在 `st.cmd` 末尾写入上报代码 |
| settings.caputlog_json | false | 启用 caputlog 模块时是否使用 JSON 日志 |
| deploy.labels | 空 | 写入 swarm 服务标签 |
| deploy.resources.limits | cpus 1,memory 1G | 资源上限 |
| deploy.resources.reservations | 空 | 资源预留 |
| deploy.placement.constraints | node.role==worker | 放置约束 |

内置两个模板:asyn、stream,创建时可选,会填充 `build` 段的内容。

### 设计原则

- 遵从 YAML 的使用便利性:列表用原生列表,键值用映射,开关用布尔,不手写分隔格式。
- 配置完整:所有字段都必须出现,用户看到的配置就是程序使用的配置。没有内容的字段写空值(空列表 `[]`、空映射 `{}`、空字符串 `""`),不省略键。
- section 名小写,`deploy` 的结构与 compose 一致。
- `build.db_load` 的 `macros` 用映射,键为宏名,值为宏值,书写顺序即生成 substitutions 文件时的列顺序。含 `:`、`#` 等特殊字符的名字或值需加引号。
- 字符串字段必须写成字符串,不做自动转换:数字(`1`、`1.10`)、布尔(`true`)、空值(`description:`)都会报错,提示加引号,避免值被悄悄改写。宏名重复时报错(ruamel 读取时按重复键处理)。

### `src` 字段的维护

`src` 是程序自动刷新的只读参考字段,方便用户编辑 `build.db_load` 时对照。它记录 `src/` 目录当前实际内容。

状态文件另有 `src_files`,记录上次确认受管理的清单。加载时:

1. 读取状态文件中的 `src_files`。
2. 扫描 `src/` 目录得到实际内容。
3. 清单中有而目录中没有的文件,记为 error "source file lost"。
4. 把实际内容写入 `ioc.yaml` 的 `src` 段。

回写使用 `ruamel.yaml`(仓库已在使用),保留用户的注释和格式。

### 读写与校验

分工:`ruamel.yaml` 负责文件读写并保留注释,`pydantic` v2 负责数据校验,两者不互相替代。

读取:
1. 用 ruamel 的 round-trip 模式读文件,得到保留注释的文档对象。
2. 递归转成普通的 `dict`/`list`/`str`,交给 pydantic 模型校验。
3. 加载、查询、编辑等操作直接使用这份普通字典(取值时容错),校验是否通过不影响识别项目。
4. 构建前(生成、导出)校验必须通过,通过后得到带类型的对象,构建代码用点号访问(如 `cfg.build.db_load[0].file`)。键名不是合法标识符的映射(`macros`、`epics_env`、`deploy.labels`)按字典使用。

写入:
- 修改配置(命令行改配置项、回写 `src`、重命名时改 `basic.name`)时,只修改 ruamel 文档对象中对应路径的值,再写回文件。不用 `model_dump()` 的结果整体写回,以免丢失注释和字段顺序。
- 新建项目时,用带字段说明注释的模板文本生成 `ioc.yaml`,不把字典直接 dump。
- 写入使用临时文件加 `os.replace`,保证原子。

校验分三层:

| 层次 | 内容 | 失败后果 |
|---|---|---|
| 语法 | YAML 能否解析 | 无法读取内容,记 error,state=error |
| 结构 | 字段类型、取值范围(`Literal`)、字段格式(`Field`)、自定义规则(`field_validator`)、键是否齐全 | 加载时只提示:错误记入 `issues`,不影响加载与识别;构建前必须通过,否则阻止生成与导出 |
| 语义与阶段 | 需要结合目录或阶段判断的规则,见下 | 记 warning,阻止对应阶段的操作 |

规则:
- 模型中所有字段都不设默认值,键缺失即结构错误;默认值只存在于创建项目时使用的模板里。字段的值是否必须非空,由各阶段的代码单独检查(如 `build.db_load` 在生成前、`basic.image` 在导出前)。
- 未知字段:模型设为 `extra="allow"`,另写函数递归收集 `model_extra` 中的内容,逐条记 warning。
- 不转换类型:`macros`、`labels`、`epics_env` 的键和值都必须是字符串,列表和映射为空时也要写成 `[]`、`{}`,不能留空。
- 需要结合 `src/` 目录判断的规则(如 `build.db_load.file` 必须存在),通过 `model_validate(data, context=...)` 传入目录信息。
- 错误整理:`ValidationError.errors()` 的 `loc` 拼成字段路径(如 `build.modules.1`),原因整理成统一措辞后记入状态文件的 `issues`。
- 取值范围用 `Literal`;取值在多处复用时再改用 `Enum`。

校验时机:
- 加载时:语法与结构,只提示错误,不影响项目被识别、查询和编辑。
- 构建前(生成、导出):结构必须通过。
- 生成启动文件前:语义与阶段检查。
- 导出前:再加部署相关项(如 `basic.image`)。
- 用户用编辑器修改配置后,立即校验并打印错误(带字段路径)。

### 必填字段(待讨论)

原则:`ioc.yaml` 中列出的字段都必须出现,没有内容时写空值。下表讨论的是**值是否必须非空**,以及在哪个阶段检查。

| 字段 | 值是否必须非空 | 检查阶段 |
|---|---|---|
| basic.name | 是,且等于目录名 | 加载 |
| basic.host | 是,`swarm` 或主机名 | 加载 |
| basic.image | host 为 swarm 时是 | 导出前 |
| basic.bin | 是 | 生成前 |
| basic.description | 否 | |
| src.* | 否,程序维护 | |
| build.modules | 否,允许空列表 | |
| build.db_load | 待确认:空则无法生成,但有的 IOC 可能不需要加载 db | 生成前 |
| build.epics_env | 否 | |
| build.raw_cmd.* | 否 | |
| build.file_copy | 否 | |
| settings.* | 是,布尔值 | 加载 |
| deploy.labels | 否 | |
| deploy.resources.limits.* | 待确认 | |
| deploy.resources.reservations.* | 否,空表示不预留 | |
| deploy.placement.constraints | 待确认 | |

由于键缺失属于结构错误,以后新增字段时,已有项目需要通过功能 14(批量升级)补齐。

## 五、状态文件 `.state.json`

只存程序产生的状态,不存用户可编辑的内容。

```json
{
  "state": "warning",
  "status": "exported",
  "snapshot": "tracked",
  "is_exported": true,
  "src_files": {"db_files": ["ramper.db"], "protocol_files": [], "other_files": []},
  "issues": [
    {"level": "warning", "reason": "snapshot files not create correctly.", "prompt": "", "time": "2026/11/12 10:00:00"}
  ]
}
```

| 字段 | 取值 | 含义 |
|---|---|---|
| state | normal / warning / error | 最新的整体健康状态。error 优先于 warning;导出等操作要求 normal;清除问题后回到 normal |
| status | created / generated / exported / restored / unknown | 项目所处阶段 |
| snapshot | untracked / tracked / error / unknown | 快照状态。新建为 untracked,快照生成成功为 tracked,失败为 error,删除快照回到 untracked |
| is_exported | true / false / unknown | 是否导出过。部署一致性检查要求其为 true |
| src_files | 对象 | `src/` 下受管理的源文件清单,按后缀分为 db_files、protocol_files、other_files |
| issues | 列表 | 状态日志,按时间追加,每项含 level(warning/error)、reason、prompt、time |

约定:
- `state` 单独存储最新状态,`issues` 只作为日志,`state` 不由 `issues` 推导。
- `status` 与 `snapshot` 不随配置复制到新项目,由程序按新项目重新生成。

读写要求:
- 原子写入:先写临时文件,再 `os.replace` 覆盖。
- 进程锁:读写时用 `fcntl.flock` 加锁。锁加在单独的 `.state.json.lock` 文件上,不加在状态文件本身,因为原子写入的 `os.replace` 会替换文件,锁会随旧文件失效。
- 读取失败不崩溃:记为"状态文件丢失/损坏"(state=error,status、snapshot、is_exported 为 unknown)并重建。
- `issues` 每次出现都追加一条,不去重。

## 六、留到代码逻辑阶段

- `issues` 日志的保留策略(重新生成启动文件时是否清空、是否限制条数)。
- `basic.name` 与目录名不一致时的处理方式(记 warning、记 error,还是自动纠正)。
