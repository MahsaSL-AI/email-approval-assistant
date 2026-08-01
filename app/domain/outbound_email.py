from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OutboundEmail:
    sender: str
    recipient: str
    subject: str
    body_text: str
    message_id: str
    in_reply_to: str
