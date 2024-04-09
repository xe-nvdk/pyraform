# Pyraform

![Pyraform](<pyraform.webp>)

Pyraform is a Python-based tool that simplifies Infrastructure as Code (IaC) for managing AWS (more Cloud Providers coming soon) resources. It leverages easy-to-write YAML configurations for efficient setup, alteration, and dismantling of cloud infrastructures, ensuring consistency, reliability, and ease of use.

## Features

- **Infrastructure as Code**: Define and manage your AWS infrastructure using simple YAML files.
- **State Management**: Track your infrastructure's current state with a `state.json` file.
- **Resource Management**: Automate the creation, modification, and deletion of resources like VMs and disks.
- **AWS Integration**: Seamlessly interacts with AWS services using Boto3.
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
  - type: vm
    name: web-server
    properties:
      image_id: ami-123456
      size: t2.micro
  - type: disk
    name: web-server-disk
    properties:
      size: 10
      attached_vm: web-server
```

```tip
Right now everything work as separate module, so you need to specify ec2.py or dns.py to deploy or destroy the infrastructure. The idea is to make it work as a single module in the future.
```

## Deploying Infrastructure EC2
Run the following command to deploy your infrastructure:

```bash
python ec2.py deploy
```

## Destroying Infrastructure EC2
To tear down your infrastructure, use:

```bash
python3 ec2.py destroy
```

## Contributing
Contributions to Pyraform are welcome! Please refer to the CONTRIBUTING.md file for guidelines.

## License
This project is licensed under the MIT License - see the LICENSE file for details.
