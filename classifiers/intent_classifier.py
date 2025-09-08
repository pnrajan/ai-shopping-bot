from open_intent_classifier.model import IntentClassifier, OpenAiIntentClassifier, IntentClassifier
from constants import get_intent_labels
from settings import settings


class ClassifierInference:

    def predict(self, input_text: str, labels: list = None, **kwargs):
        pass


class IntentDetection(ClassifierInference):

    def __init__(self, classifier: str = 'default', **kwargs):
        self._classifier = self._get_classifier(classifier, **kwargs)
        self._model = kwargs.get('model', '')
        self._labels = kwargs.get('labels', get_intent_labels())

    @staticmethod
    def _get_classifier(provider: str = 'default', **kwargs):
        if provider == 'default':
            return IntentClassifier()
        if provider == 'openai':
            model_name = kwargs.get('openai_model', 'gpt-4o-mini')
            openai_key = settings.openai_apikey
            return OpenAiIntentClassifier(model_name=model_name, openai_api_key=openai_key)

    def predict(self, input_text: str, labels: list = None, **kwargs):
        self._classifier.predict(input_text, labels or self._labels)
