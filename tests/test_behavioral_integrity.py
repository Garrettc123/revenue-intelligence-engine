from rhns.revenue_governance.behavioral_integrity import BehavioralIntegrityGate


def test_false_scarcity_is_blocked():
    assert not BehavioralIntegrityGate.evaluate_message("Act now before it is gone.").allowed


def test_opted_out_recipient_is_blocked():
    assert not BehavioralIntegrityGate.evaluate_message("A relevant update.", opted_out=True).allowed


def test_plain_helpful_message_is_allowed():
    message = "I prepared a short workflow summary. If this is not useful, please let me know and I will not follow up."
    assert BehavioralIntegrityGate.evaluate_message(message).allowed
