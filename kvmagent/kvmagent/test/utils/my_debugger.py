#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Debug utility for PR system environment analysis.
This script helps diagnose import errors in the PR system black box.
"""

import os
import sys
import traceback
import subprocess
import platform
import json
import pkgutil
import inspect
import importlib


def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 80)
    print(" " + title)
    print("=" * 80)


def get_python_info():
    """Print Python environment information"""
    print_section("PYTHON ENVIRONMENT")
    print("Python version: " + sys.version)
    print("Python executable: " + sys.executable)
    print("Platform: " + platform.platform())
    print("Current working directory: " + os.getcwd())
    print("Python path:")
    for p in sys.path:
        print("  " + p)


def check_zstacklib_import():
    """Check if zstacklib can be imported and find its location"""
    print_section("ZSTACKLIB IMPORT CHECK")
    
    # Try to import zstacklib
    try:
        import zstacklib
        print("[OK] zstacklib imported successfully")
        print("  Module location: " + zstacklib.__file__)
        
        # Try to import zstacklib.test.utils
        try:
            from zstacklib.test import utils
            print("[OK] zstacklib.test.utils imported successfully")
            print("  Module location: " + utils.__file__)
            
            # Check what's in the utils module
            print("  Available in utils module:")
            for name in dir(utils):
                if not name.startswith('_'):
                    print("    - " + name)
        except ImportError as e:
            print("[ERROR] Failed to import zstacklib.test.utils: " + str(e))
            
            # Try to find the test module
            print("  Searching for test module...")
            test_path = os.path.join(os.path.dirname(zstacklib.__file__), "test")
            if os.path.exists(test_path):
                print("  Found test directory at: " + test_path)
                print("  Contents of test directory:")
                for item in os.listdir(test_path):
                    print("    - " + item)
            else:
                print("  No test directory found in zstacklib")
                
    except ImportError as e:
        print("[ERROR] Failed to import zstacklib: " + str(e))
        
        # Try to find zstacklib in Python path
        print("  Searching for zstacklib in Python path...")
        for path in sys.path:
            if os.path.exists(path):
                zstacklib_path = os.path.join(path, "zstacklib")
                if os.path.exists(zstacklib_path):
                    print("  Found zstacklib at: " + zstacklib_path)
                    print("  Contents:")
                    for item in os.listdir(zstacklib_path):
                        print("    - " + item)


def check_kvmagent_structure():
    """Check kvmagent directory structure"""
    print_section("KVMAGENT DIRECTORY STRUCTURE")
    
    # Get current file location
    current_dir = os.path.dirname(os.path.abspath(__file__))
    print("Current debugger location: " + current_dir)
    
    # Go up to kvmagent root
    kvmagent_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
    print("Kvmagent root: " + kvmagent_root)
    
    # Check test directory structure
    test_dir = os.path.join(kvmagent_root, "test")
    if os.path.exists(test_dir):
        print("Test directory structure:")
        for root, dirs, files in os.walk(test_dir):
            level = root.replace(test_dir, '').count(os.sep)
            indent = ' ' * 2 * level
            print(indent + os.path.basename(root) + "/")
            subindent = ' ' * 2 * (level + 1)
            for file in files[:5]:  # Limit to 5 files per directory
                if file.endswith('.py'):
                    print(subindent + file)
            if len(files) > 5:
                print(subindent + "... and " + str(len(files) - 5) + " more files")
    else:
        print("[ERROR] Test directory not found: " + test_dir)


def check_import_chain():
    """Check the import chain that's failing"""
    print_section("IMPORT CHAIN ANALYSIS")
    
    # Try to import the problematic modules
    modules_to_check = [
        "kvmagent.test.utils.snapshot_utils",
        "kvmagent.test.utils.vm_utils",
        "kvmagent.test.localstorage_testsuite.test_revert_volume_snapshot_group_with_memory_snapshot"
    ]
    
    for module_name in modules_to_check:
        print("\nTrying to import: " + module_name)
        try:
            module = importlib.import_module(module_name)
            print("  [OK] Successfully imported")
            print("  Location: " + module.__file__)
        except ImportError as e:
            print("  [ERROR] Import failed: " + str(e))
            print("  Traceback:")
            traceback.print_exc()


def check_system_environment():
    """Check system environment variables and configuration"""
    print_section("SYSTEM ENVIRONMENT")
    
    # Check important environment variables
    env_vars = [
        "PATH",
        "PYTHONPATH", 
        "VIRTUAL_ENV",
        "HOME",
        "USER"
    ]
    
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            print(var + ": " + value)
        else:
            print(var + ": (not set)")
    
    # Check if we're in a virtual environment
    if hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix):
        print("Running in virtual environment: " + sys.prefix)
    else:
        print("Not running in virtual environment")


