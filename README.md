# Rancher Agent Registration Tool

**rancher-agent-registration** is a command line tool for registering the current host with a Rancher server.

Rancher asks you to run the agent container on each host, giving you the command to run that looks a bit like this:

```
sudo docker run [snipped] rancher/agent:v0.11.0 https://rancher/v1/scripts/<registration-token>
```

For interactive deployments, thats fine.

But if you need to deploy a new host using something like Salt / Ansible / Chef / etc, then you cant know the registration token in advance, making it impossible.

Enter rancher-agent-registration. Run the tool on the host you want to register, and it will negotiate a new registration token with the Rancher API and then launch the rancher-agent container in Docker.

## Installation

```
pip install rancher-agent-registration
```

## Usage

Rancher supports two kind of API keys: environment and account. You can use either with this tool, but if your account key has access to more than one environment you'll need to pass the name of the environment to the --environment flag so that the host is registered in the right place.

You can run the tool interactivly and it will prompt you for the settings it needs, otherwise you must pass at least --url, --key and --secret on the command line.

If you want to test rancher-agent-registration, you can pass --echo and it will print the docker command to run to the console instead of running it.

You can specify labels for your rancher host by passing in `--label key=value` for each label.

## SaltStack example

rancher.sls:

```
rancher-agent-registration:
  pip.installed:
    - name: rancher-agent-registration

rancher-agent:
  cmd.run:
    - name: rancher-agent-registration --url http://rancher:8080 --key <api-key> --secret <api-secret>

remove-rancher-agent-registration:
  pip.removed:
    - name: rancher-agent-registration
```

## Help

```
$ rancher-agent-registration  --help
Usage: rancher-agent-registration [OPTIONS]

  Registers the current host with your Rancher server, creating the necessary
  registration keys.

Options:
  --url TEXT          The URL for your Rancher server, eg: http://rancher:8000
  --key TEXT          The environment or account API key
  --secret TEXT       The secret for the API key
  --environment TEXT  The name of the environment to add the host into (if you
                      have more than one)
  --echo              Print the docker run command to the console, instead of
                      running it
  --sudo              Use sudo for docker run ...
  --label TEXT        Apply a label to the host in Rancher in key=value format
                      (you can use --label more than once for multiple labels)
  --help              Show this message and exit.

```

## History

#### [1.0] - 2016-04-02
First release, works.

#### [1.1] - 2016-09-02
Added --label option to define host labels at registration, contributed by @mbrannigan

## License

MIT
