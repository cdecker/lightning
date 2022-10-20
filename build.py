# Simple script to build a given version
import os
import sys
from pathlib import Path

import sh
from sh import bash, git, make, tar
import tempfile

if len(sys.argv) == 2:
    # Override the version from the CLI (used by CI)
    branch = sys.argv[1]
else:
    # Get the current branch, we'll use it as a tag too:
    branch = git('branch', '--show-current').strip()

print(f"Building version {branch}")

# Delete any existing tag, so we can tag it according to our version
# branch instead.
git('tag', '-d', branch, _ok_code=[0, 1])

# Now create the annotated tag, so the build script recognizes it
# later.
git('tag', '-a', '-m', branch, branch)

# Now ensure that this gets recognized correctly:
head = git("rev-parse", "HEAD").strip()
tag = git("describe", "--always", "--dirty=-modded", "--abbrev=7").strip()

print(f"Repo is at commit {head} with tag {tag}")
assert tag == branch

# Need to unset this variable otherwise the Makefile points to the
# wrong directory
os.environ.pop("CARGO_TARGET_DIR", None)

make(
    "clean",
    _out=sys.stdout,
    _err=sys.stderr,
    _ok_code=[0, 2],
)

bash(
    "./configure",
    "--enable-developer",
    "--disable-valgrind",
    "--enable-experimental-features",
    _out=sys.stdout,
    _err=sys.stderr,
)

make(
    f"-j{os.cpu_count()}",
    _out=sys.stdout,
    _err=sys.stderr
)

# Now install the tarball contents in `cln-versions/{VERSION}`
make(
    f"DESTDIR=cln-versions/{branch}",
    "install",
    _out=sys.stdout,
    _err=sys.stderr
)

tar(
    "-cvjf",
    f"../../lightningd-{branch}.tar.bz2",
    f".",
    _out=sys.stdout,
    _err=sys.stderr,
    _cwd=f"cln-versions/{branch}",

)

# And the node must self-identify as the desired version too
ld = sh.Command(f"cln-versions/{branch}/usr/local/bin/lightningd")
comp_version = ld("--version").strip()
assert comp_version == branch
