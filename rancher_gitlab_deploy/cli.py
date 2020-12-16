#!/usr/bin/env python
import logging
import sys
import time

import click
import requests
from requests import HTTPError

try:
    from httplib import HTTPConnection  # py2
except ImportError:
    from http.client import HTTPConnection  # py3


@click.command()
@click.option(
    "--rancher-url",
    envvar="RANCHER_URL",
    required=True,
    help="The URL for your Rancher server, eg: http://rancher:8000",
)
@click.option(
    "--rancher-key",
    envvar="RANCHER_ACCESS_KEY",
    required=True,
    help="The environment or account API key",
)
@click.option(
    "--rancher-secret",
    envvar="RANCHER_SECRET_KEY",
    required=True,
    help="The secret for the access API key",
)
@click.option(
    "--rancher-label-separator",
    envvar="RANCHER_LABEL_SEPARATOR",
    required=False,
    default=",",
    help="Where the default separator (',') could cause issues",
)
@click.option(
    "--environment",
    default=None,
    help="The name of the environment to add the host into "
    + "(only needed if you are using an account API key instead of an environment API key)",
)
@click.option(
    "--stack",
    envvar="CI_PROJECT_NAMESPACE",
    default=None,
    required=True,
    help="The name of the stack in Rancher (defaults to the name of the group in GitLab)",
)
@click.option(
    "--service",
    envvar="CI_PROJECT_NAME",
    default=None,
    required=True,
    help="The name of the service in Rancher to upgrade (defaults to the name of the service in GitLab)",
)
@click.option(
    "--start-before-stopping/--no-start-before-stopping",
    default=False,
    help="Should Rancher start new containers before stopping the old ones?",
)
@click.option(
    "--batch-size",
    default=1,
    help="Number of containers to upgrade at once",
)
@click.option(
    "--batch-interval",
    default=2,
    help="Number of seconds to wait between upgrade batches",
)
@click.option(
    "--upgrade-timeout",
    default=5 * 60,
    help="How long to wait, in seconds, for the upgrade to finish before exiting. To skip the wait, pass the --no-wait-for-upgrade-to-finish option.",
)
@click.option(
    "--wait-for-upgrade-to-finish/--no-wait-for-upgrade-to-finish",
    default=True,
    help="Wait for Rancher to finish the upgrade before this tool exits",
)
@click.option(
    "--rollback-on-error/--no-rollback-on-error",
    default=False,
    help="Rollback the upgrade if an error occured. The rollback will be performed only if the option --wait-for-upgrade-to-finish is passed",
)
@click.option(
    "--new-image",
    default=None,
    help="If specified, replace the image (and :tag) with this one during the upgrade",
)
@click.option(
    "--finish-upgrade/--no-finish-upgrade",
    default=True,
    help="Mark the upgrade as finished after it completes",
)
@click.option(
    "--sidekicks/--no-sidekicks",
    default=False,
    help="Upgrade service sidekicks at the same time",
)
@click.option(
    "--new-sidekick-image",
    default=None,
    multiple=True,
    help="If specified, replace the sidekick image (and :tag) with this one during the upgrade",
    type=(str, str),
)
@click.option(
    "--create/--no-create",
    default=False,
    help="If specified, create Rancher stack and service if they don't exist",
)
@click.option(
    "--labels",
    default=None,
    help="If specified, add a comma separated list of key=values to add to the service",
)
@click.option(
    "--label",
    default=None,
    multiple=True,
    help="If specified, add a Rancher label to the service",
    type=(str, str),
)
@click.option(
    "--variables",
    default=None,
    help="If specified, add a comma separated list of key=values to add to the service",
)
@click.option(
    "--variable",
    default=None,
    multiple=True,
    help="If specified, add a environment variable to the service",
    type=(str, str),
)
@click.option(
    "--service-links",
    default=None,
    help="If specified, add a comma separated list of key=values to add to the service",
)
@click.option(
    "--service-link",
    default=None,
    multiple=True,
    help="If specified, add a service link to the service",
    type=(str, str),
)
@click.option(
    "--host-id",
    default=None,
    help="If specified, service will be deployed on requested host",
)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable HTTP Debugging",
)
@click.option(
    "--ssl-verify/--no-ssl-verify",
    default=True,
    help="Disable certificate checks. Use this to allow connecting to a HTTPS Rancher server using an self-signed certificate",
)
@click.option(
    "--secrets",
    default=None,
    help="If specified, add a comma separated list of secrets to the service",
)
@click.option(
    "--secret",
    default=None,
    multiple=True,
    help="If specified add a secret to the service",
)
def main(
    rancher_url,
    rancher_key,
    rancher_secret,
    rancher_label_separator,
    environment,
    stack,
    service,
    new_image,
    batch_size,
    batch_interval,
    start_before_stopping,
    upgrade_timeout,
    wait_for_upgrade_to_finish,
    rollback_on_error,
    finish_upgrade,
    sidekicks,
    new_sidekick_image,
    create,
    labels,
    label,
    variables,
    variable,
    service_links,
    service_link,
    host_id,
    debug,
    ssl_verify,
    secrets,
    secret,
):
    """Performs an in service upgrade of the service specified on the command line"""
    if debug:
        debug_requests_on()

    # split url to protocol and host
    if "://" not in rancher_url:
        bail("The Rancher URL doesn't look right")

    proto, host = rancher_url.split("://")
    api = "%s://%s/v1" % (proto, host)
    apiv2 = "%s://%s/v2-beta" % (proto, host)

    stack = stack.replace(".", "-")
    service = service.replace(".", "-")

    session = requests.Session()

    # Set verify based on --ssl-verify/--no-ssl-verify option
    session.verify = ssl_verify

    # 0 -> Authenticate all future requests
    session.auth = (rancher_key, rancher_secret)

    # Check for labels and environment variables to set
    defined_labels = {}

    if labels is not None:
        labels_as_array = labels.split(rancher_label_separator)

        for label_item in labels_as_array:
            key, value = label_item.split("=", 1)
            defined_labels[key] = value

    if label:
        for item in label:
            key = item[0]
            value = item[1]
            defined_labels[key] = value

    defined_environment_variables = {}

    if variables is not None:
        variables_as_array = variables.split(",")

        for variable_item in variables_as_array:
            key, value = variable_item.split("=", 1)
            defined_environment_variables[key] = value

    if variable:
        for item in variable:
            key = item[0]
            value = item[1]
            defined_environment_variables[key] = value

    defined_secrets = []

    if secrets is not None:
        secrets_as_array = secrets.split(",")

        for secret_item in secrets_as_array:
            key, value = secret_item.split("=", 1)
            defined_secrets.append({"type": "secretReference", "name": key})

    if secret:
        for item in secret:
            defined_secrets.append({"type": "secretReference", "name": item})

    # 1 -> Find the environment id in Rancher
    try:
        r = session.get("%s/projects?limit=1000" % api)
        r.raise_for_status()
    except HTTPError:
        bail("Unable to connect to Rancher at %s - is the URL and API key right?" % host)
    else:
        environments = r.json()["data"]

    environment_id = None
    if environment is None:
        environment_id = environments[0]["id"]
        environment_name = environments[0]["name"]
    else:
        for e in environments:
            if e["id"].lower() == environment.lower() or e["name"].lower() == environment.lower():
                environment_id = e["id"]
                environment_name = e["name"]

    if not environment_id:
        if environment:
            bail(
                "The '%s' environment doesn't exist in Rancher, or your API credentials don't have access to it"
                % environment
            )
        else:
            bail("No environment in Rancher matches your request")

    # map secrets to id (checking if passed secrets are defined in the environment)
    for def_secret in defined_secrets:
        # try to retrieve secret by name
        try:
            r = session.get("%s/projects/%s/secrets?name=%s" % (apiv2, environment_id, def_secret["name"]))
            r.raise_for_status()
        except HTTPError:
            bail(
                "Unable to connect to Rancher at %s to secret id for %s - are the URL and API key right? does %s exist ?"
                % host,
                def_secret["name"],
                def_secret["name"],
            )
        else:
            result = r.json()["data"]
            if debug:
                msg("secret query result: %s" % result)
            if len(result) > 0:
                def_secret["secretId"] = result[0]["id"]
            else:
                bail("Cannot find secret %s in environment %s ?!" % (def_secret["name"], environment_id))

    # 2 -> Find the stack in the environment

    try:
        r = session.get("%s/projects/%s/environments?limit=1000" % (api, environment_id))
        r.raise_for_status()
    except HTTPError:
        bail("Unable to fetch a list of stacks in the environment '%s'" % environment_name)
    else:
        stacks = r.json()["data"]

    for s in stacks:
        if s["name"].lower() == stack.lower():
            stack = s
            break
    else:
        if create:
            new_stack = {"name": stack.lower()}
            try:
                msg("Creating stack %s in environment %s..." % (new_stack["name"], environment_name))
                r = session.post("%s/projects/%s/environments" % (api, environment_id), json=new_stack)
                r.raise_for_status()
                stack = r.json()
            except HTTPError:
                bail("Unable to create missing stack")
        else:
            bail("Unable to find a stack called '%s'. Does it exist in the '%s' environment?" % (stack, environment_name))

    # 3 -> Find the service in the stack

    try:
        r = session.get("%s/projects/%s/environments/%s/services?limit=1000" % (api, environment_id, stack["id"]))
        r.raise_for_status()
    except HTTPError:
        bail("Unable to fetch a list of services in the stack. Does your API key have the right permissions?")
    else:
        services = r.json()["data"]

    for s in services:
        if s["name"].lower() == service.lower():
            service = s
            break
    else:

        if create:
            new_service = {
                "name": service.lower(),
                "stackId": stack["id"],
                "startOnCreate": True,
                "launchConfig": {
                    "imageUuid": ("docker:%s" % new_image),
                    "labels": defined_labels,
                    "environment": defined_environment_variables,
                    "secrets": defined_secrets,
                },
            }

            if host_id is not None:
                msg("Scheduled host %s" % host_id)
                new_service["launchConfig"]["requestedHostId"] = host_id

            try:
                msg(
                    "Creating service %s in environment %s with image %s..."
                    % (new_service["name"], environment_name, new_image)
                )
                r = session.post("%s/projects/%s/services" % (apiv2, environment_id), json=new_service)
                r.raise_for_status()
                service = r.json()

                defined_service_links = []

                if service_links is not None:
                    service_links_as_array = service_links.split(",")

                    for service_link_item in service_links_as_array:
                        name, reference = service_link_item.split("=", 1)
                        serviceId = None

                        for s in services:
                            if s["name"].lower() == reference.lower():
                                serviceId = s["id"]
                                break

                        if serviceId:
                            defined_service_links.append({"name": name, "serviceId": serviceId})

                if service_link:
                    for name, reference in service_link:
                        serviceId = None

                        for s in services:
                            if s["name"].lower() == reference.lower():
                                serviceId = s["id"]
                                break

                        if serviceId:
                            defined_service_links.append({"name": name, "serviceId": serviceId})

                if defined_service_links:
                    msg(
                        "Setting service links for service %s in environment %s with image %s..."
                        % (new_service["name"], environment_name, new_image)
                    )
                    r = session.post(service["actions"]["setservicelinks"], json={"serviceLinks": defined_service_links})
                    r.raise_for_status()
                    service = r.json()
                    msg("Service links set")

                msg("Creation finished")
                sys.exit(0)
            except HTTPError:
                bail("Unable to create missing service")
        else:
            bail("Unable to find a service called '%s', does it exist in Rancher?" % service)

    # 4 -> Is the service elligible for upgrade?

    if service["state"] == "upgraded":
        warn(
            "The current service state is 'upgraded', marking the previous upgrade as finished before starting a new upgrade..."
        )

        try:
            r = session.post("%s/projects/%s/services/%s/?action=finishupgrade" % (api, environment_id, service["id"]))
            r.raise_for_status()
        except HTTPError:
            bail("Unable to finish the previous upgrade in Rancher")

        attempts = 0
        while service["state"] != "active":
            time.sleep(2)
            attempts += 2
            if attempts > upgrade_timeout:
                bail("A timeout occured while waiting for Rancher to finish the previous upgrade")
            try:
                r = session.get("%s/projects/%s/services/%s" % (api, environment_id, service["id"]))
                r.raise_for_status()
            except HTTPError:
                bail("Unable to request the service status from the Rancher API")
            else:
                service = r.json()

    if service["state"] != "active":
        bail("Unable to start upgrade: current service state '%s', but it needs to be 'active'" % service["state"])

    msg("Upgrading %s/%s in environment %s..." % (stack["name"], service["name"], environment_name))

    upgrade = {
        "inServiceStrategy": {
            "batchSize": batch_size,
            "intervalMillis": batch_interval * 1000,  # rancher expects miliseconds
            "startFirst": start_before_stopping,
            "launchConfig": {},
            "secondaryLaunchConfigs": [],
        }
    }
    # copy over the existing config
    upgrade["inServiceStrategy"]["launchConfig"] = service["launchConfig"]

    if defined_labels:
        upgrade["inServiceStrategy"]["launchConfig"]["labels"] = defined_labels

    if defined_environment_variables:
        upgrade["inServiceStrategy"]["launchConfig"]["environment"] = defined_environment_variables

    # new_sidekick_image parameter needs secondaryLaunchConfigs loaded
    if sidekicks or new_sidekick_image:
        # copy over existing sidekicks config
        upgrade["inServiceStrategy"]["secondaryLaunchConfigs"] = service["secondaryLaunchConfigs"]

    if new_image:
        # place new image into config
        upgrade["inServiceStrategy"]["launchConfig"]["imageUuid"] = "docker:%s" % new_image

    if new_sidekick_image:
        new_sidekick_image = dict(new_sidekick_image)

        for idx, secondaryLaunchConfigs in enumerate(service["secondaryLaunchConfigs"]):
            if secondaryLaunchConfigs["name"] in new_sidekick_image:
                upgrade["inServiceStrategy"]["secondaryLaunchConfigs"][idx]["imageUuid"] = (
                    "docker:%s" % new_sidekick_image[secondaryLaunchConfigs["name"]]
                )

    # 5 -> Start the upgrade

    try:
        r = session.post("%s/projects/%s/services/%s/?action=upgrade" % (api, environment_id, service["id"]), json=upgrade)
        r.raise_for_status()
    except HTTPError:
        bail("Unable to request an upgrade on Rancher")

    # 6 -> Wait for the upgrade to finish

    if not wait_for_upgrade_to_finish:
        msg("Upgrade started")
    else:
        msg("Upgrade started, waiting for upgrade to complete...")
        attempts = 0
        while service["state"] != "upgraded":
            time.sleep(2)
            attempts += 2
            if attempts > upgrade_timeout:
                message = "A timeout occured while waiting for Rancher to complete the upgrade"
                if rollback_on_error:
                    bail(message, exit=False)
                    warn("Processing image rollback...")

                    try:
                        r = session.post(
                            "%s/projects/%s/services/%s/?action=rollback" % (api, environment_id, service["id"])
                        )
                        r.raise_for_status()
                    except HTTPError:
                        bail("Unable to request a rollback on Rancher")

                    attempts = 0
                    while service["state"] != "active":
                        time.sleep(2)
                        attempts += 2
                        if attempts > upgrade_timeout:
                            bail(
                                "A timeout occured while waiting for Rancher to rollback the upgrade to its latest running state"
                            )
                        try:
                            r = session.get("%s/projects/%s/services/%s" % (api, environment_id, service["id"]))
                            r.raise_for_status()
                        except HTTPError:
                            bail("Unable to request the service status from the Rancher API")
                        else:
                            service = r.json()

                    warn("Service sucessfully rolled back")
                    sys.exit(1)
                else:
                    bail(message)
            try:
                r = session.get("%s/projects/%s/services/%s" % (api, environment_id, service["id"]))
                r.raise_for_status()
            except HTTPError:
                bail("Unable to fetch the service status from the Rancher API")
            else:
                service = r.json()

        if not finish_upgrade:
            msg("Service upgraded")
            sys.exit(0)
        else:
            msg("Finishing upgrade...")
            try:
                r = session.post("%s/projects/%s/services/%s/?action=finishupgrade" % (api, environment_id, service["id"]))
                r.raise_for_status()
            except HTTPError:
                bail("Unable to finish the upgrade in Rancher")

            attempts = 0
            while service["state"] != "active":
                time.sleep(2)
                attempts += 2
                if attempts > upgrade_timeout:
                    bail("A timeout occured while waiting for Rancher to finish the previous upgrade")
                try:
                    r = session.get("%s/projects/%s/services/%s" % (api, environment_id, service["id"]))
                    r.raise_for_status()
                except HTTPError:
                    bail("Unable to request the service status from the Rancher API")
                else:
                    service = r.json()

            msg("Upgrade finished")

    sys.exit(0)


def msg(message):
    click.echo(click.style(message, fg="green"))


def warn(message):
    click.echo(click.style(message, fg="yellow"))


def bail(message, exit=True):
    click.echo(click.style("Error: " + message, fg="red"))
    if exit:
        sys.exit(1)


def debug_requests_on():
    """Switches on logging of the requests module."""
    HTTPConnection.debuglevel = 1

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True
