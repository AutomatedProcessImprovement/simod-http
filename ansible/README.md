# Configuration management with Ansible

Ansible is used to manage the configuration of remote machines. The following scripts are available:

- [hosts.yaml](hosts.yaml): lists available machines ansible. Notice, `pix` private key is required to access the machines.
- [deploy.yaml](deploy.yaml): deploys simod-http to a remote machine. Notice, this playbook requires FLOWER_USER and FLOWER_PASSWORD environment variables to be set if run outside of GitHub Actions.
- [install-docker.yaml](install-docker.yaml): installs Docker on a remote machine (see [Docker installation instructions](https://docs.docker.com/engine/install/ubuntu/))
  
Run the scripts with `ansible-playbook -i hosts.yaml <script>.yaml` from the root directory of this repository:

```bash
ansible-playbook -i ansible/hosts.yaml ansible/install-docker.yaml
```