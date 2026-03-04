# -*- coding: utf-8 -*-
"""
Integration tests for kvmagent remote operations.

Tests kvmagent service status and functionality via SSH connection.
Requires --ssh-host to run (uses ssh_run fixture).
"""
import pytest


@pytest.mark.kvmagent
@pytest.mark.integration
def test_kvmagent_process_status(ssh_run):
    """
    Verify kvmagent process is running on remote host.
    
    Uses ssh_run fixture to check if kvmagent process is active.
    This is an integration test that requires a real SSH connection
    to a host with kvmagent installed.
    
    Skip conditions:
    - No --ssh-host provided (ssh_run will be None)
    - Remote host doesn't have kvmagent installed
    
    Args:
        ssh_run: SSH command execution fixture from pytest-ssh plugin
                 Returns (exit_code, stdout, stderr) tuple
    """
    if ssh_run is None:
        pytest.skip("Integration test requires --ssh-host parameter")
    
    # Check if kvmagent process is running
    exit_code, stdout, stderr = ssh_run("ps aux | grep '[k]vmagent' | grep -v grep")
    
    # Assert process is found
    assert exit_code == 0, f"kvmagent process not found. stderr: {stderr}"
    assert "kvmagent" in stdout, f"Expected 'kvmagent' in process list, got: {stdout}"
    
    # Additional validation: check for Python process
    # kvmagent typically runs as a Python process
    assert "python" in stdout.lower() or "kvmagent" in stdout, \
        f"Expected Python process for kvmagent, got: {stdout}"


@pytest.mark.kvmagent
@pytest.mark.integration
def test_kvmagent_config_file_exists(ssh_run):
    """
    Verify kvmagent configuration file exists on remote host.
    
    Checks for the presence of kvmagent.conf in the expected location.
    
    Args:
        ssh_run: SSH command execution fixture
    """
    if ssh_run is None:
        pytest.skip("Integration test requires --ssh-host parameter")
    
    # Standard kvmagent config location
    config_path = "/var/lib/zstack/kvmagent/kvmagent.conf"
    
    exit_code, stdout, stderr = ssh_run(f"test -f {config_path} && echo 'EXISTS' || echo 'NOT_FOUND'")
    
    # Check if file exists
    assert "EXISTS" in stdout, \
        f"kvmagent config not found at {config_path}. stderr: {stderr}"


@pytest.mark.kvmagent
@pytest.mark.integration
def test_kvmagent_log_directory_accessible(ssh_run):
    """
    Verify kvmagent log directory is accessible and contains logs.
    
    Checks if the kvmagent log directory exists and has log files.
    
    Args:
        ssh_run: SSH command execution fixture
    """
    if ssh_run is None:
        pytest.skip("Integration test requires --ssh-host parameter")
    
    # Standard kvmagent log location
    log_dir = "/var/log/zstack"
    
    # Check directory exists
    exit_code, stdout, stderr = ssh_run(f"test -d {log_dir} && echo 'EXISTS' || echo 'NOT_FOUND'")
    assert "EXISTS" in stdout, f"Log directory {log_dir} not found. stderr: {stderr}"
    
    # Check for kvmagent log files
    exit_code, stdout, stderr = ssh_run(f"ls {log_dir}/zstack-kvmagent.log* 2>/dev/null | wc -l")
    
    if exit_code == 0:
        log_count = int(stdout.strip())
        assert log_count > 0, f"No kvmagent log files found in {log_dir}"
