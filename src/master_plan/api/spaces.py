"""DigitalOcean Spaces (S3-compatible) write-through mirror for the JSON stores.

App Platform service disks are ephemeral, so the file-based stores would lose
their data on every deploy/restart. When Spaces is configured, each JSON store
is mirrored to a Spaces object:

* **on boot** — :meth:`SpacesMirror.sync_down` downloads each object to its
  local path *before* the repositories read it;
* **on write** — a post-write hook (registered in :mod:`_io`) re-uploads the
  file after every atomic local write.

This keeps the repositories unchanged — they still read/write local files — and
confines all remote I/O to this module. It is a single-writer design: the same
``instance_count: 1`` constraint as the plain local-file store applies, because
two writers would race on the same objects.

Configuration (all required to enable; unset ⇒ mirror disabled):

* ``MASTER_PLAN_SPACES_BUCKET``   — Space (bucket) name
* ``MASTER_PLAN_SPACES_ENDPOINT`` — e.g. ``https://nyc3.digitaloceanspaces.com``
* ``MASTER_PLAN_SPACES_KEY``      — Spaces access key id
* ``MASTER_PLAN_SPACES_SECRET``   — Spaces secret access key

Optional:

* ``MASTER_PLAN_SPACES_REGION``   — defaults to ``us-east-1`` (Spaces ignores
  the value but boto3 requires one)
* ``MASTER_PLAN_SPACES_PREFIX``   — key prefix, e.g. ``master-plan/``
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_REQUIRED_ENV = (
    "MASTER_PLAN_SPACES_BUCKET",
    "MASTER_PLAN_SPACES_ENDPOINT",
    "MASTER_PLAN_SPACES_KEY",
    "MASTER_PLAN_SPACES_SECRET",
)


def is_configured() -> bool:
    """True when every required Spaces env var is present and non-empty."""
    return all(os.environ.get(key) for key in _REQUIRED_ENV)


def _is_not_found(error: Exception) -> bool:
    """True when a boto3 error means the object/bucket key does not exist yet."""
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return False
    code = str(response.get("Error", {}).get("Code", ""))
    return code in {"404", "NoSuchKey", "NoSuchBucket"}


class SpacesMirror:
    """Mirrors a fixed set of local JSON files to/from a Spaces bucket."""

    def __init__(self, client: Any, bucket: str, prefix: str = "") -> None:
        self._client = client
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        # Normalised local path (str) -> object key.
        self._keys: dict[str, str] = {}

    def _object_key(self, filename: str) -> str:
        return f"{self._prefix}/{filename}" if self._prefix else filename

    def add(self, local_path: str | Path) -> None:
        """Register a local file to mirror (keyed by its basename)."""
        path = Path(local_path)
        self._keys[str(path)] = self._object_key(path.name)

    @property
    def paths(self) -> list[str]:
        return list(self._keys)

    def sync_down(self) -> None:
        """Download each registered object to its local path, if it exists.

        A missing object (fresh Space) is not an error — the store simply starts
        empty and the first write creates the object.
        """
        for local, key in self._keys.items():
            try:
                obj = self._client.get_object(Bucket=self._bucket, Key=key)
            except Exception as error:  # noqa: BLE001 — re-raised unless 404
                if _is_not_found(error):
                    continue
                raise
            data = obj["Body"].read()
            target = Path(local)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

    def on_write(self, path: Path) -> None:
        """Post-write hook: upload ``path`` if it is a mirrored store."""
        key = self._keys.get(str(path))
        if key is None:
            return
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=path.read_bytes(),
            ContentType="application/json",
        )


def configure_from_env() -> SpacesMirror | None:
    """Build a :class:`SpacesMirror` from the environment, or ``None`` if unset."""
    if not is_configured():
        return None
    import boto3  # lazy: only needed when Spaces is actually enabled

    client = boto3.client(
        "s3",
        region_name=os.environ.get("MASTER_PLAN_SPACES_REGION", "us-east-1"),
        endpoint_url=os.environ["MASTER_PLAN_SPACES_ENDPOINT"],
        aws_access_key_id=os.environ["MASTER_PLAN_SPACES_KEY"],
        aws_secret_access_key=os.environ["MASTER_PLAN_SPACES_SECRET"],
    )
    return SpacesMirror(
        client,
        bucket=os.environ["MASTER_PLAN_SPACES_BUCKET"],
        prefix=os.environ.get("MASTER_PLAN_SPACES_PREFIX", ""),
    )
