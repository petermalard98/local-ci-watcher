"""Parser check against snippets copied from real runner _diag logs. Run: python3 test_watcher.py"""
from watcher import new_job, parse_lines

LOG = """\
  "jobDisplayName": "check",
          "k": "ref",
          "v": "refs/heads/main"
          "k": "sha",
          "v": "a20e6342a7f81bfcda9da260c97b39996968d081"
          "k": "repository",
          "v": "octocat/example-repo"
          "k": "run_id",
          "v": "42682068594"
[2026-10-11 16:11:11Z INFO StepsRunner] Processing step: DisplayName='Run actions/checkout@v4'
[2026-10-11 16:11:11Z INFO StepsRunner] No need for updating job result with current step result 'Succeeded'.
[2026-10-11 16:11:17Z INFO StepsRunner] Processing step: DisplayName='Tests'
[2026-10-11 16:12:51Z INFO StepsRunner] Update job result with current step result 'Failed'.
[2026-10-11 16:12:51Z INFO StepsRunner] Processing step: DisplayName='Pack'
[2026-10-11 16:12:51Z INFO StepsRunner] No need for updating job result with current step result 'Skipped'.
[2026-10-11 16:12:51Z INFO StepsRunner] Processing step: DisplayName='Export'
"""
TAIL = """\
[2026-10-11 16:12:51Z INFO StepsRunner] No need for updating job result with current step result 'Skipped'.
[2026-10-11 16:12:51Z INFO JobRunner] Job result after all job steps finish: Failed
"""


def test():
    job, state = new_job("Worker_x.log"), {}
    parse_lines(job, LOG.splitlines(), state)
    assert job["name"] == "check"
    assert job["repository"] == "octocat/example-repo"
    assert job["ref"] == "refs/heads/main"
    assert job["url"] == "https://github.com/octocat/example-repo/actions/runs/42682068594"
    assert job["status"] == "running"
    assert job["steps"][-1] == {"name": "Export", "result": "running"}
    parse_lines(job, TAIL.splitlines(), state)  # incremental feed
    assert [s["result"] for s in job["steps"]] == ["succeeded", "failed", "skipped", "skipped"]
    assert job["status"] == "failed"


if __name__ == "__main__":
    test()
    print("ok")
