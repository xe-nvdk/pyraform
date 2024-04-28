# Pyraform

![Pyraform](<pyraform.webp>)

Pyraform is a Python-based tool that simplifies Infrastructure as Code (IaC) for managing AWS (more Cloud Providers coming soon) resources. It leverages easy-to-write YAML configurations for efficient setup, alteration, and dismantling of cloud infrastructures, ensuring consistency, reliability, and ease of use.

## Features

- **Infrastructure as Code**: Define and manage your AWS infrastructure using simple YAML files.
- **State Management**: Track your infrastructure's current state with a `state.json` file.
- **Resource Management**: Automate the creation, modification, and deletion of resources like VMs and disks.
- **DigitalOcean and AWS Integration**: Seamlessly interacts with AWS and DigitalOcean services.
- **More Cloud Providers are coming**. Your contribution is vital to this project.

## Getting Started

To use Pyraform, clone this repository and install the required dependencies:

```bash
git clone https://github.com/xe-nvdk/pyraform.git
cd pyraform
pip install -r requirements.txt
```

## Configuration
Define your infrastructure in a YAML file (e.g., infrastructure.yml). Here's an example to get you started:

```yaml
resources:
  - type: droplet
    name: web-server
    properties:
      image: ubuntu-20-04-x64  # Example image slug for Ubuntu 20.04
      size: s-1vcpu-1gb        # Example droplet size, similar to t2.micro
      ssh_keys: [m1]           # You would specify the SSH key ID or fingerprint
      region: nyc3             # New York 3 datacenter
      user_data: "./webserver.sh"  # Path to a script to run on instance creation
      tags:
        - web
        - production
```

## Deploying a DigitalOcean Droplet
Run the following command to deploy your infrastructure:

```bash
python3 pyraform.py deploy
```

Something like should appear in your terminal. Press 'y' to move forward: 

```bash
Infrastructure config:
+------------+---------+-------------------+------------------------------------------------------------------------------------------------------------------------------------+
|    Name    |  Type   |      Action       |                                                              Details                                                               |
+------------+---------+-------------------+------------------------------------------------------------------------------------------------------------------------------------+
| web-server | droplet | creation required | image: ubuntu-20-04-x64, size: s-1vcpu-1gb, ssh_keys: ['m1'], region: nyc3, user_data: ./webserver.sh, tags: ['web', 'production'] |
+------------+---------+-------------------+------------------------------------------------------------------------------------------------------------------------------------+

Plan: 1 to add, 0 to change, 0 to destroy.
Proceed with the deployment? [y/n]: 
```
If everything is going good... something like that should appear.

```bash
Creating Droplet: web-server with properties {'image': 'ubuntu-20-04-x64', 'size': 's-1vcpu-1gb', 'ssh_keys': ['m1'], 'region': 'nyc3', 'user_data': './webserver.sh', 'tags': ['web', 'production']}
Droplet 'web-server' creation request sent.
Droplet web-server created with ID: 415570865
Infrastructure deployment process completed.
```

## Destroying DigitalOcean Droplet
To tear down your infrastructure, use:

```bash
python3 pyraform destroy
```

## Contributing
Contributions to Pyraform are welcome! Please refer to the CONTRIBUTING.md file for guidelines.

## License
This project is licensed under the MIT License - see the LICENSE file for details.