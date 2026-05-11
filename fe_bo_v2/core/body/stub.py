import logging

class BodyStub:
    def __init__(self):
        self.log = logging.getLogger("FeBo.Body")
        self.position = (0,0)
    def move_to(self, x, y):
        self.log.info(f"Move to ({x},{y})")
        self.position = (x,y)
    def speak(self, text):
        self.log.info(f"Speak: {text[:50]}")
    def look_at(self, direction):
        self.log.info(f"Look at {direction}")

body = BodyStub()
