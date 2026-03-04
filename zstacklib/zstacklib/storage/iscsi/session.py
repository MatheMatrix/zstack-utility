"""iSCSI session management operations.

This module provides functions for managing iSCSI sessions:

- login(): Login to an iSCSI target
- logout(): Logout from an iSCSI target
- list_sessions(): List all active iSCSI sessions
- get_session(): Get session for a specific target
- rescan_session(): Rescan an iSCSI session
- delete_node(): Delete an iSCSI node configuration
"""

import logging
import shlex
from typing import List, Optional

from zstacklib.utils import bash, lock, linux

from .exceptions import (
    LoginError, LogoutError, SessionNotFoundError, 
    RescanError, NodeDeleteError, ChapAuthError
)
from .models import IscsiPortal, IscsiSession, IscsiTarget, ChapCredentials


logger = logging.getLogger(__name__)

# Default timeouts
DEFAULT_LOGIN_TIMEOUT = 10
DEFAULT_LOGOUT_TIMEOUT = 10
DEFAULT_RESCAN_TIMEOUT = 30


def list_sessions() -> List[IscsiSession]:
    """List all active iSCSI sessions.
    
    Returns:
        List of IscsiSession objects for all active sessions
        
    Example:
        >>> sessions = list_sessions()
        >>> for s in sessions:
        ...     print(f"Session {s.session_id}: {s.target_iqn}")
    """
    r, o, e = bash.bash_roe("iscsiadm -m session")
    
    # Return code 21 means no active sessions (not an error)
    if r == 21 or (r != 0 and "No active sessions" in (e or "")):
        return []
    
    if r != 0 and o.strip() == "":
        # No sessions
        return []
    
    sessions = []
    for line in o.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        session = IscsiSession.from_session_line(line)
        if session:
            sessions.append(session)
    
    return sessions


def get_session(
    ip: str,
    iqn: str,
    port: int = 3260
) -> Optional[IscsiSession]:
    """Get session for a specific target.
    
    Args:
        ip: iSCSI portal IP address
        iqn: Target IQN
        port: iSCSI portal port (default 3260)
        
    Returns:
        IscsiSession if found, None otherwise
        
    Example:
        >>> session = get_session('192.168.1.100', 'iqn.2020-01.com.example:storage')
        >>> if session:
        ...     print(f"Connected with session {session.session_id}")
    """
    port = int(port)
    # Use list_sessions() + Python filtering instead of grep-based shell command
    for session in list_sessions():
        if (session.target_iqn == iqn
                and session.portal
                and session.portal.ip == ip
                and session.portal.port == port):
            return session

    return None


def get_session_id(
    ip: str,
    iqn: str,
    port: int = 3260
) -> Optional[str]:
    """Get session ID for a specific target.
    
    Args:
        ip: iSCSI portal IP address
        iqn: Target IQN
        port: iSCSI portal port (default 3260)
        
    Returns:
        Session ID string if found, None otherwise
    """
    session = get_session(ip, iqn, port)
    return session.session_id if session else None


def is_logged_in(ip: str, iqn: str, port: int = 3260) -> bool:
    """Check if a target is currently logged in.
    
    Args:
        ip: iSCSI portal IP address
        iqn: Target IQN
        port: iSCSI portal port (default 3260)
        
    Returns:
        True if session exists, False otherwise
    """
    return get_session(ip, iqn, port) is not None


def _set_chap_auth(
    ip: str,
    iqn: str,
    username: str,
    password: str,
    port: int = 3260
) -> None:
    """Configure CHAP authentication for a target.
    
    This must be called after discovery and before login.
    
    Args:
        ip: iSCSI portal IP address
        iqn: Target IQN
        username: CHAP username
        password: CHAP password
        port: iSCSI portal port
        
    Raises:
        ChapAuthError: If CHAP configuration fails
    """
    portal_str = "{}:{}".format(ip, port)
    base_cmd = 'iscsiadm --mode node --targetname {} -p {} --op=update'.format(
        linux.shellquote(iqn), shlex.quote(portal_str)
    )
    
    # Set auth method to CHAP
    r, o, e = bash.bash_roe(
        '{} --name node.session.auth.authmethod --value=CHAP'.format(base_cmd)
    )
    if r != 0:
        raise ChapAuthError(
            portal=portal_str, target=iqn,
            message="Failed to set CHAP authmethod: {}".format(e),
            return_code=r
        )
    
    # Set username
    r, o, e = bash.bash_roe(
        '{} --name node.session.auth.username --value={}'.format(base_cmd, linux.shellquote(username))
    )
    if r != 0:
        raise ChapAuthError(
            portal=portal_str, target=iqn,
            message="Failed to set CHAP username: {}".format(e),
            return_code=r
        )
    
    # Set password (quote it for safety)
    quoted_password = linux.shellquote(password)
    r, o, e = bash.bash_roe(
        '{} --name node.session.auth.password --value={}'.format(base_cmd, quoted_password)
    )
    if r != 0:
        raise ChapAuthError(
            portal=portal_str, target=iqn,
            message="Failed to set CHAP password: {}".format(e),
            return_code=r
        )
    
    logger.debug("CHAP authentication configured for %s on %s", iqn, portal_str)


