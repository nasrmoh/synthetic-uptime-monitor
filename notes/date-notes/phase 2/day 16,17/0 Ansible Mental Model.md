# What Ansible Is

Ansible is an open-source automation tool used to configure and maintain systems.

Common uses include:

* Removing repetitive manual steps
* Maintaining system configuration
* Deploying software
* Performing zero-downtime rolling updates

The central idea is:

> We describe the **desired state** of a system, and Ansible works to make the system match that state.

This is different from simply describing a sequence of commands to execute.

For example, instead of saying:

```text
Run:
mkdir /opt/app
```

we describe the desired result:

```text
/opt/app should exist
```

Ansible determines whether it needs to do anything to make that true.

---

# Core Characteristics

Ansible is designed around:

* Agentless operation
* Simplicity
* Scalability and flexibility
* Idempotence and predictability

## Agentless

Ansible does not require an Ansible-specific agent to be installed on the machines it manages.

Instead, it can connect to remote Linux machines using mechanisms such as SSH.

Conceptually:

```text
Control Node
    |
    | SSH
    v
Managed Node
```

For this project:

```text
Development Machine
    |
    | SSH
    v
Azure Linux VM
```

---

## Simplicity

Ansible automation is primarily written in YAML.

The goal is for playbooks to be relatively human-readable and understandable as configuration documentation.

---

## Scalability and Flexibility

Ansible has a modular design that supports many:

* Operating systems
* Cloud platforms
* Network devices
* Infrastructure configurations

The same basic model can therefore scale from managing one VM to managing many machines.

---

## Idempotence and Predictability

Ansible is designed so that repeatedly applying the same configuration should lead to the same final state.

This is covered in more detail below.

---

# YAML Playbooks

Ansible automation is written in **playbooks** using YAML.

A playbook describes what configuration should exist on one or more managed machines.

For example:

```text
VM should have:

- Docker installed
- Application directory present
- Correct configuration files
- Correct user permissions
```

The playbook describes the desired result, and Ansible determines what changes are necessary.

---

# Idempotence

**Idempotence** means:

> Running the same automation repeatedly should produce the same final state.

If a machine already matches the desired configuration, Ansible should not unnecessarily modify it.

For example:

```text
Desired state:
Docker should be installed

Current state:
Docker is not installed

Result:
Ansible installs Docker
Status: changed
```

If we immediately run the same playbook again:

```text
Desired state:
Docker should be installed

Current state:
Docker is already installed

Result:
No modification required
Status: ok
```

This means we might see:

```text
First run:
changed > 0

Second run:
changed = 0
```

assuming nothing changed between the two runs.

This becomes an important gate later in the project.

---

# Control Node and Managed Nodes

Ansible works with two important sides.

## Control Node

The **control node** is the machine where Ansible itself is run.

For this project, that will usually be our development machine.

For example:

```bash
ansible-playbook ...
```

runs on the control node.

## Managed Node

A **managed node** is a machine that Ansible connects to and configures.

For this project, the managed node is our Azure Linux VM.

Conceptually:

```text
Development Machine
    |
    | runs Ansible
    |
    | SSH
    v
Azure Linux VM
```

---

# Inventory

An **inventory** tells Ansible which machines it manages and how to locate them.

An inventory can contain:

* IP addresses
* Fully qualified domain names
* Hostnames
* Host groups
* Variables describing how to connect

For example:

```ini
[myhosts]
192.0.2.50
192.0.2.51
192.0.2.52
```

Here:

```text
myhosts
```

is a group containing three managed hosts.

---

## Inventory Prerequisites

To use an inventory against a real remote host, we need:

```text
IP address or FQDN of the host
        +
SSH access to the host
```

For SSH key authentication, our public key must be present in the host's:

```text
~/.ssh/authorized_keys
```

The managed host could be:

* A container
* A local VM
* A cloud VM
* A physical machine

For this project, it will be the Terraform-created Azure VM.

---

# Why Inventory Exists

Without an inventory, we would repeatedly need to tell Ansible things such as:

* Which machines should be managed?
* What are their IP addresses?
* Which SSH user should be used?
* Which machines belong together?

The inventory centralizes this information.

Conceptually:

