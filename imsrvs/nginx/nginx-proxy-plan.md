# Nginx 反向代理部署计划

## Context

当前集群的 Web 服务（Grafana、Prometheus、Loki 等）各自直接暴露端口，缺少统一入口。部署 Nginx 作为反向代理，提供 HTTPS 单一入口点。同时将 registry 的 443 端口回收，让 Nginx 统一管理 443 端口。

## 架构决策

- **部署节点**: ubuntu-server (192.168.1.50)，通过 `node.labels.nginx==true` 控制
- **端口**: 443 (HTTPS, host mode) + 80 (HTTP 重定向, host mode)
- **路由方式**: 域名路由
  - 每个服务一个独立的 `server_name`（如 `grafana.<STACK>`, `prometheus.<STACK>`, `registry.<STACK>`）
  - 客户端通过不同域名访问不同后端服务
- **TLS**: 自签名证书（证书 SAN 需包含所有服务域名和节点 IP）
- **网络通信**:
  - Grafana、Prometheus、Alert Analytics 通过 overlay 网络 + Swarm DNS（`127.0.0.11`）+ 动态变量解析访问
  - AlertManager、DBWR 使用 host 网络，通过节点 IP 访问。由 `gen_local_services()` 根据 label 动态生成 upstream 地址。
  - Registry 需要会话粘性（push 时多个 blob 必须到同一后端），通过节点 IP:5000（host mode）访问各副本，Nginx 用 `ip_hash` 做粘性。IP 列表同样动态生成。
- **不代理的全局服务**：cAdvisor(8080)、nodeExporter(9100)、alloy(12345)。每节点一份，各展示本节点数据，保持 host mode 直接访问。

## 路由架构

```
                         ┌──────────────────────────────────────────────────────┐
                         │                  Nginx (443/80)                      │
                         │                                                      │
  registry.<STACK> ─────►│  upstream registry_backend (ip_hash)                 │
  (docker pull/push)     │    → 节点IP:5000 (HTTPS)                            │
                         │                                                      │
  grafana.<STACK> ──────►│  → overlay DNS → srv-grafana:3000                   │
                         │    + WebSocket /api/live/                            │
                         │                                                      │
  prometheus.<STACK> ───►│  → overlay DNS → srv-prometheus:9090                │
                         │                                                      │
  alertmanager.<STACK> ─►│  → upstream alertmanager_backend (节点IP:9093 轮询)  │
                         │                                                      │
  alertanalytics.<STACK>►│  → overlay DNS → srv-alertAnalytics:8000            │
                         │                                                      │
  dbwr.<STACK> ─────────►│  → upstream dbwr_backend (节点IP:8088, WebSocket)   │
                         │                                                      │
  80 (任意域名) ────────►│  → 301 重定向到 HTTPS                               │
                         └──────────────────────────────────────────────────────┘
```

## 需要修改的文件

### 1. 新建文件（`imsrvs/nginx/` 目录）

```
imsrvs/nginx/
├── nginx.yaml                  # 服务定义
├── config/
│   ├── nginx.conf              # 主配置
│   └── conf.d/
│       ├── registry.conf.template   # registry 域名路由模板
│       └── default.conf.template    # 默认路径路由模板
└── certs/                      # 证书目录（运行时由 gen_local_services 填充）
    └── .gitkeep
```

`gen_local_services()` 读取 `.template` 文件，替换占位符后生成最终的 `.conf` 文件到同目录。

### 2. 修改 registry 端口配置

**文件**: `imsrvs/registry/registry.yaml`

移除 routing mesh 的 443 端口映射，将 5000 改为 host mode 暴露，保留 5001 host mode（metrics）：

```yaml
ports:
- target: 5000
  published: 5000
  mode: host
- target: 5001
  published: 5001
  mode: host
```

### 3. 注册 Nginx 服务

**`imutils/IMServiceDefinition.py`** — LocalServicesList 添加：
```python
("nginx", "nginx:1.28"),
```

### 4. 添加 gen_local_services 逻辑