@lock.lock('iscsiadm')
def login(
    ip: str,
    iqn: str,
    port: int = 3260,
    chap_username: Optional[str] = None,
    chap_password: Optional[str] = None,
    timeout: int = DEFAULT_LOGIN_TIMEOUT
) -> IscsiSession:
    """Login to an iSCSI target.
    
    If the session already exists, returns the existing session.
    
    Args:
        ip: iSCSI portal IP address
        iqn: Target IQN
        port: iSCSI portal port (default 3260)
        chap_username: CHAP username (optional)
        chap_password: CHAP password (optional)
        timeout: Command timeout in seconds (default 10)
        
    Returns:
        IscsiSession for the logged-in target
        
    Raises:
        LoginError: If login fails
        ChapAuthError: If CHAP configuration fails
        
    Example:
        >>> session = login('192.168.1.100', 'iqn.2020-01.com.example:storage')
        >>> print(f"Logged in with session {session.session_id}")
        
        >>> # With CHAP authentication
        >>> session = login('192.168.1.100', 'iqn.2020-01.com.example:storage',
        ...                 chap_username='user', chap_password='secret')
    """
    portal = IscsiPortal(ip=ip, port=port)
    portal_str = str(portal)
    
    # Check if already logged in
    existing = get_session(ip, iqn, port)
    if existing:
        logger.debug("Already logged in to %s on %s", iqn, portal_str)
        return existing
    
    logger.info("Logging in to iSCSI target %s on %s", iqn, portal_str)
    
    # Configure CHAP if credentials provided
    if chap_username and chap_password:
        _set_chap_auth(ip, iqn, chap_username, chap_password, port)
    
    # Perform login
    cmd = 'timeout {} iscsiadm --mode node --targetname {} -p {} --login'.format(
        int(timeout), linux.shellquote(iqn), shlex.quote(portal_str)
    )
    r, o, e = bash.bash_roe(cmd)
    
    if r != 0:
        # Check for common errors
        error_msg = e.strip() if e else o.strip() if o else "unknown error"
        
        # Session might already exist (race condition)
        if "already present" in error_msg.lower():
            session = get_session(ip, iqn, port)
            if session:
                return session
        
        logger.error("Failed to login to %s on %s: %s", iqn, portal_str, error_msg)
        raise LoginError(
            portal=portal_str,
            target=iqn,
            message="Login failed: {}".format(error_msg),
            return_code=r
        )
    
    # Get the new session
    session = get_session(ip, iqn, port)
    if not session:
        raise LoginError(
            portal=portal_str,
            target=iqn,
            message="Login completed but session not found"
        )
    
    logger.info("Successfully logged in to %s, session %s", iqn, session.session_id)
    return session


@lock.lock('iscsiadm')
def logout(
    ip: str,
    iqn: str,
    port: int = 3260,
    delete_node: bool = True,
    timeout: int = DEFAULT_LOGOUT_TIMEOUT
) -> bool:
    """Logout from an iSCSI target.
    
    Args:
        ip: iSCSI portal IP address
        iqn: Target IQN
        port: iSCSI portal port (default 3260)
        delete_node: Whether to delete the node configuration after logout (default True)
        timeout: Command timeout in seconds (default 10)
        
    Returns:
        True if logout was successful or session didn't exist
        
    Raises:
        LogoutError: If logout fails
        
    Example:
        >>> logout('192.168.1.100', 'iqn.2020-01.com.example:storage')
        True
    """
    portal = IscsiPortal(ip=ip, port=port)
    portal_str = str(portal)
    
    # Check if session exists
    if not is_logged_in(ip, iqn, port):
        logger.debug("Not logged in to %s on %s, nothing to logout", iqn, portal_str)
        return True
    
    logger.info("Logging out from iSCSI target %s on %s", iqn, portal_str)
    
    # Perform logout
    cmd = 'timeout {} iscsiadm --mode node --targetname {} -p {} --logout'.format(
        int(timeout), linux.shellquote(iqn), shlex.quote(portal_str)
    )
    r, o, e = bash.bash_roe(cmd)
    
    if r != 0:
        error_msg = e.strip() if e else o.strip() if o else "unknown error"
        
        # Session might already be gone
        if "No matching sessions" in error_msg or not is_logged_in(ip, iqn, port):
            logger.debug("Session already gone for %s", iqn)
        else:
            logger.error("Failed to logout from %s on %s: %s", iqn, portal_str, error_msg)
            raise LogoutError(
                portal=portal_str,
                target=iqn,
                message="Logout failed: {}".format(error_msg),
                return_code=r
            )
    
    # Delete node configuration if requested
    if delete_node:
        try:
            _delete_node(ip, iqn, port, timeout)
        except NodeDeleteError as e:
            # Log but don't fail - logout was successful
            logger.warning("Failed to delete node after logout: %s", e)
    
    logger.info("Successfully logged out from %s", iqn)
    return True


