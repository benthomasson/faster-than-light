ulimit -Sn 10000
#Argtest

../../scripts/perf_test.py x x x x --only-header
for t in argtest
do
for n in 1 10 100 1000 10000
do
#../../scripts/perf_test.py "ftl -i inventory${n}.yml -M modules -m ${t}" ftl ${t} ${n} --no-header
../../scripts/perf_test.py "ftl -i inventory${n}.yml -M ftl_modules -f ${t}" ftl_async ${t} ${n} --no-header
done
done