```text
Inventory
    |
    +-- application_servers
    |      +-- server1
    |      +-- server2
    |
    +-- database_servers
           +-- db1
```

Our project is initially much simpler:

```text
Inventory
    |
    +-- Azure application VM
```

---

# INI or YAML Inventory

Ansible inventories can be written in either INI or YAML.

## INI

INI is straightforward and easy to read for a small number of nodes.

```ini
[myhosts]
192.0.2.50
192.0.2.51
192.0.2.52
```

For a project with one VM, this may be all we need initially.

---

## YAML

YAML becomes useful as the inventory grows because it makes host names, groups, and variables more explicit.

```yaml
myhosts:
  hosts:
    my_host_01:
      ansible_host: 192.0.2.50
    my_host_02:
      ansible_host: 192.0.2.51
    my_host_03:
      ansible_host: 192.0.2.52
```

Here the names:

```text
my_host_01
my_host_02
my_host_03
```

are inventory names, while `ansible_host` contains the actual address Ansible connects to.

---

# Verifying an Inventory

We can inspect how Ansible interprets an inventory using:

```bash
ansible-inventory -i inventory.ini --list
```

This is useful for verifying:

* Hosts
* Groups
* Variables
* Inventory structure

This is a good check before running real configuration tasks.

---

# Testing Connectivity

Ansible provides a `ping` module that can be used to verify that Ansible can communicate with managed hosts.

Example:

```bash
ansible myhosts -m ping -i inventory.ini
```

A successful result looks roughly like:

```text
SUCCESS
ping: pong
changed: false
```

This is not simply an ICMP network ping.

It verifies that Ansible can connect to the machine and successfully execute the module.

For our project, the flow is:

```text
Terraform creates Azure VM
        ↓
SSH access works
        ↓
Inventory identifies VM
        ↓
Ansible ping succeeds
```

Only after this should we start configuring the machine.

---

## Different SSH Username

If the username on the managed node differs from the username on the control node, we can specify it using:

```bash
-u <username>
```

For example:

```bash
ansible myhosts -m ping -i inventory.ini -u azureuser
```

---

# Inventory Variables

An inventory can also store values Ansible needs for specific hosts or groups.

This prevents us from repeatedly passing the same information through command-line arguments.

Variables can apply to individual hosts.

```yaml
webservers:
  hosts:
    webserver01:
      ansible_host: 192.0.2.140
      http_port: 80

    webserver02:
      ansible_host: 192.0.2.150
      http_port: 443
```

Variables can also apply to an entire group using `vars`.

```yaml
webservers:
  hosts:
    webserver01:
      ansible_host: 192.0.2.140

    webserver02:
      ansible_host: 192.0.2.150

  vars:
    ansible_user: my_server_user
```

Here:

```text
ansible_host
```

tells Ansible where the machine is located.

```text
ansible_user
```

tells Ansible which SSH user to use.

---

# Inventory Groups

Hosts can be organized into logical groups.

The documentation suggests thinking about groups according to:

## What

What kind of machine is it?

Examples:

```text
web
db
leaf
spine
```

## Where

Where is the machine located?

Examples:

```text
region
datacenter
floor
building
```

## When

Which environment or stage does it belong to?

Examples:

```text
development
test
staging
production
```

---

# Inventory Group Naming

Group names should be:

* Meaningful
* Unique
* Case-sensitive
* Free of spaces
* Free of hyphens
* Not begin with a number

For example:

```text
floor_19     good
19th_floor   bad
floor-19     bad
```

---

# Metagroups

Groups can themselves be combined into larger groups using `children`.

Basic syntax:

```yaml
metagroupname:
  children:
```

Conceptually:

```text
datacenter
    |
    +-- network
    |     +-- leafs
    |     +-- spines
    |
    +-- webservers
```

For example:

```yaml
leafs:
  hosts:
    leaf01:
      ansible_host: 192.0.2.100

spines:
  hosts:
    spine01:
      ansible_host: 192.0.2.120

network:
  children:
    leafs:
    spines:

webservers:
  hosts:
    webserver01:
      ansible_host: 192.0.2.140

datacenter:
  children:
    network:
    webservers:
```

A group can belong to more than one metagroup.

