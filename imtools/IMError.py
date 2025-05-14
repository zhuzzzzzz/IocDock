class IMInitError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class IMValueError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class IMIOCError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
