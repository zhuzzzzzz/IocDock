#### 部署 registry 运行环境

0. 切换至 `srcipts/` 目录
1. 执行 `./prepare-images.sh` 在本地拉取镜像并为镜像重命名
2. 执行 `IocManager swarm --gen-builtin-services` 为 registry 项目生成部署文件
3. 执行 `docker node update <node_name> --lable-add registry=true` 为主机指定 registry 部署标签
4. 确保要部署 registry 服务的节点都挂载了相应的 NFS 目录
5. 执行 `IocManager service registry --deploy` 部署 registry 服务
6. 执行 `IocManager cluster --registry-login` 为集群节点登录镜像仓库
7. 再次执行 `./prepare-images.sh` 上传镜像

### 镜像操作

#### 镜像拉取和推送

- 为镜像重新打上标签   
  ```docker tag busybox:latest registry.iasf/busybox```


- 推送镜像   
  ```docker push registry.iasf/busybox```


- 拉取镜像   
  ```docker pull registry.iasf/busybox```

#### 管理 registry

- 查看镜像列表   
  ```curl -u user:password https://registry.iasf/v2/_catalog```

- 查看镜像标签列表   
  ```curl -u user:password https://registry.iasf/v2/image-name/tags/list```

- 查看镜像清单(manifests)   
  ```curl -I -u user:password https://registry.iasf/v2/image-name/manifests/tag-name```   
  或    
  ```curl -I -H "Accept: application/vnd.docker.distribution.manifest.v2+json" https://registry.iasf/v2/nginx/manifests/latest ```

- 镜像删除  
  ```curl -X DELETE -u username:password https://registry.iasf/v2/nginx/manifests/sha256:abc123```

- 镜像删除后需定期执行垃圾回收!
