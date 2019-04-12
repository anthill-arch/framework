from anthill.framework.db import db
from anthill.framework.utils import timezone
from anthill.framework.utils.asynchronous import as_future
import binascii
import os


class Token(db.Model):
    """
    The default authorization token model.
    """
    __tablename__ = 'tokens'

    key = db.Column(db.String(40), primary_key=True)
    created = db.Column(db.DateTime, nullable=False, default=timezone.now)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False, unique=False)
    user = relationship('User', backref='tokens', cascade="all, delete-orphan")

    async def save(self, *args, **kwargs):
        if not self.key:
            self.key = await self.generate_key()
        super().save(*args, **kwargs)

    # noinspection PyMethodMayBeStatic
    @as_future
    def generate_key(self):
        return binascii.hexlify(os.urandom(20)).decode()

    def __str__(self):
        return self.key
