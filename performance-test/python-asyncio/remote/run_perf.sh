#!/bin/bash -e
ulimit -Sn 10000
#Argtest

../../scripts/perf_test.py x x x x --only-header
for t in argtest
do
for n in 1 10 100 1000
do
../../scripts/perf_test.py "ftl -i inventory_remote${n}.yml -M modules -m ${t}" ftl_remote ${t} ${n} --no-header
#../../scripts/perf_test.py "ftl -i inventory_remote${n}.yml -M ftl_modules -f ${t}" ftl_async_remote ${t} ${n} --no-header
done
done