def _delete_node(
    ip: str,
    iqn: str,
    port: int = 3260,
    timeout: int = DEFAULT_LOGOUT_TIMEOUT
) -> None:
    """Delete an iSCSI node configuration.
    
    Args:
        ip: iSCSI portal IP address
        iqn: Target IQN
        port: iSCSI portal port
        timeout: Command timeout in seconds
        
    Raises:
        NodeDeleteError: If deletion fails
    """
    portal_str = "{}:{}".format(ip, port)
    
    cmd = 'timeout {} iscsiadm -m node -o delete -T {} -p {}'.format(
        int(timeout), linux.shellquote(iqn), shlex.quote(portal_str)
    )
    r, o, e = bash.bash_roe(cmd)
    
    if r != 0:
        error_msg = e.strip() if e else "unknown error"
        # Ignore "No records found" - node might already be deleted
        if "No records found" not in error_msg:
            raise NodeDeleteError(
                portal=portal_str,
                target=iqn,
                message="Failed to delete node: {}".format(error_msg),
                return_code=r
            )


def rescan_session(session_id: str, timeout: int = DEFAULT_RESCAN_TIMEOUT) -> None:
    """Rescan an iSCSI session for new LUNs.
    
    Args:
        session_id: Session ID to rescan
        timeout: Command timeout in seconds (default 30)
        
    Raises:
        RescanError: If rescan fails
        
    Example:
        >>> session = login('192.168.1.100', 'iqn.2020-01.com.example:storage')
        >>> rescan_session(session.session_id)
    """
    if not str(session_id).isdigit():
        raise ValueError(f"Invalid session_id: {session_id!r}, must be numeric")
    cmd = "timeout {} iscsiadm -m session -r {} --rescan".format(int(timeout), session_id)
    r, o, e = bash.bash_roe(cmd)
    
    if r != 0:
        raise RescanError(
            session_id=session_id,
            message="Rescan failed: {}".format(e.strip() if e else "unknown error"),
            return_code=r
        )
    
    logger.debug("Rescanned session %s", session_id)


def rescan_all_sessions(timeout: int = DEFAULT_RESCAN_TIMEOUT) -> None:
    """Rescan all active iSCSI sessions.
    
    Args:
        timeout: Command timeout in seconds (default 30)
    """
    cmd = "timeout {} iscsiadm -m session -R".format(int(timeout))
    r, o, e = bash.bash_roe(cmd)
    
    if r != 0:
        logger.warning("Rescan all sessions returned error: %s", e)
    else:
        logger.debug("Rescanned all iSCSI sessions")


def get_host_number(session_id: str) -> Optional[int]:
    """Get the SCSI host number for an iSCSI session.
    
    Args:
        session_id: Session ID
        
    Returns:
        Host number if found, None otherwise
    """
    if not str(session_id).isdigit():
        raise ValueError(f"Invalid session_id: {session_id!r}, must be numeric")
    cmd = "iscsiadm -m session -P 3 --sid={} | grep 'Host Number:' | awk '{{print $3}}'".format(
        session_id
    )
    r, o, e = bash.bash_roe(cmd)
    
    if r != 0 or not o.strip():
        return None
    
    try:
        return int(o.strip())
    except ValueError:
        return None


def get_session_luns(session_id: str) -> List[str]:
    """Get list of LUNs for an iSCSI session.
    
    Args:
        session_id: Session ID
        
    Returns:
        List of LUN lines from iscsiadm output
    """
    if not str(session_id).isdigit():
        raise ValueError(f"Invalid session_id: {session_id!r}, must be numeric")
    cmd = "iscsiadm -m session -P 3 --sid={} | grep Lun".format(session_id)
    r, o, e = bash.bash_roe(cmd)
    
    if r != 0 or not o.strip():
        return []
    
    return [line.strip() for line in o.strip().splitlines() if line.strip()]
