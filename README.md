# Rancher GitLab Deployment Tool

**rancher-gitlab-deploy** is a tool for deploying containers built with GitLab CI onto your Rancher infrastructure.

It fits neatly into the `gitlab-ci.yml` workflow and requires minimal configuration. It will upgrade existing services as part of your CI workflow.

Both GitLab's built in Docker registry and external Docker registries are supported.

`rancher-gitlab-deploy` will pick as much of its configuration up as possible from environment variables set by the GitLab CI runner.

This tool is not suitable if your services are not already created in Rancher. It will upgrade existing services, but will not create new ones. If you need to create services you should use `rancher-compose` in your CI workflow, but that means storing any secret environment variables in your Git repo.

## Installation

I recommend you use the pre-built container:

https://hub.docker.com/r/cdrx/rancher-gitlab-deploy/

But you can install the command locally, with `pip`, if you prefer:

```
pip install rancher-gitlab-deploy
```

## Usage

You will need to create a set of API keys in Rancher and save them as secret variables in GitLab for your project.

Three secret variables are required:

`RANCHER_URL` (eg `https://rancher.example.com`)

`RANCHER_ACCESS_KEY`

`RANCHER_SECRET_KEY`

Rancher supports two kind of API keys: environment and account. You can use either with this tool, but if your account key has access to more than one environment you'll need to specify the name of the environment with the --environment flag. This is so that the tool can upgrade find the service in the right place. For example, in your `gitlab-ci.yml`:

```
deploy:
  stage: deploy
  image: cdrx/rancher-gitlab-deploy
  script:
    - upgrade --environment production
```

`rancher-gitlab-deploy` will use the GitLab group and project name as the stack and service name by default. For example, the project:

`http://gitlab.example.com/acme/webservice`

will upgrade the service called `webservice` in the stack called `acme`.

If the names of your services don't match your repos in GitLab 1:1, you can change the service that gets upgraded with the `--stack` and `--service` flags:

```
deploy:
  stage: deploy
  image: cdrx/rancher-gitlab-deploy
  script:
    - upgrade --stack acmeinc --service website
```

You can change the image (or :tag) used to deploy the upgraded containers with the `--new-image` option:

```
deploy:
  stage: deploy
  image: cdrx/rancher-gitlab-deploy
  script:
    - upgrade --new-image registry.example.com/acme/widget:1.2
```

You may use this with the `$CI_BUILD_TAG` environment variable that GitLab sets.

`rancher-gitlab-deploy`'s default upgrade strategy is to upgrade containers one at time, waiting 2s between each one. It will start new containers after shutting down existing ones, to avoid issues with multiple containers trying to bind to the same port on a host. It will wait for the upgrade to complete in Rancher, then mark it as finished. The upgrade strategy can be adjusted with the flags in `--help` (see below).

## GitLab CI Example

Complete gitlab-ci.yml:

```
image: docker:latest
services:
  - docker:dind

stages:
  - build
  - deploy

build:
  stage: build
  script:
    - docker login -u gitlab-ci-token -p $CI_BUILD_TOKEN registry.example.com
    - docker build -t registry.example.com/group/project .
    - docker push registry.example.com/group/project

deploy:
  stage: deploy
  image: cdrx/rancher-gitlab-deploy
  script:
    - upgrade
```

A more complex example:

```
deploy:
  stage: deploy
  image: cdrx/rancher-gitlab-deploy
  script:
    - upgrade --environment production --stack acme --service web --new-image alpine:3.4 --no-finish-upgrade
```

## Help

```
$ rancher-gitlab-deploy --help

Usage: rancher-gitlab-deploy [OPTIONS]

  Performs an in service upgrade of the service specified on the command
  line

Options:
  --rancher-url TEXT              The URL for your Rancher server, eg:
                                  http://rancher:8000  [required]
  --rancher-key TEXT              The environment or account API key
                                  [required]
  --rancher-secret TEXT           The secret for the access API key
                                  [required]
  --environment TEXT              The name of the environment to add the host
                                  into (only needed if you are using an
                                  account API key instead of an environment
                                  API key)
  --stack TEXT                    The name of the stack in Rancher (defaults
                                  to the name of the group in GitLab)
                                  [required]
  --sidekicks/--no-sidekicks      Upgrade service sidekicks at the same time?
                                  Defaults to not upgrading sidekicks
  --new-sidekick-image NAME IMAGE If specified, replace the named sidekick image
                                  (and :tag) with this one during the upgrade.
                                  This flag can be used more than once.
  --service TEXT                  The name of the service in Rancher to
                                  upgrade (defaults to the name of the service
                                  in GitLab)  [required]
  --start-before-stopping / --no-start-before-stopping
                                  Should Rancher start new containers before
                                  stopping the old ones?
  --batch-size INTEGER            Number of containers to upgrade at once
  --batch-interval INTEGER        Number of seconds to wait between upgrade
                                  batches
  --upgrade-timeout INTEGER       How long to wait, in seconds, for the
                                  upgrade to finish before exiting. To skip
                                  the wait, pass the --no-wait-for-upgrade-to-
                                  finish option.
  --wait-for-upgrade-to-finish / --no-wait-for-upgrade-to-finish
                                  Wait for Rancher to finish the upgrade
                                  before this tool exits
  --new-image TEXT                If specified, replace the image (and :tag)
                                  with this one during the upgrade
  --finish-upgrade / --no-finish-upgrade
                                  Mark the upgrade as finished after it
                                  completes
  --ssl-verify / --no-ssl-verify  Whether we should skip certificate checks
                                  or not when connecting to the Rancher API.
                                  Default behaviour is to check cert validity.
  --create / --no-create          Will create the Rancher stack
                                  and service, if they are missed
                                  (needs --new-image option)
  --labels                        Will add Rancher labels to the service being
                                  created by passing a comma separated list.
  --variables                     Will add environment variables to the service being
                                  created by passing a comma separated list.
  --help                          Show this message and exit.

```

## History

#### [1.5] - 2017-11-25
Fixed UnicodeError bug with authentication, thank you to @evilmind for the fix

#### [1.4] - 2017-07-18
Fixed some bug to do with error and sidekick handling and made `--no-start-before-stopping` the default behaviour

#### [1.3] - 2017-03-16
Added the --new-sidekick-image flag to change sidekick images while upgrading, thank you @kariae for the PR

#### [1.2] - 2017-01-03
Added the --sidekicks flag to upgrade sidekicks at the same time, thank you @kiesiu for the PR

#### [1.1] - 2016-09-29
Fixed a bug that caused a crash when using --environment, thank you @mvriel for the PR

#### [1.0] - 2016-09-14
First release, works.

## License

MIT
