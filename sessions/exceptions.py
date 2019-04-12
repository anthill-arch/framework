from anthill.framework.core.exceptions import SuspiciousOperation


class InvalidSessionKey(SuspiciousOperation):
    """Invalid characters in session key."""


class SuspiciousSession(SuspiciousOperation):
    """The session may be tampered with."""
