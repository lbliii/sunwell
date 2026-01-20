class EchoProtocol:
    def __init__(self):
        self.message = None

    def send(self, message):
        self.message = message

    def receive(self):
        if self.message is not None:
            return self.message
        else:
            return None