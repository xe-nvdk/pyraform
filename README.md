# Pyraform

Pyraform is a Python-based tool that simplifies Infrastructure as Code (IaC) for managing AWS resources. It leverages easy-to-write YAML configurations for efficient setup, alteration, and dismantling of cloud infrastructures, ensuring consistency, reliability, and ease of use.

## Features

- **Infrastructure as Code**: Define and manage your AWS infrastructure using simple YAML files.
- **State Management**: Track your infrastructure's current state with a `state.json` file.
- **Resource Management**: Automate the creation, modification, and deletion of resources like VMs and disks.
- **AWS Integration**: Seamlessly interacts with AWS services using Boto3.
- **More Cloud Providers are coming. Your contribution is vital for this project.

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

## Deploying Infrastructure
Run the following command to deploy your infrastructure:

```bash
python main.py deploy
```

## Destroying Infrastructure
To tear down your infrastructure, use:

```bash
python3 main.py destroy
```

## Contributing
Contributions to Pyraform are welcome! Please refer to the CONTRIBUTING.md file for guidelines.

## License
This project is licensed under the MIT License - see the LICENSE file for details.
