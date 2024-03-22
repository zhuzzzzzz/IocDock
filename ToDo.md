- README文件改为.md格式
- 更新README文件 按功能和操作编写使用文档
- 备份文件的恢复
- 导出文件至ioc-for-docker目录时，不应导出全部IOC，当只有部分IOC需要修改时，这将覆盖其他不需修改的IOC目录，导致他们都需要重启操作系统
以更新NFS mount. 可以设置选择导出哪个或哪些IOC又或是全部导出(给出提示！)
- 考虑增加导出目录IOC配置与当前仓库IOC配置的比较来判断是否运行的是最新的IOC
- 考虑设置EPICS_CAS_INTF_ADDR_LIST 绑定EPICS运行将使用的网卡


当前项目目录结构
Docker(NFS主文件夹)
├── images
│   ├── base-beta-0.1.1.tar.gz
│   └── ioc-exec-beta-0.1.1.tar.gz
├── ioc-backup
│   └── 2024.03.22-13:57:24.tar.gz
├── ioc-for-docker
│   ├── worker-standard
│   │   ├── compose.yaml
│   │   ├── iocLog
│   │   ├── worker-standard_1
│   │   ├── worker-standard_2
│   │   └── worker-standard_3
│   ├── worker_test
│   │   ├── compose.yaml
│   │   ├── iocLog
│   │   ├── worker_test_1
│   │   ├── worker_test_2
│   │   └── worker_test_3
│   ├── worker_test1
│   │   ├── compose.yaml
│   │   ├── iocLog
│   │   ├── worker_test1_1
│   │   ├── worker_test1_2
│   │   └── worker_test1_3
│   └── worker_test2
│       ├── compose.yaml
│       ├── iocLog
│       ├── worker_test2_1
│       ├── worker_test2_2
│       └── worker_test2_3
├── registry
│   └── docker
│       └── registry
└── repository-ioc
    ├── auto-test-for-IocManager.sh
    ├── imtools
    │   ├── docker-manager
    │   ├── IMFuncsAndConst.py
    │   ├── IocClass.py
    │   ├── ioc-snapshot
    │   ├── __pycache__
    │   └── template
    ├── IocManager.py
    ├── ioc-repository
    │   ├── worker-standard_1
    │   ├── worker-standard_2
    │   ├── worker-standard_3
    │   ├── worker_test_1
    │   ├── worker_test1_1
    │   ├── worker_test1_2
    │   ├── worker_test1_3
    │   ├── worker_test_2
    │   ├── worker_test2_1
    │   ├── worker_test2_2
    │   ├── worker_test2_3
    │   └── worker_test_3
    ├── make-test-project.sh
    └── README

