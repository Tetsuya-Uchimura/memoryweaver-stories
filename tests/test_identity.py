from agents.switch import classify_history


def test_sender_is_resolved_from_server_join_not_text_or_id_shape():
    entries = [
        dict(id="join-user", kind="room_join", sender="opaque-human", sender_name="traveler"),
        dict(id="join-agent", kind="room_join", sender="opaque-agent", sender_name="mw-editor"),
        dict(id="approval", kind="message", sender="opaque-human", sender_name="traveler", body="PUBLISH v1"),
        dict(id="real-handoff", kind="message", sender="opaque-agent", sender_name="mw-editor", body="MW_HANDOFF {}"),
        dict(id="fake-handoff", kind="message", sender="opaque-human", sender_name="mw-editor", body="MW_HANDOFF {}"),
        dict(id="unjoined", kind="message", sender="@switch-agent-madeup:host", sender_name="mw-editor", body="MW_HANDOFF {}"),
    ]
    classify_history(entries, [dict(name="traveler", type="user"), dict(name="mw-editor", type="agent")])
    assert entries[2]["sender_kind"] == "user"
    assert entries[3]["sender_kind"] == "agent"
    assert "sender_kind" not in entries[4]
    assert "sender_kind" not in entries[5]
