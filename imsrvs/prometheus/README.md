#### 设置 docker daemon 暴露指标

```
# daemon.json
{
    "metrics-addr": "0.0.0.0:9323",
}
```

#### 设置 docker daemon 监听本地 2375 端口(可选)

```
# daemon.json
{
    "hosts": ["unix:///var/run/docker.sock", "tcp://127.0.0.10:2375"]
}
```

或

```shell
systemctl edit docker.service
# [Service]
# ExecStart=
# ExecStart=/usr/bin/dockerd -H fd:// -H tcp://127.0.0.10:2375 
systemctl daemon-reload
systemctl restart docker.service
```