def check_package_installation():
    """Check installed packages"""
    print_section("INSTALLED PACKAGES")
    
    try:
        # Try to use pip to list packages
        result = subprocess.Popen(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = result.communicate()
        
        if result.returncode == 0:
            packages = json.loads(stdout)
            print("Found " + str(len(packages)) + " installed packages")
            
            # Look for zstack-related packages
            zstack_packages = [p for p in packages if "zstack" in p["name"].lower()]
            if zstack_packages:
                print("\nZStack-related packages:")
                for pkg in zstack_packages:
                    print("  " + pkg['name'] + "==" + pkg['version'])
            else:
                print("\nNo ZStack-related packages found")
        else:
            print("Failed to list packages: " + stderr)
    except Exception as e:
        print("Error checking packages: " + str(e))


def check_file_permissions():
    """Check file permissions for critical paths"""
    print_section("FILE PERMISSIONS")
    
    paths_to_check = [
        "/root/.zguest/zstack-utility",
        "/var/lib/zstack",
        "/usr/local/zstack",
        os.path.dirname(os.path.abspath(__file__))
    ]
    
    for path in paths_to_check:
        if os.path.exists(path):
            try:
                stat_info = os.stat(path)
                print(path + ":")
                print("  Exists: Yes")
                print("  Permissions: " + oct(stat_info.st_mode)[-3:])
                print("  Owner: " + str(stat_info.st_uid))
                print("  Group: " + str(stat_info.st_gid))
            except Exception as e:
                print(path + ": Error checking - " + str(e))
        else:
            print(path + ": Does not exist")


def run_shell_commands():
    """Run diagnostic shell commands"""
    print_section("SHELL COMMANDS OUTPUT")
    
    commands = [
        ("pwd", "Current directory"),
        ("ls -la", "Directory listing"),
        ("which python", "Python executable location"),
        ("python -c \"import sys; print('Python path:', sys.path)\"", "Python path from interpreter"),
        ("find /root/.zguest -name 'zstacklib' -type d 2>/dev/null | head -5", "Find zstacklib directories"),
        ("find /usr/local -name 'zstacklib' -type d 2>/dev/null | head -5", "Find zstacklib in /usr/local")
    ]
    
    for cmd, description in commands:
        print("\n" + description + ":")
        print("  Command: " + cmd)
        try:
            result = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = result.communicate(timeout=10)
            if stdout:
                print("  Output:\n" + stdout)
            if stderr:
                print("  Stderr:\n" + stderr)
            print("  Return code: " + str(result.returncode))
        except subprocess.TimeoutExpired:
            print("  Command timed out")
        except Exception as e:
            print("  Error: " + str(e))


def create_test_import():
    """Create a test import to diagnose the exact issue"""
    print_section("TEST IMPORT DIAGNOSIS")
    
    # Create a simple test to see what imports work
    test_code = '''
import sys
print("Python path:")
for p in sys.path:
    print("  " + p)

print("\nTrying imports:")
try:
    import zstacklib
    print("[OK] zstacklib imported")
    print("  Location: " + zstacklib.__file__)
    
    # Check if test module exists
    import inspect
    import pkgutil
    
    # Look for test submodule
    if hasattr(zstacklib, 'test'):
        print("[OK] zstacklib.test exists")
        if hasattr(zstacklib.test, 'utils'):
            print("[OK] zstacklib.test.utils exists")
        else:
            print("[ERROR] zstacklib.test.utils does not exist")
            # List what's in test
            print("  Contents of zstacklib.test:")
            for name in dir(zstacklib.test):
                if not name.startswith('_'):
                    print("    - " + name)
    else:
        print("[ERROR] zstacklib.test does not exist")
        print("  Contents of zstacklib:")
        for name in dir(zstacklib):
            if not name.startswith('_'):
                print("    - " + name)
                
except ImportError as e:
    print("[ERROR] zstacklib import failed: " + str(e))
    
    # Try to find it manually
    import os
    for path in sys.path:
        zstacklib_path = os.path.join(path, "zstacklib")
        if os.path.exists(zstacklib_path):
            print("Found zstacklib directory at: " + zstacklib_path)
            print("Contents:")
            for item in os.listdir(zstacklib_path):
                print("  - " + item)
'''
    
    # Write and execute the test
    test_file = "/tmp/debug_import_test.py"
    try:
        with open(test_file, "w") as f:
            f.write(test_code)
        
        print("Running test from: " + test_file)
        result = subprocess.Popen(
            [sys.executable, test_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = result.communicate()
        
        print("\nTest output:")
        print(stdout)
        if stderr:
            print("Stderr:\n" + stderr)
        
        # Clean up
        os.remove(test_file)
    except Exception as e:
        print("Error running test: " + str(e))


def main():
    """Main debug function"""
    print("PR SYSTEM DEBUG UTILITY")
    print("=" * 80)
    
    # Run all diagnostic functions
    get_python_info()
    check_system_environment()
    check_kvmagent_structure()
    check_zstacklib_import()
    check_import_chain()
    check_package_installation()
    check_file_permissions()
    run_shell_commands()
    create_test_import()
    
    print_section("DEBUG SUMMARY")
    print("Debug information collection complete.")
    print("Common issues to check:")
    print("1. zstacklib not installed or in Python path")
    print("2. zstacklib.test module missing")
    print("3. Incorrect virtual environment")
    print("4. File permission issues")
    print("5. Symbolic link problems")


if __name__ == "__main__":
    main()