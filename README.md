# Local CI Watcher

Live web view of a self-hosted GitHub Actions runner. Shows recent jobs, step results, and live step output.

It reads the runner's `_diag` logs. No dependencies beyond Python 3.8+.

## Usage

Run on the machine where the runner lives

```
python3 watcher.py --runner-dir /home/runner/actions-runner --port 8765
```

Then open http://127.0.0.1:8765.

| Option | Default |
| --- | --- |
| `--runner-dir` | `/home/runner/actions-runner` |
| `--port` | `8765` |

The server binds to `127.0.0.1` only.

## Tests

```
python3 test_watcher.py
```

## How it works

`watcher.py` polls `Worker_*.log` and `pages/*.log` in the runner's `_diag` folder once per second, parses job, step, and result lines, and pushes updates to the page over server-sent events. The page is `index.html`. The watcher keeps the last 20 runs in memory.
