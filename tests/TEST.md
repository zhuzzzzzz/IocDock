#### 概括测试

进行概括测试，执行以下命令可创建测试 IOC 并将其部署至 swarm

```shell
cd $MANAGER_PATH

# 创建测试IOC
./make-test-prject.sh make
# 部署测试IOC
IocManager swarm --deploy-all-iocs
# 列出所有IOC
IocManager list
# 展示swarm集群信息
IocManager swarm --show-digest
```

#### 异常测试

##### 创建项目后删除 config file

结果符合预期。提示 config file 文件丢失。

1. IocManager create 将恢复配置文件
2. IocManager list 将尝试列出IOC项目，IocManager list -i 命令仅展示状态信息
3. 其余 IocManager 操作无法进行，因未识别到有效配置文件而认定 IOC 不存在
4. 若保存过快照，快照功能正常
5. 若导出过项目，项目一致性检测功能正常

##### 创建项目后删除 state info file

结果符合预期。提示 state info file 文件丢失。

1. IocManager list -i命令展示了相关状态信息，同时也展示了配置信息
2. 后续除 export 操作外(export操作检查IOC状态)，其余 IOC 操作不影响
3. 若保存过快照，则快照恢复功能正常，快照对比操作无法进行(需恢复tracked状态)
4. 若导出过项目，项目一致性检测操作无法进行(需恢复is_exported=true状态)

##### 创建项目后删除 src 目录

结果符合预期。提示 source directory lost 目录丢失，并在首次发现时自动创建空目录。

1. IocManager list -i命令会报错源文件目录不存在，展示了相关状态信息，同时也展示了配置信息
2. 空目录被自动创建，IOC 其他后续操作可正常进行
3. 若保存过快照，则快照对比功能正常，快照恢复功能正常，恢复后可使快照对比保持一致
4. 若导出过项目，项目一致性检测操作不受影响

##### 创建项目后删除 src 目录内文件

结果符合预期。提示 source file lost 目录丢失。

1. IocManager list -i 命令会更新状态信息，提示源文件丢失
2. 若保存过快照，则快照对比功能正常。
3. 若导出过项目，项目一致性检测操作不受影响

##### 创建项目后删除 startup 目录 及 目录内文件

结果符合预期。提示项目不一致

