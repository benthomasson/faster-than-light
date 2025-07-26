import os
from subprocess import check_output

HERE = os.path.dirname(os.path.abspath(__file__))


def test1():
    os.chdir(HERE)
    output = check_output("ansible -i inventory.yml -m ping all".split(" "))
    print(output.decode())
    assert output


def test2():
    os.chdir(HERE)
    output = check_output(
        "ansible -M modules -i inventory.yml -m timetest all".split(" ")
    )
    print(output.decode())
    assert output


def test3():
    os.chdir(HERE)
    output = check_output(
        "ansible -M modules -i inventory.yml -m argtest all".split(" ")
    )
    print(output.decode())
    assert output