For our current project, this is useful to understand conceptually, but probably unnecessary while we only have one VM.

---

# Variable Inheritance

Variables defined on parent groups can apply to hosts in child groups.

If a child group defines the same variable, the child's value overrides the parent value.

Because multiple parent groups can make inheritance more difficult to reason about, keeping group relationships simple makes configuration more predictable.

---

# Playbooks

A **playbook** is an automation blueprint written in YAML.

The basic hierarchy is:

```text
Playbook
    ↓
one or more Plays
    ↓
Tasks
    ↓
Modules
```

---

# Play

A **play** maps a collection of tasks to selected managed hosts.

Conceptually:

```text
On these hosts:

application_servers

perform these tasks:

1. Install Docker
2. Create application directory
3. Configure permissions
```

A play therefore connects:

```text
hosts
+
configuration tasks
```

---

# Task

A **task** represents one operation Ansible should perform.

Examples include:

* Ensure a directory exists
* Ensure Docker is installed
* Copy a configuration file
* Start a service
* Create a user
* Configure permissions

Tasks run in the order they appear in the play.

```text
Task 1
    ↓
Task 2
    ↓
Task 3
```

This matters when later tasks depend on earlier configuration.

---

# Module

A **module** is the Ansible functionality used to perform a task on a managed node.

For example:

```text
Task:
"Make sure package X is installed"

        ↓

Package module

        ↓

Managed node
```

Modules exist for operations such as:

* File management
* Package installation
* Service management
* Copying files
* User management

Instead of manually writing shell commands for every operation, we generally use modules that already understand the desired state we want to enforce.

---

# Fully Qualified Collection Names

Modules are organized into collections.

A module can be referenced using its **Fully Qualified Collection Name**, or FQCN.

For example:

```text
ansible.builtin.ping
```

This can be read as:

```text
ansible
    ↓
builtin collection
    ↓
ping module
```

Using the FQCN makes it explicit which module is being used.

---

# Basic Playbook Structure

A simple playbook might look like:

```yaml
- name: My first play
  hosts: myhosts

  tasks:
    - name: Ping my hosts
      ansible.builtin.ping:

    - name: Print message
      ansible.builtin.debug:
        msg: Hello world
```

We can read this as:

```text
Play:
"My first play"

Targets:
myhosts

Tasks:
1. Ping each host
2. Print a message
```

---

# Running a Playbook

A playbook can be run using:

```bash
ansible-playbook -i inventory.ini playbook.yaml
```

This means:

```text
Use inventory.ini
        +
Run playbook.yaml
```

Ansible reads the inventory, selects the hosts specified by the play, and executes the tasks against them.

---

# Reading Playbook Output

Example output:

```text
PLAY [My first play] ******************************

TASK [Gathering Facts] ****************************
ok: [192.0.2.50]

TASK [Ping my hosts] ******************************
ok: [192.0.2.50]

TASK [Print message] ******************************
ok: [192.0.2.50] => {
    "msg": "Hello world"
}

PLAY RECAP ****************************************
192.0.2.50: ok=3 changed=0 unreachable=0 failed=0
```

From this output we can see:

* The name of the play
* The name of each task
* The status of each task for each host
* A final recap for each managed host

---

# Task Statuses

## `ok`

`ok` means the task completed successfully and did not need to modify the managed node.

Example:

```text
Docker already installed

→ ok
```

## `changed`

`changed` means Ansible had to modify the managed node to make it match the desired configuration.

Example:

```text
Docker missing

→ Ansible installs Docker

→ changed
```

The distinction between `ok` and `changed` is important when checking idempotence.

---


## `become`

`become` tells ansible to execute a task with elevated privileges. this is effectively running a command with `sudo`

for example

```
- name: Configure server
  hosts: application_servers
  become: true
```

this will cause the entire play to be played with elevated privileges 


or you can do it at the task level

```
- name: Some privileged Task
  become: true
```


---

# Play Recap Fields

The final recap can contain fields such as:

```text
ok
```

Tasks that completed successfully.

```text
changed
```

Tasks that modified the machine.

```text
unreachable
```

Hosts Ansible could not communicate with.

```text
failed
```

Tasks that executed but failed.

```text
skipped
```