**`imutils/SwarmClass.py`** — 在 `gen_local_services()` 中添加 nginx 设置块：
- 检查 `SERVER_CERT_PATH/nginx/nginx.crt` 和 `.key` 是否存在
- 验证证书有效性
- 拷贝到 `imsrvs/nginx/certs/`
- 读取 `conf.d/registry.conf.template`，替换 `<REGISTRY_SERVERS>` 为 registry label 节点的 IP:5000 列表，写入 `conf.d/registry.conf`
- 读取 `conf.d/default.conf.template`，替换 `<ALERTMANAGER_SERVERS>` 和 `<DBWR_SERVERS>` 为对应 label 节点的 IP 列表，写入 `conf.d/default.conf`

## Nginx 配置核心内容

### `nginx.yaml` 服务定义

```yaml
services:
  srv-nginx:
    image: registry.iasf/nginx:1.28
    labels:
      service-type: local
      prometheus-job: nginx
    ports:
    - target: 443
      published: 443
      mode: host
    - target: 80
      published: 80
      mode: host
    deploy:
      mode: replicated
      replicas: 1
      resources:
        limits:
          cpus: "1"
          memory: 512M
      placement:
        constraints:
        - node.platform.os==linux
        - node.labels.nginx==true
    volumes:
    - source: ./config/nginx.conf
      target: /etc/nginx/nginx.conf
      type: bind
      read_only: true
    - source: ./config/conf.d
      target: /etc/nginx/conf.d
      type: bind
      read_only: true
    - source: ./certs
      target: /etc/nginx/certs
      type: bind
      read_only: true
    - source: /etc/localtime
      target: /etc/localtime
      type: bind
      read_only: true
```

### `config/nginx.conf` — 主配置

```nginx
user  nginx;
worker_processes  auto;

error_log  /var/log/nginx/error.log warn;
pid        /var/run/nginx.pid;

events {
    worker_connections  1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                      '$status $body_bytes_sent "$http_referer" '
                      '"$http_x_forwarded_for" upstream=$upstream_addr';

    access_log  /var/log/nginx/access.log  main;

    sendfile        on;
    keepalive_timeout  65;
    client_max_body_size  0;

    include /etc/nginx/conf.d/*.conf;
}
```

### `conf.d/registry.conf.template` — Registry 域名路由

```nginx
upstream registry_backend {
    ip_hash;
    <REGISTRY_SERVERS>
}

server {
    listen 443 ssl;
    server_name registry.<PREFIX_STACK_NAME>;

    ssl_certificate     /etc/nginx/certs/nginx.crt;
    ssl_certificate_key /etc/nginx/certs/nginx.key;
    ssl_protocols       TLSv1.2 TLSv1.3;

    client_max_body_size 0;
    chunked_transfer_encoding on;

    location / {
        proxy_pass https://registry_backend;
        proxy_ssl_verify off;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

`gen_local_services()` 将 `<REGISTRY_SERVERS>` 替换为节点 IP 列表，`<PREFIX_STACK_NAME>` 替换为 stack 名：
```
    server 192.168.1.50:5000;
    server 192.168.1.52:5000;
    server 192.168.1.53:5000;
```

说明：
- `ip_hash`：同一客户端 IP 的请求固定到同一后端，确保 push 镜像时 blob 不分散
- `proxy_pass https://`：registry 自身配了 TLS（`http.tls` 段），所以用 HTTPS 转发
- `proxy_ssl_verify off`：registry 使用自签名证书，跳过后端证书验证

### `conf.d/default.conf.template` — 各服务域名路由

```nginx
upstream alertmanager_backend {
    <ALERTMANAGER_SERVERS>
}

upstream dbwr_backend {
    <DBWR_SERVERS>
}

# Grafana
server {
    listen 443 ssl;
    server_name grafana.<PREFIX_STACK_NAME>;

    ssl_certificate     /etc/nginx/certs/nginx.crt;
    ssl_certificate_key /etc/nginx/certs/nginx.key;
    ssl_protocols       TLSv1.2 TLSv1.3;

    location / {
        resolver 127.0.0.11 valid=30s;
        set $upstream_grafana tasks.<PREFIX_STACK_NAME>_srv-grafana;
        proxy_pass http://$upstream_grafana:3000;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/live/ {
        resolver 127.0.0.11 valid=30s;
        set $upstream_grafana tasks.<PREFIX_STACK_NAME>_srv-grafana;
        proxy_pass http://$upstream_grafana:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $http_host;
    }
}

# Prometheus
server {
    listen 443 ssl;
    server_name prometheus.<PREFIX_STACK_NAME>;
    ...
}

# AlertManager (upstream 轮询)
server {
    listen 443 ssl;
    server_name alertmanager.<PREFIX_STACK_NAME>;
    ...
    location / {
        proxy_pass http://alertmanager_backend;
        ...
    }
}

# Alert Analytics
server {
    listen 443 ssl;
    server_name alertanalytics.<PREFIX_STACK_NAME>;
    ...
}

# DBWR (upstream + WebSocket)
server {
    listen 443 ssl;
    server_name dbwr.<PREFIX_STACK_NAME>;
    ...
    location / {
        proxy_pass http://dbwr_backend/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        ...
    }
}

# HTTP → HTTPS 重定向
server {
    listen 80 default_server;
    server_name _;
    return 301 https://$host$request_uri;
}
```

