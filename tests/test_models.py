from burnbox.models import InboxMessage, MessagePreview


def test_inbox_message_fields():
    m = InboxMessage(id="1", sender="a@b", subject="hi", content="body")
    assert m.id == "1"
    assert m.sender == "a@b"
    assert m.subject == "hi"
    assert m.content == "body"


def test_inbox_message_immutable():
    m = InboxMessage(id="1", sender="a@b", subject="hi", content="body")
    try:
        m.id = "2"
        assert False, "Should raise FrozenInstanceError"
    except AttributeError:
        pass


def test_message_preview():
    p = MessagePreview(id="1", sender="x@y", subject="sub")
    assert p.subject == "sub"
