"""
Who may do what (single place to change the rules).

admin   = Django user with is_staff (superuser is the "super admin" who may also manage users)
judge   = Profile.role == 'judge'. Can edit results only for events where Event.judge == that user.
agent / sporter / visitor = read-only; they only see public data.
Anonymous (not logged in) = read-only public data (home medal table, events, athletes, results).
"""

ADMIN = 'admin'


def get_role(user):
    if not user.is_authenticated:
        return 'guest'
    if user.is_staff or user.is_superuser:
        return ADMIN
    profile = getattr(user, 'profile', None)
    return profile.role if profile else 'visitor'


def is_admin(user):
    return get_role(user) == ADMIN


def can_edit_results(user, event):
    """Requirement 4: administrators or (the assigned) judge may edit scores."""
    role = get_role(user)
    if role == ADMIN:
        return True
    return role == 'judge' and event.judge_id is not None and event.judge_id == user.id
