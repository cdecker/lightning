#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#     "sh",
#     "google-cloud-storage",
#     "grpcio-tools==1.69.0",
#     "mako",
#     "packaging",
#     "click",
#     "rich"
# ]
# ///
# Simple script to build a given version
from datetime import datetime
import os
import sys
import json
from pathlib import Path
from google.cloud import storage
from google.oauth2.service_account import Credentials
import click
from rich.logging import RichHandler
from rich.pretty import pprint
import logging
import tempfile
import logging
import re

import sh
from sh import bash, git, make, tar, sha256sum, cargo, uv

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
)
logging.getLogger("sh").setLevel(logging.ERROR)


@click.group()
def cli():
    pass


@cli.command()
@click.argument("branch", type=str)
def build(branch: str | None):
    DIR = f"cln-versions/{branch}"

    print(f"Building version {branch}")

    # Delete any existing tag, so we can tag it according to our version
    # branch instead.
    git("tag", "-d", branch, _ok_code=[0, 1])

    # Now create the annotated tag, so the build script recognizes it
    # later.
    git("tag", "-a", "-m", branch, branch)

    # Now ensure that this gets recognized correctly:
    head = git("rev-parse", "HEAD").strip()
    tag = git("describe", "--always", "--dirty=-modded", "--abbrev=7").strip()

    print(f"Repo is at commit {head} with tag {tag}")

    # Need to unset this variable otherwise the Makefile points to the
    # wrong directory
    os.environ.pop("CARGO_TARGET_DIR", None)

    # Build Rust artifacts in release mode
    os.environ["CARGO_CFG_RELEASE"] = "1"
    os.environ["RUST_PROFILE"] = "release"

    make(
        "clean",
        _out=sys.stdout,
        _err=sys.stderr,
        _ok_code=[0, 2],
    )

    os.system(".venv/bin/python3 -m pip install grpcio-tools")

    git("reset", "--hard")
    bash(
        "./configure",
        "--disable-valgrind",
        "--enable-static",
        _out=sys.stdout,
        _err=sys.stderr,
    )

    # Master branch uses uv instead of make directly
    if branch[0] != "v":
        uv(
            "run",
            "--with",
            "mako",
            "make",
            f"-j{os.cpu_count()}",
            _out=sys.stdout,
            _err=sys.stderr,
        )
    else:
        make(
            f"-j{os.cpu_count()}",
            _out=sys.stdout,
            _err=sys.stderr,
        )

    # Now install the tarball contents in `cln-versions/{VERSION}`
    make(f"DESTDIR=cln-versions/{branch}", "install", _out=sys.stdout, _err=sys.stderr)

    print("=" * 20 + "cargo build cln-lsps-client" + "=" * 20)
    cargo("build", "--release", "--bin", "cln-lsps-client")
    os.system("cargo build --release --bin cln-lsps-client")

    # Build a manifest for us to know what we deployed
    root = Path(DIR)
    files = root.glob("**/*")
    shasum = [(str(f), sha256sum(f).split(" ")[0]) for f in files if f.is_file()]
    manipath = root / "manifest.json"
    manifest = {
        "sha256sums": shasum,
        "compilation_time": datetime.utcnow().isoformat(),
        "version": branch,
        "commit": git("rev-parse", "HEAD"),
    }

    print(json.dumps(manifest, indent=2))
    with open(manipath, "w") as f:
        json.dump(manifest, f, sort_keys=True, indent=2)

        filename = f"lightningd-{branch}.tar.bz2"
        tar(
            "-cvjf",
            f"../../{filename}",
            "usr",
            "manifest.json",
            _out=sys.stdout,
            _err=sys.stderr,
            _cwd=f"cln-versions/{branch}",
        )

        # And the node must self-identify as the desired version too
        ld = sh.Command(f"cln-versions/{branch}/usr/local/bin/lightningd")
        comp_version = ld("--version").strip()
        print(f"Compiled version {comp_version}, expected {branch}")
        print(git("--no-pager", "diff", "--text"))

        print(comp_version, branch)
        assert comp_version == branch


@cli.command()
@click.argument("filename", type=str)
def upload(filename: str):
    service_acc = Path("ci-service-account.json")
    assert service_acc.exists()
    bucket = "greenlight-artifacts"
    print(f"Uploading CLN version {filename} to gs://{bucket}/cln/{filename}")

    credentials = Credentials.from_service_account_file(service_acc)
    client = storage.Client(credentials=credentials, project="c-lightning")
    bucket = client.bucket(bucket)
    blob = bucket.blob(f"cln/{filename}")
    blob.upload_from_filename(filename)


@cli.command()
def genmanifest():
    """Download all available versions, summarize and sign them, then
    upload the manifest for clients to verify their authenticity.

    """
    service_acc = Path("ci-service-account.json")
    assert service_acc.exists()
    bucket = "greenlight-artifacts"
    credentials = Credentials.from_service_account_file(service_acc)
    client = storage.Client(credentials=credentials, project="c-lightning")
    bucket = client.bucket(bucket)
    blobs = bucket.list_blobs(prefix="cln")
    d = tempfile.TemporaryDirectory()
    dd = Path(d.name)
    data = {"versions": {}}
    for blob in blobs:
        logging.info(f"Downloading {blob.name} to {dd}")
        if blob.name.startswith("cln/"):
            name = blob.name[4:]
        else:
            # Not a `cln/` entry
            continue
        blob.download_to_filename(dd / name)
        s = sha256sum(dd / name).strip().split(" ")[0]
        matches = re.search(r"v\d+\.\d+\.?\d*[g]?[l]?\d*", name)
        if not matches:
            logging.warning(f"No version substring in {name}, ignoring")
            continue
        version = matches[0]
        data["versions"][version] = {
            "filename": name,
            "sha256": s,
            "md5": blob.md5_hash,
            "size": blob.size,
            "mtime": blob.updated,
        }
        pprint(data["versions"][version])
    d.cleanup()
    with Path("manifest.json").open(mode="w") as f:
        json.dump(data, f, indent=2, sort_keys=True, default=str)
    blob = bucket.blob(f"cln/manifest.json")
    blob.upload_from_filename("manifest.json")


if __name__ == "__main__":
    cli()
