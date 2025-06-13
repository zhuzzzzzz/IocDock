#### 概括测试

包含项目的创建、设置、生成运行文件、导出运行文件、生成部署文件

```shell
cd $MANAGER_PATH
./make-test-prject.sh make
```

#### 异常测试

##### 文件丢失测试

1. 创建项目后删除 config file   
   结果符合预期。提示 config file 文件丢失，list 命令仅展示状态信息，
   后续 IOC 操作无法进行，因未识别到有效配置文件而认定 IOC 不存在


2. 创建项目后删除 state info file   
   结果符合预期。提示 state info file 文件丢失，list 命令展示了相关状态信息，同时也展示了配置信息，
   后续 IOC 操作依然可以进行


3. 创建项目后删除 src 目录   
   结果符合预期。提示 source directory lost 目录丢失，并自动创建空目录。

##### 错误配置测试