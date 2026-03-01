from models.session import Session


def get_all_sessions():
    return Session.get_all()