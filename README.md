# docker-deploy
Docker deployment script

## Requirements

* plumbum, install: `pip install plumbum` (`yum install python-pip` to install pip on CentOS 7).

## Install

Install as a system wide command:

```
ln -s /root/docker-deploy/docker.py /usr/bin/docker.py
```

## Deploy configuration

JSON layout:

```
{
    "shared_environment_variables": [...],
    "container-name-1": {
        "image": "",
        "restart": "",
        "remove": false,
        "daemon": true,             //defaults (when omitted) to false
        "interactive: true          //defaults (when omitted) to false
        "memory": "",
        "port_mappings": [...],
        "volume_mappings" : [...],
        "environment_variables": [...]
    },
    "container-name-1": {
        ...
    },
    ...
    "container-name-n": {
        ...
    }
}
```