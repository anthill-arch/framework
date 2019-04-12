from anthill.framework.db import db


class AbstractBaseSession(db.Model):
    __abstract__ = True

    session_key = db.Column(db.String(40), unique=True, primary_key=True)
    session_data = db.Column(db.Text, nullable=False)
    expire_date = db.Column(db.DateTime, nullable=False, index=True)

    def __str__(self):
        return self.session_key

    @classmethod
    def get_session_store_class(cls):
        raise NotImplementedError

    def get_decoded(self):
        session_store_class = self.get_session_store_class()
        return session_store_class().decode(self.session_data)
