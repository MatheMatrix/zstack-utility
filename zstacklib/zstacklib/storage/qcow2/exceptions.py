# Copyright (c) ZStack.io, Inc.

"""
QCOW2 image format exceptions.
"""


class Qcow2Error(Exception):
    """Base exception for QCOW2 operations."""
    pass


class Qcow2FormatError(Qcow2Error):
    """Raised when an image has an invalid or unsupported format."""
    
    def __init__(self, path, fmt=None, msg=None):
        """Init."""
        # type: (str, str, str) -> None
        self.path = path
        self.format = fmt
        if msg:
            message = msg
        elif fmt:
            message = 'Unknown format [{}] of image file [{}]'.format(fmt, path)
        else:
            message = 'Invalid or unsupported format'
        super(Qcow2FormatError, self).__init__(message)


class Qcow2InfoError(Qcow2Error):
    """Raised when image info cannot be retrieved."""
    
    def __init__(self, path, msg=None):
        """Init."""
        # type: (str, str) -> None
        self.path = path
        message = msg or 'Cannot get info for image [{}]'.format(path)
        super(Qcow2InfoError, self).__init__(message)


class Qcow2CreateError(Qcow2Error):
    """Raised when image creation fails."""
    
    def __init__(self, path, msg=None):
        """Init."""
        # type: (str, str) -> None
        self.path = path
        message = msg or 'Failed to create image [{}]'.format(path)
        super(Qcow2CreateError, self).__init__(message)


class Qcow2ConvertError(Qcow2Error):
    """Raised when image conversion fails."""
    
    def __init__(self, src, dst, msg=None):
        """Init."""
        # type: (str, str, str) -> None
        self.src = src
        self.dst = dst
        message = msg or 'Failed to convert [{}] to [{}]'.format(src, dst)
        super(Qcow2ConvertError, self).__init__(message)


class Qcow2ChainError(Qcow2Error):
    """Raised when backing file chain operations fail."""
    
    def __init__(self, path, msg=None):
        """Init."""
        # type: (str, str) -> None
        self.path = path
        message = msg or 'Backing file chain error for [{}]'.format(path)
        super(Qcow2ChainError, self).__init__(message)
