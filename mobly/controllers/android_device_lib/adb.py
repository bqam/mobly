#!/usr/bin/env python3.4
#
# Copyright 2016 Google Inc.
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from builtins import str
from past.builtins import basestring

import logging
import subprocess


class AdbError(Exception):
    """Raised when there is an error in adb operations."""

    def __init__(self, cmd, stdout, stderr, ret_code):
        self.cmd = cmd
        self.stdout = stdout
        self.stderr = stderr
        self.ret_code = ret_code

    def __str__(self):
        return ('Error executing adb cmd "%s". ret: %d, stdout: %s, stderr: %s'
                ) % (self.cmd, self.ret_code, self.stdout, self.stderr)


def list_occupied_adb_ports():
    """Lists all the host ports occupied by adb forward.

    This is useful because adb will silently override the binding if an attempt
    to bind to a port already used by adb was made, instead of throwing binding
    error. So one should always check what ports adb is using before trying to
    bind to a port with adb.

    Returns:
        A list of integers representing occupied host ports.
    """
    out = AdbProxy().forward('--list')
    clean_lines = str(out, 'utf-8').strip().split('\n')
    used_ports = []
    for line in clean_lines:
        tokens = line.split(' tcp:')
        if len(tokens) != 3:
            continue
        used_ports.append(int(tokens[1]))
    return used_ports


class AdbProxy(object):
    """Proxy class for ADB.

    For syntactic reasons, the '-' in adb commands need to be replaced with
    '_'. Can directly execute adb commands on an object:
    >> adb = AdbProxy(<serial>)
    >> adb.start_server()
    >> adb.devices() # will return the console output of "adb devices".

    By default, command args are expected to be an iterable which is passed
    directly to subprocess.Popen():
    >> adb.shell(['echo', 'a', 'b'])

    This way of launching commands is recommended by the subprocess
    documentation to avoid shell injection vulnerabilities and avoid having to
    deal with multiple layers of shell quoting and different shell environments
    between different OSes.

    If you really want to run the command through the system shell, this is
    possible by supplying shell=True, but try to avoid this if possible:
    >> adb.shell('cat /foo > /tmp/file', shell=True)
    """

    def __init__(self, serial=''):
        self.serial = serial

    def _exec_cmd(self, args, shell):
        """Executes adb commands.

        Args:
            args: string or list of strings, program arguments.
                See subprocess.Popen() documentation.
            shell: bool, True to run this command through the system shell,
                False to invoke it directly. See subprocess.Popen() docs.

        Returns:
            The output of the adb command run if exit code is 0.

        Raises:
            AdbError is raised if the adb command exit code is not 0.
        """
        proc = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shell)
        (out, err) = proc.communicate()
        ret = proc.returncode
        logging.debug('cmd: %s, stdout: %s, stderr: %s, ret: %s', args, out,
                      err, ret)
        if ret == 0:
            return out
        else:
            raise AdbError(cmd=args, stdout=out, stderr=err, ret_code=ret)

    def _exec_adb_cmd(self, name, args, shell):
        if shell:
            if self.serial:
                adb_cmd = 'adb -s "%s" %s %s' % (self.serial, name, args)
            else:
                adb_cmd = 'adb %s %s' % (name, args)
        else:
            adb_cmd = ['adb']
            if self.serial:
                adb_cmd.extend(['-s', self.serial])
            adb_cmd.append(name)
            if args:
                if isinstance(args, basestring):
                    adb_cmd.append(args)
                else:
                    adb_cmd.extend(args)
        return self._exec_cmd(adb_cmd, shell=shell)

    def getprop(self, prop_name):
        """Get a property of the device.

        This is a convenience wrapper for "adb shell getprop xxx".

        Args:
            prop_name: A string that is the name of the property to get.

        Returns:
            A string that is the value of the property, or None if the property
            doesn't exist.
        """
        return self.shell('getprop %s' % prop_name).decode('utf-8').strip()

    def __getattr__(self, name):
        def adb_call(args=None, shell=False):
            """Wrapper for an ADB command.

            Args:
                args: string or list of strings, arguments to the adb command.
                    See subprocess.Proc() documentation.
                shell: bool, True to run this command through the system shell,
                    False to invoke it directly. See subprocess.Proc() docs.

            Returns:
                The output of the adb command run if exit code is 0.
            """
            args = args or ''
            clean_name = name.replace('_', '-')
            return self._exec_adb_cmd(clean_name, args, shell=shell)

        return adb_call
