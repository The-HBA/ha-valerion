# Contributing

Thank you for helping make Valerion projectors work better with Home Assistant.

## Testing your projector model

All testing so far was done on a VisionMaster Pro2. If you own another model, [Help test your projector](docs/help-test.md) lists tests that run entirely in Home Assistant, from easy to advanced.

## Reporting a problem

Open an issue with the bug report template. Please attach the integration diagnostics (device page > three dots > Download diagnostics) and, when it is a protocol question, the output of the command line tool (see below). Never paste your security code.

## Testing against a projector

The protocol library can be exercised without Home Assistant. From the repository root:

```bash
python scripts/awollink.py --host 192.168.1.50 probe
python scripts/awollink.py --host 192.168.1.50 query POWR
python scripts/awollink.py --host 192.168.1.50 survey -o survey-pro2.json
```

`survey` runs every documented query once and records the raw replies with timings. If you own a model that is not listed as tested in the README, a survey file attached to an issue is the most useful contribution you can make.

## Development setup

```bash
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements_dev.txt
ruff format . && ruff check .
mypy
pytest
```

Home Assistant level tests need Linux and their own environment, see `docs/testing.md`.

The folder `custom_components/valerion/lib` must stay free of Home Assistant imports; a test enforces this so the library can be published on its own later.

## Pull requests

- One topic per pull request, with a short description of what changed and how it was verified (which projector model and firmware).
- Keep the official command list as the source of truth for command codes and values. Undocumented commands need a note in `docs/protocol.md` describing how they were discovered and on which firmware they worked.
- Run the linters and tests before pushing; CI runs the same checks plus the Home Assistant hassfest and HACS validations.
