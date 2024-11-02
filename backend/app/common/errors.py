class AggregateError(Exception):
    def __init__(self, *errors):
        self.errors = errors

    def __str__(self):
        return "\n".join(str(error) for error in self.errors)
