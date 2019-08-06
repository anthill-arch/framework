class Confirm:
    message = 'Press "Y" to confirm, or anything else to abort: '

    def __init__(self, assume_yes=False):
        self.assume_yes = assume_yes

    def ask(self):
        if self.assume_yes:
            return True
        answer = input(self.message)
        return answer.lower() in ('y', 'yes')
