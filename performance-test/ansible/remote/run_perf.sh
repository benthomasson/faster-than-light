ulimit -Sn 10000
#Argtest

../../scripts/perf_test.py x x x x --only-header
for t in argtest
do
for n in 1 10 100 1000
do
../../scripts/perf_test.py "ansible -M modules -i inventory_remote${n}.yml -m argtest all" ansible_remote ${t} ${n} --no-header
done
done
