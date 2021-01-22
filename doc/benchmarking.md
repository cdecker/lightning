# Benchmarking c-lightning

## Building an optimized c-lightning

In order to compare apples to apples we need to build c-lightning with
the same parameters across benchmark runs. The following environment
variables tell `./configure` and `make` to build an optimized
`lightningd`:

 - `DEVELOPER=0`: yhe developer mode contains a number of sanity
   checks that are not necessary in production.
 - `COMPAT=0` disables backward compatibility shims that are
   eventually going to be removed.
 - `EXPERIMENTAL_FEATURES=0` disables features whose specification is
   not finalized and may be changed without further notice.
 
The following command then will build this configuration:

```bash
export DEVELOPER=0
export COMPAT=0
export EXPERIMENTAL_FEATURES=0
./configure COPTFLAGS=-O3
make
```
 
## Running 

Like the compilation above we also need to tell the test runner that
we don't have the developer options, with `DEVELOPER=0`, the others
are picked up at runtime.

Since we don't want to benchmark the performance of our disks we chose
to use a RAM-disk instead with `TEST_DIR=/dev/shm`.

```bash
export DEVELOPER=0
export TEST_DIR=/dev/shm
pytest tests/benchmark.py --benchmark-autosave  --benchmark-compare
```

Don't worry if the benchmark takes a while to kick off, unless an
error is reported it just means that the slow polling of `bitcoind`
and slow gossip forwarding isn't done yet.

## Interpreting the results

Most benchmarks are just latency tests (answering the question "how
long does one operation take from start to finish"), however some
tests are throughput tests (identified as such by the name containing
`throughput`). Throughput tests are more interested in how many
concurrent executions can be run in a set interval. For these
throughput tests we modified the benchmark code to report reasonable
operations per second (OPS) figures, however the individual stats such
as min, max, stddev, etc are nothing more than a single datapoint, and
hence have little meaning. For throughput tests please consider only
the OPS column, not the others.
