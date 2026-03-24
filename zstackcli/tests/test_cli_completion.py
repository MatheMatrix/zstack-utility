"""
Tests for zstack-cli tab completion behavior.

Tests the REAL Cli.complete() method by constructing a Cli instance
with __new__ (skipping __init__) and setting only the attributes
that complete() depends on.

Verifies:
1. complete() calls completer_print on first match (index=0) when multiple matches exist
2. complete() does NOT call completer_print when only one match
3. complete() does NOT call completer_print on subsequent indices (index>0)
4. Substring matching (in) works correctly with case insensitivity
5. menu-complete returns full words (not suffixes) to avoid double-completion
"""
import sys
import types
import readline
from unittest.mock import MagicMock, patch

# Mock heavy dependencies before importing Cli
_MOCKED_MODULES = [
    'zstacklib', 'zstacklib.utils', 'zstacklib.utils.log',
    'zstacklib.utils.linux', 'zstacklib.utils.jsonobject',
    'zstacklib.utils.filedb',
    'apibinding', 'apibinding.inventory', 'apibinding.api',
    'zstackcli.parse_config', 'zstackcli.deploy_config',
    'zstackcli.read_config',
]

_saved = {}
for mod_name in _MOCKED_MODULES:
    _saved[mod_name] = sys.modules.get(mod_name)
    mock_mod = types.ModuleType(mod_name)
    # apibinding.inventory needs api_names and queryMessageInventoryMap
    if mod_name == 'apibinding.inventory':
        mock_mod.api_names = []
        mock_mod.queryMessageInventoryMap = {}
    # zstacklib.utils.log needs SENSITIVE_FIELD_NAME and configure_log
    if mod_name == 'zstacklib.utils.log':
        mock_mod.SENSITIVE_FIELD_NAME = 'password'
        mock_mod.configure_log = lambda *a, **kw: None
    sys.modules[mod_name] = mock_mod

from zstackcli.cli import Cli  # noqa: E402

# Restore original modules (if any) after import
for mod_name, original in _saved.items():
    if original is None:
        # leave mock in place so Cli methods can still reference it
        pass
    else:
        sys.modules[mod_name] = original


def make_cli(words_db):
    """Create a Cli instance without calling __init__, set fields for complete()."""
    cli = object.__new__(Cli)
    cli.words_db = list(words_db)
    cli.words = list(words_db)
    cli.cli_cmd = []
    cli.is_cmd = True
    cli.curr_pattern = None
    cli.matching_words = None
    cli.api_class_params = {}
    # Mock completer_print to track calls without terminal output
    cli.completer_print = MagicMock()
    return cli


@patch.object(readline, 'get_line_buffer')
class TestCompletionDisplay:
    """Test that completer_print is called correctly from complete()."""

    def test_multiple_matches_shows_list_on_first_index(self, mock_buf):
        mock_buf.return_value = 'QueryModelSer'
        cli = make_cli(['QueryModelService', 'QueryModelServiceInstanceGroup'])

        result = cli.complete('QueryModelSer', 0)

        assert result == 'QueryModelService '
        cli.completer_print.assert_called_once()
        args = cli.completer_print.call_args[0]
        assert args[0] == 'QueryModelSer'
        assert len(args[1]) == 2

    def test_multiple_matches_no_list_on_subsequent_index(self, mock_buf):
        mock_buf.return_value = 'QueryModelSer'
        cli = make_cli(['QueryModelService', 'QueryModelServiceInstanceGroup'])

        cli.complete('QueryModelSer', 0)
        cli.completer_print.reset_mock()
        result = cli.complete('QueryModelSer', 1)

        assert result == 'QueryModelServiceInstanceGroup '
        cli.completer_print.assert_not_called()

    def test_single_match_no_list(self, mock_buf):
        mock_buf.return_value = 'QueryZon'
        cli = make_cli(['QueryZone'])

        result = cli.complete('QueryZon', 0)

        assert result == 'QueryZone '
        cli.completer_print.assert_not_called()

    def test_no_match_returns_none(self, mock_buf):
        mock_buf.return_value = 'XyzNotExist'
        cli = make_cli(['QueryZone'])

        result = cli.complete('XyzNotExist', 0)

        assert result is None
        cli.completer_print.assert_not_called()

    def test_index_out_of_range_returns_none(self, mock_buf):
        mock_buf.return_value = 'QueryZon'
        cli = make_cli(['QueryZone'])

        result = cli.complete('QueryZon', 1)

        assert result is None


