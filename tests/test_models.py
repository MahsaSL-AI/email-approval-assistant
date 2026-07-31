from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models.email import EmailAnalysis, EmailMessage, SuggestedReply


def test_external_message_id_is_unique() -> None:
    constraints = EmailMessage.__table__.constraints

    assert any(
        isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns] == ["external_message_id"]
        for constraint in constraints
    )


def test_each_email_has_at_most_one_analysis() -> None:
    constraints = EmailAnalysis.__table__.constraints

    assert any(
        isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns] == ["email_id"]
        for constraint in constraints
    )


def test_each_email_has_at_most_one_suggested_reply() -> None:
    constraints = SuggestedReply.__table__.constraints

    assert any(
        isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns] == ["email_id"]
        for constraint in constraints
    )


def test_analysis_confidence_is_bounded() -> None:
    constraints = EmailAnalysis.__table__.constraints

    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_email_analyses_confidence_range"
        for constraint in constraints
    )


def test_all_email_children_cascade_on_delete() -> None:
    child_tables = [EmailAnalysis.__table__, SuggestedReply.__table__]

    for table in child_tables:
        foreign_key = next(iter(table.foreign_keys))
        assert foreign_key.ondelete == "CASCADE"
