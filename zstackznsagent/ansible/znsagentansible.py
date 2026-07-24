#!/usr/bin/env python
# encoding: utf-8
import argparse
import datetime
import os
import sys

from zstacklib import *


def add_true_in_command(cmd):
    return "%s || true" % cmd


logger_dir = "/var/log/zstack/"
create_log(logger_dir)
banner("Starting to deploy zstack zns agent")
start_time = datetime.datetime.now()

pip_url = "https=//pypi.python.org/simple/"
proxy = ""
sproxy = ""
chroot_env = 'false'
zstack_repo = 'false'
current_dir = os.path.dirname(os.path.realpath(__file__))
file_root = "files/znsagentansible"
src_pkg_znsagent = ""
dest_pkg_znsagent = "zns-agent.bin"
post_url = ""
chrony_servers = None
fs_rootpath = ""
remote_user = "root"
remote_pass = None
remote_port = None
host_uuid = None
require_python_env = "false"
tmout = None

parser = argparse.ArgumentParser(description='Deploy zns-agent to host')
parser.add_argument('-i', type=str, help="""specify inventory host file
                        default=/etc/ansible/hosts""")
parser.add_argument('--private-key', type=str, help='use this file to authenticate the connection')
parser.add_argument('-e', type=str, help='set additional variables as key=value or YAML/JSON')
args = parser.parse_args()
argument_dict = eval(args.e)

locals().update(argument_dict)
zns_root = "%s/zns-agent/package" % zstack_root

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
if remote_pass is not None and remote_user != 'root':
    host_post_info.become = True

host_info = get_remote_host_info_obj(host_post_info)
host_info = upgrade_to_helix(host_info, host_post_info)
releasever = get_host_releasever(host_info)
host_post_info.releasever = releasever

zstacklib_args = ZstackLibArgs()
zstacklib_args.distro = host_info.distro
zstacklib_args.distro_release = host_info.distro_release
zstacklib_args.distro_version = host_info.major_version
zstacklib_args.zstack_repo = zstack_repo
zstacklib_args.zstack_root = zstack_root
zstacklib_args.host_post_info = host_post_info
zstacklib_args.pip_url = pip_url
zstacklib_args.trusted_host = trusted_host
zstacklib_args.require_python_env = require_python_env
zstacklib_args.zstack_releasever = releasever
if host_info.distro in DEB_BASED_OS:
    zstacklib_args.apt_server = yum_server
    zstacklib_args.zstack_apt_source = zstack_repo
else:
    zstacklib_args.yum_server = yum_server
zstacklib = ZstackLib(zstacklib_args)

if host_info.host_arch == 'x86_64':
    src_pkg_znsagent = "zns-agent.bin"
else:
    src_pkg_znsagent = "zns-agent.{}.bin".format(host_info.host_arch)

run_remote_command(add_true_in_command("rm -rf %s/*" % zns_root), host_post_info)
run_remote_command(add_true_in_command("mkdir -p %s" % zns_root), host_post_info)

copy_arg = CopyArg()
copy_arg.src = "%s/%s" % (file_root, src_pkg_znsagent)
copy_arg.dest = "%s/%s" % (zns_root, dest_pkg_znsagent)
copy(copy_arg, host_post_info)

run_remote_command(add_true_in_command("bash %s %s" % (copy_arg.dest, fs_rootpath)), host_post_info)
run_remote_command(add_true_in_command("systemctl daemon-reload && systemctl enable zstack-zns-agent.service && systemctl restart zstack-zns-agent.service"), host_post_info)
run_remote_command("systemctl status zstack-zns-agent.service > /dev/null", host_post_info)

host_post_info.start_time = start_time
handle_ansible_info("SUCC: Deploy zns agent successful", host_post_info, "INFO")
sys.exit(0)
