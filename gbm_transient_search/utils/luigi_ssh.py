import subprocess
import os
import logging
import time
import random
import numpy as np
import luigi.format
from luigi.contrib.ssh import RemoteCalledProcessError
from luigi.contrib.ssh import RemoteContext as LuigiRemoteContext
from luigi.contrib.ssh import RemoteFileSystem as LuigiRemoteFileSystem
from luigi.contrib.ssh import RemoteTarget as LuigiRemoteTarget
from luigi.target import FileSystemTarget
from gbm_transient_search.utils.configuration import gbm_transient_search_config

socket_base_path = gbm_transient_search_config["ssh"].get(
    "master_socket_base_path", None
)
nr_sockets = gbm_transient_search_config["ssh"].get("nr_sockets", 1)
max_connections = gbm_transient_search_config["ssh"]["connection_limit_per_socket"]

sleep_min = gbm_transient_search_config["ssh"].get("sleep_min", 0)
sleep_max = gbm_transient_search_config["ssh"].get("sleep_max", 0)


class RemoteContext(LuigiRemoteContext):
    @property
    def master_socket_paths(self):
        sockets = []

        host_name = self._host_ref()
        for i in range(nr_sockets):
            socket_path = os.path.join(socket_base_path, f"{host_name}_{i+1}:22")

            if os.path.exists(socket_path):
                sockets.append(socket_path)

            else:
                logging.error(
                    f"The master socket path is not existing at {socket_path}."
                    f"It has the be created manually."
                )
        if len(sockets) < 1:
            raise RuntimeError(
                f"The {host_name} has no open socket! You have to create them manually."
            )

        return sockets

    def check_nr_of_channels(self, master_socket):
        output = subprocess.check_output(
            f"lsof -U | grep {master_socket.replace(':22', '')} | wc -l", shell=True
        ).decode()
        nr_channels = int(output.strip(" \n"))
        return nr_channels

    def get_free_socket(self):
        open_connections = np.array(
            [self.check_nr_of_channels(socket) for socket in self.master_socket_paths]
        )

        free_connections = max_connections - open_connections

        logging.debug(f"SSH sockets: {zip(self.master_socket_paths, open_connections)}")

        if len(np.where(free_connections > 0)[0]) < 1:
            raise RuntimeError("No master socket available with free connections.")

        # Assign each socket a probability proportional to its free connections
        lh = free_connections / max_connections
        probs = lh / sum(lh)

        # Sample from list of master sockets
        socket = np.random.choice(self.master_socket_paths, p=probs)

        return socket

    def _prepare_cmd(self, cmd):
        connection_cmd = ["ssh", self._host_ref()]

        # Sleep for a random time to avoid overloading the master sockets
        time.sleep(random.randint(sleep_min, sleep_max))

        # Add custom master connection socket
        if socket_base_path is not None:
            connection_cmd += ["-S", self.get_free_socket()]
        else:
            connection_cmd += ["-o", "ControlMaster=no"]

        if self.sshpass:
            connection_cmd = ["sshpass", "-e"] + connection_cmd
        else:
            connection_cmd += ["-o", "BatchMode=yes"]  # no password prompts etc
        if self.port:
            connection_cmd.extend(["-p", self.port])

        if self.connect_timeout is not None:
            connection_cmd += ["-o", "ConnectTimeout=%d" % self.connect_timeout]

        if self.no_host_key_check:
            connection_cmd += [
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                "StrictHostKeyChecking=no",
            ]

        if self.key_file:
            connection_cmd.extend(["-i", self.key_file])

        if self.tty:
            connection_cmd.append("-t")
        return connection_cmd + cmd

    def check_output(self, cmd):
        p = self.Popen(cmd, stdout=subprocess.PIPE)

        output, _ = p.communicate()

        if p.returncode != 0:
            raise RemoteCalledProcessError(p.returncode, cmd, self.host, output=output)

        try:
            p.terminate()
        except Exception as e:
            print(e)

        _ = super().check_output(["exit"])

        return output


class RemoteFileSystem(LuigiRemoteFileSystem):
    def __init__(self, host, **kwargs):
        self.remote_context = RemoteContext(host, **kwargs)

    def _scp(self, src, dest):
        cmd = ["scp", "-q", "-C"]

        # Add custom master connection socket
        if socket_base_path is not None:
            cmd += ["-o", f"ControlPath={self.remote_context.get_free_socket()}"]
        else:
            cmd += ["-o", "ControlMaster=no"]

        if self.remote_context.sshpass:
            cmd = ["sshpass", "-e"] + cmd
        else:
            cmd.append("-B")
        if self.remote_context.no_host_key_check:
            cmd.extend(
                ["-o", "UserKnownHostsFile=/dev/null", "-o", "StrictHostKeyChecking=no"]
            )
        if self.remote_context.key_file:
            cmd.extend(["-i", self.remote_context.key_file])
        if self.remote_context.port:
            cmd.extend(["-P", self.remote_context.port])
        if os.path.isdir(src):
            cmd.extend(["-r"])
        cmd.extend([src, dest])
        p = subprocess.Popen(cmd)
        output, _ = p.communicate()
        if p.returncode != 0:
            raise subprocess.CalledProcessError(p.returncode, cmd, output=output)


class RemoteTarget(LuigiRemoteTarget):
    """
    Target used for reading from remote files.

    The target is implemented using ssh commands streaming data over the network.
    """

    def __init__(self, path, host, format=None, **kwargs):
        FileSystemTarget.__init__(self, path)
        if format is None:
            format = luigi.format.get_default_format()
        self.format = format
        self._fs = RemoteFileSystem(host, **kwargs)
