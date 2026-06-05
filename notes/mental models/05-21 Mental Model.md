📐 MENTAL MODEL — Docker 
A [[container]] is not a lightweight VM: it is a normal process isolated with Linux namespaces and cgroups, sharing the host kernel rather than emulating hardware. An image is a layered filesystem template, and Docker caches layers — a changed line invalidates every layer after it, which is why `requirements.txt` is copied and installed _before_ the application code. Without containers, "works on my machine" diverges from the server over glibc, Python, and OS differences. It hides the build/layer/registry machinery behind a Dockerfile. Real alternatives: Podman, full VMs, Nix.



## The Mental Model At a High Level

- Containers are *not* mini-computers. They are processes with extra restrictions. 
	- Understanding this distinction can help you reason about what
		- containers can and cannot do, and
		- why they can break in ways a virtual machine wouldn't




## What is a Virtual Machine?


A [[virtual machine]] is a full emulation of physical hardware. We run hypervisor (VMware, VirtualBox, Hyper-V) that pretends to be physical hardware.
- Fake CPU
- Fake Ram
- Fake disc
Within this  virtual machine  a full guest OS boots, this includes its own kernel. From the guest OS's perspective, its thinking its running on physical hardware. 

Virtual  machines are heavy. Booting one can take some time. since an entire OS has to startup too. Every VM brings with it Gigabytes of its own OS files. 


## What is a Container?

a container is just a regular Linux process, but the [[Operating System|OS]] has been told to hide most of the system from it. This process can't see other processes, can't see the full [[Filesystem|filesystem]] but it does have its own network stack. But there is no:
- fake hardware
- separate kernel
- boot sequence

Its the same [[Kernel|kernel]] the host is using. The process is just isolated from seeing the rest of the machine.

Containers start very quickly. Since there is no real boot sequence. 



## What are namespaces?

Namespaces control *what a process can see*. There are namespaces for:
- PIDs (the [[Container]] sees only its own processes, not the host's)
- the [[Filesystem|filesystem]] (the container has its own `/` root)
- the network (its own network interfaces, IP address)
- hostnames, users, and more

when [[Docker]] starts a container, it creates a new set of namespaces and starts your process inside them. The process can't see beyond those namespaces


## What are cgroups?
**cgroups** (control groups) control *what a process can consume*.
- CPU time
- RAM
- disk I/O
if you set a container to use at most 512MB of RAM, cgroups enforces that limit at the kernel level. 

Without cgroups a single container could starve other processes on the machine. 


## What is a kernel?


The core of an [[Operating System]], the piece of software that sits between our programs and the physical hardware. When python code reads a file or opens a network socket, it doesn't touch the disc or network card directly. Instead it makes a system call to the kernel, which handles the actual physical hardware interaction

Linux, macOS, and Windows all have different kernels. [[Docker]] [[Container|containers]] are Linux only at the kernel level. So when we are running docker on mac or windows we are also actually running a small [[Virtual Machine]] underneath, giving the container the Linux kernel it needs.



## What is an Image?


An image is a read-only snapshot of a [[Filesystem|filesystem]]. It contains everything an application needs to run. the [[Operating System|OS]] files, python interpreter, our installed packages, our source code. Its pretty much a template.

When we run a [[Container]] docker takes that image and adds a thin writable layer on top of it. The container writes to that layer. The image underneath never changes. This means we can have ten containers all running from the same image simultaneously. 
- each gets their own writable layer, but share a single read-only base.

a [[Dockerfile]] is the recipe for building an image. 

`docker build` executes the recipe (`dockerfile`) and produces the image 


## What is Docker?

Docker is a tool that lets us package an application and everything it needs to run together. The [[Operating System|OS]], runtime, libraries, dependencies, config all together into a single portable unit called a [[Container|container]]. We can then run the container on any machine that has docker installed and it behaves identically, regardless of how the host machine is actually working 

Before Docker we had to install Python, install the packages we needed, setup all the environmental variables, and hope the server matched host machines setup. Docker lets us remove this issue and lets us standardize. 



## What is a Dockerfile?

A dockerfile is the recipe for building a [[Docker]] [[Image]]. Its a plain text file containing a sequence of instructions that will tell Docker how to construct our image layer by layer.

A simple example

```dockerfile
FROM python:3.12-slim                        # start from an existing base image
COPY requirements.txt .                          # copy our dependencies file in
RUN  pip install -r requirements.txt                 # install them
Copy . .                                             # copy our source code in
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"] # default start command
```

Each instruction becomes a layer. When we run `docker build`, docker executes each instruction top to bottom and produces an image. That image is what we use to then run as our [[Container|container]].

Dockerfiles will live in our repository alongside our code, this makes sure that our environment is version-controlled just like everything else. 

## What does "Docker Caches Layers" mean?


Dockerfiles are sequences of instructions. Each instruction produces a layer, or a "diff" of what changed in the filesystem. Docker stores each separately and reuses them across builds. 

The rule
- if a layer's instructions and its inputs haven't changed, docker reuses the cached layer and skips re-running it. But if a layer changes, every layer ***after*** it gets invalidated and rebuilt from scratch, since each layer is built on top of each other.

This is why ordering matters in a Dockerfile 

```dockerfile
COPY requirements.txt
RUN pip install -r requirements.txt # expensive approx, 30s
COPY ..                             # our source code 
```

If we change our source code only the last layer is invalid. The pip install layer is reused from the cache. But if we put `COPY . .` first and then `pip install`, changing any source file would invalidate the pip install layer, and we'd wait 30 seconds on every rebuild




## What is glibc?

the GNU C Library. The standard library that almost every Linux program depends on for basic operations. Such as 
- Memory allocation
- String handling
- File I/O
- Sending System calls to the [[Kernel]]

It acts as the bridge between C code (and Python code since its written in C) and the Linux

Why is it relevant to [[Docker]]? Different Linux distributions ship with different versions / releases of glibc. A python package compiled against glibc 2.31 on Ubuntu might not run on a system with glibc 2.17. This is what leads to the "Runs on my machine" problem. Our machine has Ubuntu with one glibc version, while the server runs CentOS with an older one. Which could lead to things breaking in weird ways at runtime


[[Container|containers]] solve this by bundling an [[Operating System|OS]] [[Filesystem]] (including the right glibc version) inside of the image. The container always runs against the glibc it was built with, regardless of what version the host OS is using
