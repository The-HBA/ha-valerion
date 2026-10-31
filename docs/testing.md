# Testing

## Without a projector

```bash
pip install -r requirements_dev.txt
pytest
```

The library tests start a fake AWOL Link server on localhost that replays
scripted replies, so they run on any operating system.

## In Home Assistant, without a projector

These tests set up the integration in a test Home Assistant, against the
same fake server. Home Assistant runs on Linux only, so use a separate
virtual environment there (CI runs them in their own job):

```bash
pip install -r requirements_test_ha.txt
pytest tests/ha --cov=custom_components/valerion --cov-report=term-missing
```

Without Home Assistant installed, `pytest` skips `tests/ha`.

On Windows or macOS, Docker gives the same Linux environment:

```bash
docker run --rm -it -v "$PWD:/src" -w /src python:3.14-slim   sh -c "pip install -r requirements_test_ha.txt && pytest tests/ha -p no:cacheprovider"
```

| File | Covers |
| --- | --- |
| `test_config_flow.py` | Setup and settings dialogs |
| `test_init.py` | Setup, unload, removal, migration |
| `test_coordinator.py` | Polling, standby, power, locks, error messages |
| `test_<platform>.py` | Each entity type, plus a snapshot of its entities |
| `test_services.py` | *Send raw command* |
| `test_diagnostics.py` | Diagnostics download (snapshot) |

Snapshots live in `tests/ha/snapshots/`. After an intended change to an
entity or to the diagnostics, update them with `--snapshot-update` and
review the diff.

## Against a projector, without Home Assistant

The command line tool opens one short session per call, so other apps that
use AWOL Link keep working in between:

```bash
python scripts/awollink.py --host <ip> probe
python scripts/awollink.py --host <ip> query POWR
python scripts/awollink.py --host <ip> set LASL 5
python scripts/awollink.py --host <ip> raw "%3PICL ?"
python scripts/awollink.py --host <ip> survey -o survey-<model>.json
```

Add `--code <security code>` when one is set on the projector. The survey
file is the input for `docs/protocol.md` and for new test fixtures.

## Inside Home Assistant

1. Install the integration from this repository as a custom repository in
   HACS / the Marketplace, or copy `custom_components/valerion` into your
   configuration directory.
2. Restart Home Assistant and add the integration.
3. On the integration page, enable debug logging. The log then shows every
   line sent to and received from the projector.
4. Download the diagnostics from the device page when reporting a problem.
