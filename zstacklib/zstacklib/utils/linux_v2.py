import socket


def check_remote_port_whether_open(remote_addr, remote_port):
    """ Check the remote port whether open

    :param remote_addr: Remote host's ip address
    :param remote_port: Remote host's tcp port
    :type remote_addr: string
    :type remote_port: int
    :return: A boolean value to decide the port whether open
    :rtype: boolean
    """

    family = socket.AF_INET6 if ':' in remote_addr else socket.AF_INET
    s = socket.socket(family, socket.SOCK_STREAM)
    ret = s.connect_ex((remote_addr, remote_port))

    return ret == 0
