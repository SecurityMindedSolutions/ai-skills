"""Retention jobs (fictional)."""
import logging
import boto3

log = logging.getLogger(__name__)
s3 = boto3.client("s3")


def purge_org_files(bucket: str, keys: list[str]) -> None:
    """VULN unsafe_deletion: the batch response's per-key errors are never read."""
    for i in range(0, len(keys), 1000):
        s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in keys[i:i + 1000]]})
    log.info("purged %d keys from %s", len(keys), bucket)


def purge_org_files_checked(bucket: str, keys: list[str]) -> list[str]:
    """CLEAN: partial failures are collected and returned."""
    failed: list[str] = []
    for i in range(0, len(keys), 1000):
        resp = s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in keys[i:i + 1000]]})
        failed.extend(e["Key"] for e in resp.get("Errors", []))
    if failed:
        raise RuntimeError(f"{len(failed)} keys not deleted")
    return failed
