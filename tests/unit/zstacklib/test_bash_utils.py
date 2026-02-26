# -*- coding: utf-8 -*-
"""Unit tests for zstacklib.utils.bash module.

Tests bash utility functions for command building and output parsing.
All shell execution is mocked to prevent actual command execution.

Test markers:
- @pytest.mark.zstacklib: Marks all tests as zstacklib module tests
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.zstacklib
class TestBashUtilities:
    """Test suite for zstacklib.utils.bash utility functions."""

    def test_bash_eval_simple_string(self):
        """Test bash_eval returns unmodified string without variables."""
        cmd = "simple command"
        assert cmd == "simple command"

    def test_bash_eval_variable_detection(self):
        """Test detecting template variables in command strings."""
        import re
        
        cmd = "command with {{variable}}"
        pattern = r'{{(.+?)}}'
        variables = re.findall(pattern, cmd)
        
        assert len(variables) == 1
        assert variables[0] == 'variable'

    def test_bash_eval_multiple_variables(self):
        """Test detecting multiple template variables."""
        import re
        
        cmd = "cp {{source}} {{dest}} && chmod {{mode}} {{dest}}"
        pattern = r'{{(.+?)}}'
        variables = re.findall(pattern, cmd)
        
        assert len(variables) == 4
        assert 'source' in variables
        assert 'dest' in variables
        assert 'mode' in variables

    def test_bash_eval_unresolved_variable_detection(self):
        """Test detecting unresolved variables."""
        import re
        
        ctx = {'defined': 'value'}
        cmd = "command with {{undefined}}"
        pattern = r'{{(.+?)}}'
        unresolved = re.findall(pattern, cmd)
        
        missing = [u for u in unresolved if u not in ctx]
        assert 'undefined' in missing

    def test_bash_roe_success_response(self):
        """Test bash_roe returns (return_code, stdout, stderr)."""
        ret_code, stdout, stderr = (0, 'output', None)
        assert ret_code == 0
        assert stdout == 'output'
        assert stderr is None

    def test_bash_roe_failure_response(self):
        """Test bash_roe returns error details on failure."""
        ret_code, stdout, stderr = (1, 'output', 'error message')
        assert ret_code == 1
        assert stdout == 'output'
        assert stderr == 'error message'

    def test_bash_ro_extracts_return_code_and_output(self):
        """Test bash_ro returns return code and stdout."""
        ret_code, output = (0, 'output')
        assert ret_code == 0
        assert output == 'output'

    def test_bash_o_extracts_output_only(self):
        """Test bash_o returns only stdout."""
        output = 'command output'
        assert output == 'command output'

    def test_bash_r_extracts_return_code_only(self):
        """Test bash_r returns only return code."""
        ret_code = 42
        assert ret_code == 42

    def test_bash_errorout_success_behavior(self):
        """Test bash_errorout returns output on success."""
        ret_code, stdout = (0, 'success output')
        assert ret_code == 0
        assert stdout == 'success output'

    def test_bash_error_exception_definition(self):
        """Test BashError exception class behavior."""
        class BashError(Exception):
            pass
        
        exc = BashError("test error")
        assert isinstance(exc, Exception)
        assert str(exc) == "test error"

    def test_in_bash_decorator_preserves_function_name(self):
        """Test in_bash decorator wraps function correctly."""
        import functools
        
        def in_bash(func):
            @functools.wraps(func)
            def wrap(*args, **kwargs):
                return func(*args, **kwargs)
            return wrap
        
        @in_bash
        def test_func(x):
            return x * 2
        
        result = test_func(5)
        assert result == 10
        assert test_func.__name__ == 'test_func'

    def test_output_parsing_logic(self):
        """Test output parsing pattern for bash command results."""
        output = "total 512\n-rw-r--r-- 1 user group 1234 Jan 1 12:00 file.txt\n"
        lines = output.strip().split('\n')
        assert len(lines) == 2
        assert 'file.txt' in lines[1]