Tasks that were skipped.

```text
rescued
```

Tasks whose failure was handled by a rescue block.

```text
ignored
```

Failures that were explicitly ignored.

For our later idempotency test, we want something similar to:

```text
changed=0
failed=0
unreachable=0
```

on the second playbook run.

---

# Gathering Facts

When a playbook runs, Ansible normally performs an automatic step called:

```text
Gathering Facts
```

Ansible collects information about the managed system, such as details about its operating system and environment.

Those facts can later be used by tasks in the playbook.

---

# Why Descriptive Task Names Matter

We should give plays and tasks names that clearly describe what they do.

Instead of:

```yaml
- name: Install
```

prefer something like:

```yaml
- name: Install Docker package
```

When debugging a larger playbook, the output will then tell us exactly which operation:

```text
changed
failed
or
succeeded
```

This makes troubleshooting much easier.

---

# Ansible vs Bash

Ansible can initially look like a more complicated Bash setup script, but the important difference is the **desired-state model**.

A Bash script commonly says:

```text
run command A
run command B
run command C
```

Ansible generally says:

```text
package X should be installed

directory Y should exist

service Z should be running
```

Ansible then determines whether a change is required.

This makes Ansible similar to Terraform conceptually.

Terraform describes the desired state of our Azure infrastructure.

Ansible describes the desired state of the operating system and software inside the VM.

```text
Terraform
    |
    | creates infrastructure
    v
Azure Linux VM
    |
    | Ansible configures
    v
Configured application server
```

---

# How This Fits the Synthetic Uptime Monitor

Terraform answers:

```text
What Azure infrastructure should exist?
```

For example:

```text
Resource group
VNet
Subnet
NSG
VM
Public IP
```

Ansible answers:

```text
What configuration should exist inside the VM?
```

Later, Ansible can ensure the VM has:

```text
Docker
Docker Compose
application user
application directories
permissions
nginx
Certbot
monitoring configuration
runtime configuration
```

Ansible should **not** create Azure infrastructure.

The intended division of responsibility is:

```text
Terraform
    ↓
creates the machine

Ansible
    ↓
turns it into the machine our application needs
```

---

# Mental Model

```text
Inventory
= Which machines Ansible manages

Host
= One managed machine

Group
= A named collection of hosts

Metagroup
= A group containing other groups

Playbook
= Automation blueprint

Play
= Tasks applied to selected hosts

Task
= One operation Ansible should perform

Module
= Ansible functionality that performs the operation

Variable
= Configurable value used by inventories or playbooks

Idempotence
= Re-running the same automation should not unnecessarily
  change an already-correct system
```

Overall flow:

```text
Inventory identifies the VM
        ↓
Playbook selects the VM
        ↓
Play contains ordered tasks
        ↓
Tasks use modules
        ↓
Modules inspect/change the VM
        ↓
VM converges toward the desired state
```

The practical proof of idempotence is:

```text
First playbook run:
changed > 0

Second playbook run:
changed = 0
```

assuming nothing changed between runs.

---

# Command Reference

Inspect an inventory:

```bash
ansible-inventory -i inventory.ini --list
```

Test connectivity to a group:

```bash
ansible myhosts -m ping -i inventory.ini
```

Test connectivity using a specific SSH username:

```bash
ansible myhosts -m ping -i inventory.ini -u azureuser
```

Run a playbook:

```bash
ansible-playbook -i inventory.ini playbook.yaml
```


# Example Ansible Playbook


``` yaml

- name: Setup Tailscale  
  hosts: synth_vm  
  
  tasks:  
	- name: Install Tailscale
      ansible.builtin.shell: "curl -fsSL https://tailscale.com/install.sh | sh"  
  
     become: true  
      ansible.builtin.command: "tailscale up --auth-key={{ lookup('ansible.builtin.file', '~/secrets/synth_uptime_monitor_auth_key') }}"  
  
  
  
    - name: Grab Tailscale IPv4 address  
      ansible.builtin.command: tailscale ip --4  
      register: command_result  
      changed_when: false  
  
   
    - name: Hand off Tailscale IPv4 address  
      ansible.builtin.debug:  
        msg: "{{ command_result.stdout }}"
```