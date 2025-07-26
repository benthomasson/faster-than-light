import os


class _Settings:

    def __init__(self):
        if os.path.exists(".env"):
            with open(".env") as f:
                for line in f.readlines():
                    key, _, value = line.partition("=")
                    value = value.strip()
                    setattr(self, key, value)


settings = _Settings()
