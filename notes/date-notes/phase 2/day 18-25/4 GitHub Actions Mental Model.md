5 "levels" of CI/CD
```
1. Source control         -> everyone commits to a shared repo
2. Continuous Integration -> every commit triggers an automatic build
3. Continuous Testing     -> every build automatically runs the test suite
4. Continuous Delivery    -> every passing build is automatically staged
                             and release-ready; human approves promotion to prod
5. Continuous Deployment  -> every passing build goes to prod automatically,
                             no human gate
```


# GitHub Actions

## What is GitHub Actions?

GitHub Actions is a platform for **continuous integration and continuous delivery**.

It allows us to automate tasks such as:
- building software
- running tests
- performing code quality checks
- creating artifacts
- deploying applications

For example, a workflow could automatically run tests whenever a pull request is opened, or deploy an application after changes are merged into the main branch.

GitHub Actions can run workflows on:
- **GitHub-hosted runners**, which are temporary virtual machines provided by GitHub
- **self-hosted runners**, which are machines that we manage ourselves

A GitHub Actions workflow is usually triggered when an **event** occurs in a repository.

A workflow contains one or more **jobs**, and each job contains one or more **steps**.

Conceptually:

```text
Event
  ↓
Workflow
  ↓
Jobs
  ↓
Steps
```

---

## Workflows

A **workflow** is an automated process defined in a YAML file within the repository.

Workflow files are normally stored under:

```text
.github/workflows/
```

A workflow can contain one or more jobs.

Workflows can be triggered by:

- repository events
    
- manual execution
    
- scheduled times
    
- other supported triggers
    

For example:

```text
push
   ↓
workflow starts
   ↓
tests run
```

---

## Events

An **event** is an activity that can cause a workflow to run.

Examples include:

- a commit being pushed
    
- a pull request being opened or updated
    
- an issue being created
    
- a release being published
    

Workflows can also be started manually or on a schedule.

The event answers the question:

> What caused this workflow to start?

---

## Jobs

A **job** is a collection of steps that execute on the same runner.

For example:

```text
Test Job
├── checkout repository
├── install dependencies
└── run tests
```

Each job gets its own execution environment.

Jobs are independent by default, so multiple jobs can run in parallel.

For example:

```text
Workflow
├── Test Job
├── Lint Job
└── Build Job
```

These jobs may run simultaneously.

A job can also depend on another job.

For example:

```text
Test
  ↓
Build
  ↓
Deploy
```

In this case, later jobs will not run until their dependencies have completed successfully.

---

## Steps

A **step** is an individual operation inside a job.

Steps run sequentially within that job.

A step can either:

- execute a shell command or script
    
- use an existing Action
    

For example:

```text
Job
├── Step 1: checkout repository
├── Step 2: set up Python
├── Step 3: install dependencies
└── Step 4: run tests
```

Because the steps belong to the same job, they execute on the same runner and can use files created by earlier steps.

---

## Actions

An **Action** is a reusable task that can be used as a step inside a job.

Actions reduce the amount of repetitive workflow configuration we need to write.

Common actions can perform tasks such as:

- checking out the repository
    
- configuring a programming language
    
- authenticating with a cloud provider
    
- uploading build artifacts
    

Conceptually:

```text
Job
├── reusable Action
├── reusable Action
└── custom shell command
```

Actions can be created by GitHub, third parties, or ourselves.

---

## Runners

A **runner** is the machine that executes a job.

There are two main types.

### GitHub-hosted runners

GitHub provides temporary virtual machines for workflow jobs.

For example:

```text
GitHub
   ↓
temporary Linux VM
   ↓
job executes
```

The runner exists for the duration of the job and is discarded afterward.

This provides a relatively clean environment for every run.

### Self-hosted runners

A self-hosted runner is a machine that we manage ourselves.

This could be:

- a physical server
    
- a personal computer
    
- a virtual machine
    
- a cloud server
    

GitHub sends jobs to the runner, but we are responsible for maintaining the machine and the software installed on it.

---

## Service Containers

A **service container** is a temporary Docker container that provides a supporting service required by a job.

Common examples include:

- PostgreSQL
    
- Redis
    
- MySQL
    
- message queues
    

Conceptually:

```text
Runner
│
├── Job
│    └── Tests
│
├── PostgreSQL container
└── Redis container
```

The service containers run using the runner's CPU and memory.

GitHub manages their lifecycle for the job:

```text
job starts
   ↓
service containers start
   ↓
steps execute
   ↓
job finishes
   ↓
service containers are removed
```

# Overall Mental Model

A simple CI workflow might look conceptually like:

```text
push or pull request
        ↓
workflow starts
        ↓
test job gets a runner
        ↓
repository is checked out
        ↓
dependencies are prepared
        ↓
supporting services are started
        ↓
tests run
        ↓
job passes or fails
```

The important distinction is:

```text
Workflow = entire automated process
Job      = group of steps running on one runner
Step     = individual operation inside a job
Action   = reusable task used by a step
Runner   = machine executing a job
Event    = trigger that starts the workflow
```





# Our workflow file


we want to first grab the repository

then setup the runner (is it already setup???)
- run the requirement.txt file

need it to setup the .env file too so where will that be grabbed from? 

then have it run docker compose network

then have it run pytest which will override the .env file contents with .env.locals (this is handled automatically when pytest runs)



