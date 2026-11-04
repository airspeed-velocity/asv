# Licensed under a 3-clause BSD style license - see LICENSE.rst
from os.path import join

import pytest

from asv import config, machine

from . import tools


def test_machine(tmpdir):
    tmpdir = str(tmpdir)

    m = machine.Machine.load(
        interactive=False,
        machine="orangutan",
        os="BeOS",
        arch="MIPS",
        cpu="10 MHz",
        ram="640k",
        _path=join(tmpdir, 'asv-machine.json'),
    )

    m = machine.Machine.load(_path=join(tmpdir, 'asv-machine.json'), interactive=False)

    assert m.machine == 'orangutan'
    assert m.os == 'BeOS'
    assert m.arch == 'MIPS'
    assert m.cpu == '10 MHz'
    assert m.ram == '640k'


def test_machine_defaults(tmpdir):
    tmpdir = str(tmpdir)

    m = machine.Machine.load(
        interactive=True, use_defaults=True, _path=join(tmpdir, 'asv-machine.json')
    )

    assert m.__dict__ == m.get_defaults()


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"cpu": "CI CPU"},
        {"machine": "ci-runner"},
        {"os": "CI OS", "arch": "CI arch", "cpu": "CI CPU", "num_cpu": "2", "ram": "1GB"},
    ],
)
def test_machine_command_defaults(tmp_path, monkeypatch, overrides):
    path = str(tmp_path / "asv-machine.json")
    monkeypatch.setattr(machine.MachineCollection, "get_machine_file_path", lambda: path)
    defaults = machine.Machine.get_defaults()
    expected = {**defaults, **overrides}
    args = ["machine"]
    if not overrides:
        args.append("--yes")
    for name, value in expected.items():
        args.extend(["--" + name, value])

    tools.run_asv_with_conf(config.Config(), *args)

    assert machine.MachineCollection.load(expected["machine"], _path=path) == expected


def test_machine_overrides_preserve_saved_values(tmp_path):
    path = str(tmp_path / "asv-machine.json")
    saved = {
        "machine": "ci-runner",
        "os": "CI OS",
        "arch": "CI arch",
        "cpu": "CI CPU",
        "num_cpu": "2",
        "ram": "1GB",
    }
    machine.MachineCollection.save(saved["machine"], saved, _path=path)

    updated = machine.Machine.load(machine_name=saved["machine"], cpu="new CPU", _path=path)

    expected = {**saved, "cpu": "new CPU"}
    assert updated.__dict__ == expected
    assert machine.MachineCollection.load(saved["machine"], _path=path) == expected
