class AnonymousUser:
    id = None
    is_active = False
    is_superuser = False
    username = ''

    def __str__(self):
        return 'AnonymousUser'

    def __eq__(self, other):
        return isinstance(other, self.__class__)

    def __hash__(self):
        return 1  # instances always return the same hash value

    def __bool__(self):
        return False

    @property
    def is_anonymous(self):
        return True

    @property
    def is_authenticated(self):
        return False

    def save(self):
        raise NotImplementedError("Anthill doesn't provide a DB representation for AnonymousUser.")

    def delete(self):
        raise NotImplementedError("Anthill doesn't provide a DB representation for AnonymousUser.")

    def set_password(self, raw_password):
        raise NotImplementedError("Anthill doesn't provide a DB representation for AnonymousUser.")

    def check_password(self, raw_password):
        raise NotImplementedError("Anthill doesn't provide a DB representation for AnonymousUser.")

    def get_username(self):
        return self.username
