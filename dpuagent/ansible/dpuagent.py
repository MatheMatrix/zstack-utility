#!/usr/bin/env python
# encoding: utf-8
import argparse
import datetime
import os.path

from zstacklib import *

# create log
logger_dir = "/var/log/zstack/"
create_log(logger_dir)
banner("Starting to deploy baremetal2 dpu agent")
start_time = datetime.datetime.now()
# set default value
file_root = "files/dpuagent"
pip_url = "https=//pypi.python.org/simple/"
proxy = ""
sproxy = ""
chroot_env = 'false'
zstack_repo = 'false'
current_dir = os.path.dirname(os.path.realpath(__file__))
post_url = ""
chrony_servers = None
fs_rootpath = ""
max_capacity = 0
client = "false"
remote_user = "root"
remote_pass = None
remote_port = None
host_uuid = None
require_python_env = "false"
skip_packages = ""
new_add = "false"

# get parameter from shell
parser = argparse.ArgumentParser(description='Deploy dpu agent to host')
parser.add_argument('-i', type=str, help="""specify inventory host file
                        default=/etc/ansible/hosts""")
parser.add_argument('--private-key', type=str, help='use this file to authenticate the connection')
parser.add_argument('-e', type=str, help='set additional variables as key=value or YAML/JSON')

args = parser.parse_args()
argument_dict = eval(args.e)

# update the variable from shell arguments
locals().update(argument_dict)
dpuagent_root = "%s/dpuagent/package" % zstack_root
utils_root = "%s/dpuagent" % zstack_root

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

# include zstacklib.py
host_info = get_remote_host_info_obj(host_post_info)
releasever = get_host_releasever(host_info)
host_post_info.releasever = releasever

IS_AARCH64 = host_info.host_arch == 'aarch64'
IS_MIPS64EL = host_info.host_arch == 'mips64el'
IS_LOONGARCH64 = host_info.host_arch == 'loongarch64'

if host_info.host_arch == 'x86_64':
    src_pkg_dpuagent = "dpu-agent.bin"
else:
    src_pkg_dpuagent = "dpu-agent.{}.bin".format(host_info.host_arch)

dst_pkg_dpuagent = "dpu-agent.bin"

# name: copy dpuagent binary
command = 'rm -rf {};mkdir -p {}'.format(dpuagent_root, dpuagent_root + "/certs")
run_remote_command(command, host_post_info)
copy_arg = CopyArg()
dest_pkg = "%s/%s" % (dpuagent_root, dst_pkg_dpuagent)
copy_arg.src = "%s/%s" % (file_root, src_pkg_dpuagent)
copy_arg.args = "force=yes"
copy_arg.dest = dest_pkg
copy(copy_arg, host_post_info)

# name: copy iptables-scrpit
copy_arg = CopyArg()
copy_arg.src = "%s/dpu-iptables" % file_root
copy_arg.dest = "%s/dpu-iptables" % dpuagent_root
copy_arg.args = "force=yes"
copy(copy_arg, host_post_info)


# name: install zstack-store
if client == "false":
    command = "bash %s %s %s" % (dest_pkg, fs_rootpath, max_capacity)
else:
    command = "bash " + dest_pkg
run_remote_command(command, host_post_info)

# if user is not root , Change the owner of the directory to ordinary user
if fs_rootpath != '' and remote_user != 'root':
    run_remote_command("sudo chown -R -H --dereference %s: %s" % (remote_user, fs_rootpath), host_post_info)


host_post_info.start_time = start_time
handle_ansible_info("SUCC: Deploy dpuagent successful", host_post_info, "INFO")
sys.exit(0)

