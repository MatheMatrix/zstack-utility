import re


class NumericVersion(object):
    """Version comparison that extracts only numeric segments.

    Based on distutils.version.LooseVersion parsing logic, but filters
    out non-numeric segments to avoid Python 3 int vs str TypeError.

    e.g., '5.2.0-8.el8' -> (5, 2, 0, 8, 8), '2.a.1' -> (2, 1)
    """

    component_re = re.compile(r'(\d+|[a-z]+|\.)', re.VERBOSE)

    def __init__(self, vstring):
        self.vstring = str(vstring)
        components = [x for x in self.component_re.split(self.vstring) if x and x != '.']
        self.version = tuple(int(x) for x in components if x.isdigit())

    def _pad(self, other):
        if isinstance(other, str):
            other = NumericVersion(other)
        elif not isinstance(other, NumericVersion):
            return NotImplemented
        maxlen = max(len(self.version), len(other.version))
        a = self.version + (0,) * (maxlen - len(self.version))
        b = other.version + (0,) * (maxlen - len(other.version))
        return a, b

    def __lt__(self, other):
        pair = self._pad(other)
        return NotImplemented if pair is NotImplemented else pair[0] < pair[1]

    def __le__(self, other):
        pair = self._pad(other)
        return NotImplemented if pair is NotImplemented else pair[0] <= pair[1]

    def __gt__(self, other):
        pair = self._pad(other)
        return NotImplemented if pair is NotImplemented else pair[0] > pair[1]

    def __ge__(self, other):
        pair = self._pad(other)
        return NotImplemented if pair is NotImplemented else pair[0] >= pair[1]

    def __eq__(self, other):
        pair = self._pad(other)
        return NotImplemented if pair is NotImplemented else pair[0] == pair[1]

    def __ne__(self, other):
        pair = self._pad(other)
        return NotImplemented if pair is NotImplemented else pair[0] != pair[1]

    def __repr__(self):
        return 'NumericVersion(%r)' % self.vstring

    def __str__(self):
        return self.vstring
