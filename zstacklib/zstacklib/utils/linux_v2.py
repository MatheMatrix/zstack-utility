from zstacklib.utils import network_ipv6


def check_remote_port_whether_open(remote_addr, remote_port):
    """ Check the remote port whether open

    :param remote_addr: Remote host's ip address
    :param remote_port: Remote host's tcp port
    :type remote_addr: string
    :type remote_port: int
    :return: A boolean value to decide the port whether open
    :rtype: boolean
    """

    s = network_ipv6.create_tcp_socket_for_host(remote_addr)
    ret = s.connect_ex((remote_addr, remote_port))

    return ret == 0
