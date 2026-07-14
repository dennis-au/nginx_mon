from nginx_mon.tailer import LogFollower


def test_follower_reads_each_complete_appended_line_once(tmp_path):
    log_file = tmp_path / "access.json.log"
    log_file.write_text('{"request":"first"}\n', encoding="utf-8")
    follower = LogFollower(log_file)

    assert follower.poll() == ['{"request":"first"}\n']
    assert follower.poll() == []

    with log_file.open("a", encoding="utf-8") as handle:
        handle.write('{"request":"second"}\n')

    assert follower.poll() == ['{"request":"second"}\n']


def test_follower_waits_for_a_partial_line_to_finish(tmp_path):
    log_file = tmp_path / "access.json.log"
    log_file.write_text('{"request":"partial"', encoding="utf-8")
    follower = LogFollower(log_file)

    assert follower.poll() == []

    with log_file.open("a", encoding="utf-8") as handle:
        handle.write("}\n")

    assert follower.poll() == ['{"request":"partial"}\n']


def test_follower_recovers_after_log_truncation_and_rotation(tmp_path):
    log_file = tmp_path / "access.json.log"
    log_file.write_text("old request\n", encoding="utf-8")
    follower = LogFollower(log_file)
    assert follower.poll() == ["old request\n"]

    log_file.write_text("new\n", encoding="utf-8")
    assert follower.poll() == ["new\n"]

    rotated_file = tmp_path / "access.json.log.1"
    log_file.rename(rotated_file)
    log_file.write_text("rotated\n", encoding="utf-8")

    assert follower.poll() == ["rotated\n"]
