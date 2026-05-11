class PolyvagalSimulator:
    def __init__(self):
        self.state = "ventral_vagal"  # safe social engagement
    def update(self, threat_detected):
        if threat_detected:
            self.state = "sympathetic"  # fight/flight
        else:
            self.state = "ventral_vagal"
    def get_state(self):
        return self.state
