import os.path

from oslo_concurrency import processutils
from oslo_log import log as logging
import subprocess
import re
import time

from bm_instance_agent.common import utils as agent_utils
from bm_instance_agent import exception

from centos_network_config import CentOSNetworkConfig as config
from centos import CentOSDriver

LOG = logging.getLogger(__name__)


class KylinDriver(CentOSDriver):

    driver_name = 'kylin'

    def attach_port(self, instance_obj, network_obj):
        for port in network_obj.ports:
            self._attach_port(port)
            if port.type == port.PORT_TYPE_BOND:
                self._write_bond_to_dracut_config(port)
                try:
                    subprocess.check_call(['dracut', '-f'])
                except Exception as e:
                    LOG.error("Failed to update dracut configuration: %s" % e)



    def detach_port(self, instance_obj, network_obj):
        for port in network_obj.ports:
            # Ensure that the conf file exist because command ifdown
            # requires it.
            if port.type == port.PORT_TYPE_BOND:
                raise exception.NewtorkInterfaceConfigParasInvalid(
                    exception_msg="port type {} is not support".format(port.type))
            self._detach_port(port)

    def _write_bond_to_dracut_config(self, port):
        output_file = "/etc/dracut.conf.d/bonding.conf"
        bonding_config = "/etc/sysconfig/network-scripts/ifcfg-%s" % port.iface_name
        if not os.path.exists(bonding_config):
            return

        slave_interfaces = self._read_slaves_from_sys(port.iface_name)
        bonding_opts = self._read_bonding_opts_from_ifcfg(bonding_config)
        new_config_content = (
            'add_dracutmodules+=" network "\n'
            'kernel_cmdline+=" bond={name}:{slaves}:{bonding_opts} ip={name}:dhcp bootdev={name}"'
        ).format(
            name=port.iface_name,
            slaves=slave_interfaces,
            bonding_opts=bonding_opts
        )

        if os.path.exists(output_file):
            try:
                with open(output_file, "r") as f:
                    existing_content = f.read()

                add_dracutmodules_pattern = re.compile(r'add_dracutmodules\s*\+=\s*"\s*network\s*"')

                if add_dracutmodules_pattern.search(existing_content):
                    kernel_cmdline_pattern = re.compile(r'kernel_cmdline\s*\+=\s*" bond=[^"]+"')
                    existing_kernel_cmdline_match = kernel_cmdline_pattern.search(existing_content)
                    if existing_kernel_cmdline_match:
                        existing_kernel_cmdline = existing_kernel_cmdline_match.group(0)
                        new_kernel_cmdline = (
                            'kernel_cmdline+=" bond={name}:{slaves}:{bonding_opts} '
                            'ip={name}:dhcp"'
                        ).format(
                            name=port.iface_name,
                            slaves=slave_interfaces,
                            bonding_opts=bonding_opts
                        )

                        if existing_kernel_cmdline != new_kernel_cmdline:
                            with open(output_file, "a") as f:
                                f.write("\n" + new_kernel_cmdline + "\n")
                    else:
                        with open(output_file, "a") as f:
                            f.write("\n" + new_config_content + "\n")
                else:
                    with open(output_file, "a") as f:
                        f.write(new_config_content + "\n")
            except IOError as e:
                LOG.info("fail to get config, error :%s" % e)
        else:
            try:
                with open(output_file, "w") as f:
                    f.write(new_config_content)
            except IOError as e:
                LOG.info("write config has error :%s" % e)

    def _read_slaves_from_sys(self, bond_name):
        slaves_file_path = '/sys/class/net/{}/bonding/slaves'.format(bond_name)
        max_retries = 3
        for attempt in range(3):
            try:
                with open(slaves_file_path, 'r') as f:
                    slaves = f.read().strip()

                if slaves:
                    LOG.info("the slaves file is %s", slaves)
                    return ','.join(slaves.split())

                LOG.warning("Attempt %d/%d: Slaves file is empty. Retrying...", attempt + 1, max_retries)
            except FileNotFoundError:
                LOG.error("Attempt %d/%d: Slaves file not found. Retrying...", attempt + 1, max_retries)

            time.sleep(3)

        LOG.error("Failed to read slaves after %d attempts.", max_retries)
        return None

    def _read_bonding_opts_from_ifcfg(self, ifcfg_file):
        bonding_opts = ""

        try:
            with open(ifcfg_file, 'r') as f:
                content = f.readlines()
                LOG.info("the bond ifcfg file is %s" % content)

            for line in content:
                match = re.search(r'^\s*BONDING_OPTS\s*=\s*"([^"]+)"', line)
                if match:
                    opts_str = match.group(1).strip()
                    bonding_opts = ','.join([opt.strip() for opt in opts_str.split()])
                    break

        except FileNotFoundError:
            LOG.error("Error: The file %s was not found." % ifcfg_file)
        except Exception as e:
            LOG.error("Failed to read bonding options from %s: %s" % (ifcfg_file, e))

        return bonding_opts

    def update_default_route(
            self, instance_obj, old_network_obj, new_network_obj):
        """ Update the default route(gateway) on CentOS

        If old_network_obj is not none, update the conf file.
        If new_network_obj is not none, update the conf file, change default
        gw if new gw is not equal to exist gw.
        """

        if old_network_obj:
            old_port = old_network_obj.ports[0]
            if old_port.type == old_port.PORT_TYPE_BOND:
                raise exception.NewtorkInterfaceConfigParasInvalid(
                    exception_msg="port type {} is not support".format(old_port.type))
            config.persist_network_config(old_port)

        agent_utils.ip_route_del('default')

        if new_network_obj:
            port = new_network_obj.ports[0]
            if old_port.type == old_port.PORT_TYPE_BOND:
                raise exception.NewtorkInterfaceConfigParasInvalid(
                    exception_msg="port type {} is not support".format(old_port.type))
            config.persist_network_config(port)

            cmd = ['ip', 'route', 'add', 'default', 'via',
                   port.gateway, 'dev', port.get_l3_interface()]
            processutils.execute(*cmd)


class KylinV10ARM(KylinDriver):

    driver_name = 'kylin_v10_arm'
