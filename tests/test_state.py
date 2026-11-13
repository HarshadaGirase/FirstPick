from src.state import empty_state, load_state, mark_sent, save_state


def test_mark_sent_moves_issues_out_of_the_pool():
    state = empty_state()
    state["pool"] = {"a": {}, "b": {}, "c": {}}
    mark_sent(state, ["a"], {"closed": ["b"], "assigned": [], "linked_pr": [], "claimed": []})
    assert state["pool"] == {"c": {}}
    assert state["sent"] == ["a"]
    assert state["dropped"] == {"b": "closed"}


def test_save_and_load_round_trip(tmp_path):
    path = str(tmp_path / "state.json")
    state = empty_state()
    state["sent"].append("https://github.com/x/y/issues/1")
    save_state(state, path)
    assert load_state(path) == state


def test_old_state_file_gets_new_keys(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"pool": {}, "sent": [], "stats": []}')
    assert load_state(str(path))["dropped"] == {}