说明：
- 每个服务通过独立的 `server_name` 域名路由，无需子路径和 strip prefix
- overlay 网络服务使用 `resolver 127.0.0.11` + `set $variable` 实现动态 DNS 解析
- host 网络服务（AlertManager、DBWR）使用 upstream 块，IP 由 `gen_local_services()` 动态生成
- DBWR 的 `proxy_pass` 尾部斜杠用于 strip `/` 前缀（后端监听根路径）

### 路由总览

| 域名 | 后端 | 网络方式 | 备注 |
| ------ | ------ | ---------- | ------ |
| `registry.<STACK>` | 节点IP:5000 | 节点 IP + ip_hash | HTTPS 转发，会话粘性 |
| `grafana.<STACK>` | srv-grafana:3000 | overlay DNS | 含 WebSocket `/api/live/` |
| `prometheus.<STACK>` | srv-prometheus:9090 | overlay DNS | |
| `alertmanager.<STACK>` | 节点IP:9093 | upstream 轮询 | host 网络 |
| `alertanalytics.<STACK>` | srv-alertAnalytics:8000 | overlay DNS | |
| `dbwr.<STACK>` | 节点IP:8088 | upstream | host 网络，含 WebSocket |

## 实施步骤

1. 创建 `imsrvs/nginx/` 目录结构和配置文件（nginx.yaml、nginx.conf、模板文件）
2. 修改 `IMServiceDefinition.py` 添加 nginx 注册
3. 修改 `SwarmClass.py` 添加 nginx 设置逻辑（证书拷贝 + 模板渲染生成最终 .conf + upstream 节点检查）
4. 修改 `registry.yaml` 移除 443 routing mesh，改为 5000 host mode

## 验证方法

1. 给节点添加 label：`docker node update --label-add nginx=true ubuntu-server`
2. 生成 TLS 证书：`cd imtools/certs/scripts && ./make-certs.sh --server nginx --subject-alt-names "DNS:registry.iasf,IP:192.168.1.50,..."`
3. 推送 nginx 镜像到私有仓库
4. 执行 `IocManager gen-services local && IocManager deploy nginx`
5. 重新部署修改过的服务（registry）
6. 测试：
   ```bash
   # Registry 域名路由
   docker pull registry.iasf/nginx:1.28
   curl -k https://registry.iasf/v2/_catalog

   # 各服务域名路由
   curl -k https://grafana.iasf/
   curl -k https://prometheus.iasf/
   curl -k https://alertmanager.iasf/
   curl -k https://alertanalytics.iasf/
   curl -k https://dbwr.iasf/
   ```

## 风险和注意事项

- **Registry 切换顺序**: 先部署 nginx 并确认工作，再移除 registry 的 443 routing mesh 端口，避免中间不可用。由于 `/etc/hosts` 将 `registry.iasf` 指向 192.168.1.50，切换后对 Docker client 透明。
- **Registry 粘性**: 通过 `ip_hash` + 节点 IP:5000 实现。同一客户端 push 镜像时所有 blob 上传都到同一后端，避免 NFS 缓存不一致。
- **动态生成的配置**: alertManager/dbwr/registry 的 upstream IP 由 `gen_local_services()` 根据 label 分布生成。label 迁移后需重新执行 `IocManager gen-services local` 并重新部署 nginx。
- **upstream 节点检查**: `gen_local_services()` 会检查 registry/alertmanager/dbwr 标签节点是否存在，为空则报错并中止配置生成，避免空 upstream 导致 nginx 无法启动。
