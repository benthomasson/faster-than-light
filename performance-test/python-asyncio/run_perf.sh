ulimit -Sn 10000
#Argtest

./perf_test.py x x x x --only-header
for t in argtest
do
for n in 1 10 100 1000
do
./perf_test.py "ftl -i inventory${n}.yml -M modules -m ${t}" ftl ${t} ${n} --no-header
./perf_test.py "ftl -i inventory${n}.yml -M ftl_modules -f ${t}" ftl_async ${t} ${n} --no-header
done
done
