"""CLEAN (test code): looks vulnerable, is a test."""
import subprocess


def test_convert_shell():
    subprocess.run("echo test", shell=True, check=True)
    assert True
