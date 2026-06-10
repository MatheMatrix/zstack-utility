#!/usr/bin/env python
# encoding: utf-8
import argparse
import datetime
import os
import sys

from zstacklib import *


def shell_quote(value):
    if value is None:
        return "''"
    return "'" + value.replace("'", "'\"'\"'") + "'"


logger_dir = "/var/log/zstack/"
create_log(logger_dir)
banner("Starting to deploy zns proxy")
start_time = datetime.datetime.now()

src_pkg_znsproxy = ""
dst_pkg_znsproxy = "/var/lib/zstack/zns-proxy/package/zns-proxy.bin"
znsproxy_health_url = "http://127.0.0.1:7890/zns-proxy/api/v1/health"
post_url = ""
chrony_servers = None
remote_user = "root"
remote_pass = None
remote_port = None
host_uuid = None

parser = argparse.ArgumentParser(description="Deploy zns proxy to host")
parser.add_argument("-i", type=str, help="specify inventory host file default=/etc/ansible/hosts")
parser.add_argument("--private-key", type=str, help="use this file to authenticate the connection")
parser.add_argument("-e", type=str, help="set additional variables as key=value or YAML/JSON")
args = parser.parse_args()
argument_dict = eval(args.e)
locals().update(argument_dict)

if not src_pkg_znsproxy:
    error("src_pkg_znsproxy is empty")

host_post_info = HostPostInfo()
host_post_info.host_inventory = args.i
host_post_info.host = host
host_post_info.host_uuid = host_uuid
host_post_info.post_url = post_url
host_post_info.chrony_servers = chrony_servers
host_post_info.private_key = args.private_key
host_post_info.remote_user = remote_user
host_post_info.remote_pass = remote_pass
host_post_info.remote_port = remote_port
if remote_pass is not None and remote_user != "root":
    host_post_info.become = True

package_dir = os.path.dirname(dst_pkg_znsproxy)
run_remote_command("mkdir -p %s" % shell_quote(package_dir), host_post_info)

copy_arg = CopyArg()
copy_arg.src = src_pkg_znsproxy
copy_arg.dest = dst_pkg_znsproxy
copy_arg.args = "force=yes mode=0755"
copy(copy_arg, host_post_info)

run_remote_command("chmod 0755 %s" % shell_quote(dst_pkg_znsproxy), host_post_info)
run_remote_command("%s install" % shell_quote(dst_pkg_znsproxy), host_post_info)
run_remote_command("curl -fsS %s" % shell_quote(znsproxy_health_url), host_post_info)

host_post_info.start_time = start_time
handle_ansible_info("SUCC: Deploy zns proxy successful", host_post_info, "INFO")
sys.exit(0)