@patch.object(readline, 'get_line_buffer')
class TestSubstringMatching:
    """Test that substring matching (in) works correctly."""

    def test_substring_match_finds_inner_matches(self, mock_buf):
        """Typing 'Vm' should match QueryVmInstance, StartVmInstance, etc."""
        mock_buf.return_value = 'Vm'
        cli = make_cli([
            'QueryVmInstance', 'StartVmInstance', 'StopVmInstance', 'QueryZone'
        ])

        matches = []
        for i in range(10):
            result = cli.complete('Vm', i)
            if result is None:
                break
            matches.append(result.strip())

        assert 'QueryVmInstance' in matches
        assert 'StartVmInstance' in matches
        assert 'StopVmInstance' in matches
        assert 'QueryZone' not in matches

    def test_case_insensitive_matching(self, mock_buf):
        mock_buf.return_value = 'loginby'
        cli = make_cli(['LogInByAccount', 'LogInByLdap', 'LoginByCas'])

        matches = []
        for i in range(10):
            result = cli.complete('loginby', i)
            if result is None:
                break
            matches.append(result.strip())

        assert len(matches) == 3
        assert 'LogInByAccount' in matches
        assert 'LoginByCas' in matches


@patch.object(readline, 'get_line_buffer')
class TestMenuCompleteNoDoubleCompletion:
    """
    Verify the fix for the double-completion bug.

    The bug: show-all-if-ambiguous extends common prefix (appends "vice"),
    then menu-complete also inserts first match (appends "vice" again).

    The fix: complete() manually calls completer_print (stdout only, no
    buffer modification). menu-complete alone handles buffer replacement.
    """

    def test_matches_returned_are_full_words(self, mock_buf):
        """complete() returns full match words, not partial suffixes."""
        mock_buf.return_value = 'QueryModelSer'
        cli = make_cli(['QueryModelService', 'QueryModelServiceInstanceGroup'])

        match0 = cli.complete('QueryModelSer', 0)
        match1 = cli.complete('QueryModelSer', 1)

        assert match0 == 'QueryModelService '
        assert match1 == 'QueryModelServiceInstanceGroup '

    def test_loginby_case_inconsistency(self, mock_buf):
        """LogInBy* and LoginByCas have different casing but should all match."""
        mock_buf.return_value = 'LogInBy'
        cli = make_cli([
            'LogInByAccount', 'LogInByLdap', 'LogInByUser', 'LoginByCas'
        ])

        matches = []
        for i in range(10):
            result = cli.complete('LogInBy', i)
            if result is None:
                break
            matches.append(result.strip())

        assert len(matches) == 4
        assert 'LoginByCas' in matches
        assert 'LogInByAccount' in matches

    def test_completer_print_receives_correct_args(self, mock_buf):
        """completer_print should receive (pattern, matches, max_length)."""
        mock_buf.return_value = 'LogInBy'
        cli = make_cli([
            'LogInByAccount', 'LogInByLdap', 'LogInByUser', 'LoginByCas'
        ])

        cli.complete('LogInBy', 0)

        cli.completer_print.assert_called_once()
        pattern, matches, max_len = cli.completer_print.call_args[0]
        assert pattern == 'LogInBy'
        assert len(matches) == 4
        assert max_len == max(len(m) for m in matches)
