#!/usr/bin/env python

from plumbum import local, cli
from plumbum import commands
from sys import stdout
import os
import json

class Docker:
    """
    Interface to docker actions and high level administrative task such as deploying from the configuration file.
    """
    def __init__(self, config=None, verbose=False):
        self.verbose = verbose
        self.docker = local["docker"]
        self.container = Container(verbose)
        self.config = config

    def version(self):
        return self.docker("version")

    def deploy(self, name, shared_vars=[]):
        if self.config is None:
            raise StandardError("Configuration not initialized")

        if name in self.config:
            self.container.deploy(name, self.config[name], shared_vars)
        else:
            raise StandardError("%s not found in configuration" % name)

    def remove_untagged(self):
        untagged = 0
        removed = 0
        for line in self.docker("images").splitlines():
            repository = line[0:44].strip()
            tag = line[44:64].strip()
            image_id = line[64:84].strip()
            created = line[84:104].strip()
            virtual_size = line[104:].strip()

            untagged += 1
            if repository == "<none>" and tag == "<none>":
                self.print_to_stdout("Removing %s: " % image_id)
                if self.execute_docker_command("rm", image_id):
                    removed += 1

        print "Processed: %d, removed: %d, failed: %d" % (untagged, removed, untagged-removed)

    def remove_dangling(self):
        dangling = 0
        removed = 0
        for line in self.docker("images", "-q", "-f", "dangling=true").splitlines():
            dangling += 1
            image_id = line.strip()
            self.print_to_stdout("Removing %s: " % image_id)
            if self.execute_docker_command("rm", image_id):
                removed += 1

        print "Processed: %d, removed: %d, failed: %d" % (dangling, removed, dangling-removed)

    def execute_docker_command(self, *args):
        try:
            self.docker(args)
            self.print_to_stdout("Success.\n")
            return True
        except commands.processes.ProcessExecutionError, e:
            self.print_to_stdout("Failed (exit code=%s, message=%s).\n" % (e.retcode, e.stderr.rstrip()))
            return False

    def print_to_stdout(self, text):
        if self.verbose:
            stdout.write(text)
            stdout.flush()

class Image:
    """
    Interface to image actions
    """
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.docker = local["docker"]

    def build(self, image_name, dir):
        if self.verbose:
            print "    Building docker image: %s" % image_name
        self.docker(["build", "-t", image_name, dir])


class Container:
    """
    Interface to container actions
    """
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.docker = local["docker"]

    def deploy(self, name, config, shared_vars=[]):
        if not self.stop(name):
            return
        if not self.remove(name):
            return
        self.run(name, config, shared_vars)

    def run(self, name, config, shared_vars=[]):
        args = ["run", "--name", name]

        if "daemon" in config and config["daemon"]:
            args.append("-d")
        if "interactive" in config and config["interactive"]:
            args.append("-i")

        if "remove" in config and config["remove"]:
            args.append("--rm")
        if "memory" in config:
            args.append("-m")
            args.append(config["memory"])
        if "restart" in config:
            args.append("--restart")
            args.append(config["restart"])
        for var in shared_vars:
            args.append("-e")
            args.append(var)
        for var in config["environment_variables"]:
            args.append("-e")
            args.append(var)
        for port in config["port_mappings"]:
            args.append("-p")
            args.append(port)
        for volume in config["volume_mappings"]:
            args.append("-v")
            args.append(volume)
            if volume.startswith("/"):
                host_path = volume.split(":")[0]
                if not os.path.isdir(host_path):
                    self.print_to_stdout("Creating host directory [%s]\n" % host_path)
                    os.makedirs(host_path)
        args.append(config["image"])

        #self.print_to_stdout("Args: %s.\n" % args)
        self.print_to_stdout("Running container [%s]: " % name)

        return self.execute_docker_command(args)

    def stop(self, name):
        self.print_to_stdout("Stopping [%s]: " % name)

        if not self.is_running(name):
            self.print_to_stdout("Not running.\n")
            return True
        else:
            return self.execute_docker_command(["stop", name])

    def remove(self, name):
        self.print_to_stdout("Removing [%s]: " % name)

        if not self.does_exist(name):
            self.print_to_stdout("Doesn't exist.\n")
            return True

        return self.execute_docker_command(["rm", name])

    def execute_docker_command(self, args):
        try:
            self.docker.run(args)
            self.print_to_stdout("Success.\n")
            return True
        except commands.processes.ProcessExecutionError, e:
            self.print_to_stdout("Failed (exit code=%s, message=%s).\n" % (e.retcode, e.stderr.rstrip()))
            return False

    def inspect(self, name):
        try:
            data = self.docker("inspect", name)
            return json.loads(data)
        except:
            return None

    def is_running(self, name):
        json = self.inspect(name)
        if json is None:
            return False
        else:
            if "State" in json[0] and "Status" in json[0]["State"]:
                status = json[0]["State"]["Status"]
                return status == "running" or status == "restarting"
            else:
                return False

    def does_exist(self, name):
        json = self.inspect(name)
        if json is None:
            return False
        else:
            return True

    def print_to_stdout(self, text):
        if self.verbose:
            stdout.write(text)
            stdout.flush()


class App(cli.Application):
    PROGNAME = "docker.py"
    VERSION = "0.0.1"
    verbose = cli.Flag(["v", "verbose"], help="Verbose output")
    deployment_file = None
    config = None

    @cli.switch(["-d", "--deploy_file"], str, help="Specify a deployment file. Absolute path or relatice to the current working directory")
    def set_deployment_file(self, file):
        if file.startswith("/"):
            self.deployment_file = file
        else:
            self.deployment_file = os.path.join(os.getcwd(), file)

    def load_deployment_file(self):
        if self.deployment_file is None:
            raise StandardError("Deployment file is required")
        if not os.path.exists(self.deployment_file):
            raise StandardError("Deployment file [%s] not found" % self.deployment_file)

        with open(self.deployment_file) as json_data_file:
            self.config = json.load(json_data_file)

    #def main(self):
    #    print "Unused"


@App.subcommand("deploy")
class Deploy(cli.Application):
    """Docker deploy utilities"""

    container = None

    @cli.switch(["-c", "--container"], str, help="Specify which container to deploy, defaults to ALL")
    def set_container(self, container):
        self.container = container

    def main(self):
        self.parent.load_deployment_file()
        docker = Docker(config=self.parent.config, verbose=self.parent.verbose)

        shared_vars = []
        if "shared_environment_variables" in self.parent.config:
            shared_vars = self.parent.config["shared_environment_variables"]

        if self.container is not None:
            docker.deploy(self.container, shared_vars)
        else:
            for key in self.parent.config:
                if not key == "shared_environment_variables":
                    docker.deploy(key, shared_vars)


@App.subcommand("clean")
class Clean(cli.Application):
    """Docker cleanup utilities"""

    untagged = False
    dangling = False

    @cli.switch(["-u", "--untagged"], help="Remove untagged containers, defaults to false")
    def set_untagged(self):
        self.untagged = True

    @cli.switch(["-d", "--dangling"], help="Remove dangling containers, defaults to false")
    def set_dangling(self):
        self.dangling = True

    def main(self):
        docker = Docker(verbose=self.parent.verbose)
        if self.untagged:
            print "Cleaning untagged images"
            docker.remove_untagged()
        if self.dangling:
            print "Cleaning dangling images"
            docker.remove_dangling()


if __name__ == "__main__":
    App.run()
