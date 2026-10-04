"""Test configuration for the whole suite.

The API rate limiter is switched off here so the many in-process requests the tests make are not
throttled. The rate-limit tests set their own limit explicitly. Servers started by the end-to-end
tests inherit this too.
"""
import os

os.environ.setdefault("MIRROR_RATE_LIMIT_PER_MINUTE", "0")
