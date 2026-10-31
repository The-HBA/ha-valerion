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
pytest tests/ha
```

Without Home Assistant installed, `pytest` skips `tests/ha`.

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
