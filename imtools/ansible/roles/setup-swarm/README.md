```yaml
# playbook.yaml 
- name: test role
  hosts: all
  become: true
  gather_facts: true
  vars:
    ansible_ssh_user: ubuntu
    for_user: "{{ ansible_ssh_user }}"
  roles:
    - setup-swarm
```