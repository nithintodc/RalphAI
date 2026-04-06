from orchestrator.state_machine import OperatorState, transition


def test_happy_path():
    s = OperatorState.NEW
    s = transition(s, "start_deepdive")
    assert s == OperatorState.DEEPDIVE_RUNNING
    s = transition(s, "deepdive_complete")
    assert s == OperatorState.DEEPDIVE_DONE
