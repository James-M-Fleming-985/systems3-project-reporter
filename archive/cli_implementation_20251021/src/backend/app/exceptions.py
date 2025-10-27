class FeatureDisabledException(Exception):
    def __init__(self, feature: str):
        self.feature = feature
        super().__init__(f"Feature {feature} is disabled")