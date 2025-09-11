"""Intent Classification Module for Inflection Curator.

This module provides intelligent intent classification capabilities for the
personal shopping assistant. It can distinguish between shopping-related
conversations and general dialogue using various machine learning models,
including local BERT models and OpenAI's GPT models.

Example:
    >>> from inflection_curator.classifiers import IntentDetection
    >>> detector = IntentDetection(classifier='default')
    >>> result = detector.predict("I want to buy a new laptop")
    >>> print(result['label'])
    shopping_intent
"""

from typing import List, Dict, Any, Optional, Union
from abc import ABC, abstractmethod
from dataclasses_json import dataclass_json
from open_intent_classifier.model import (
    IntentClassifier,
    OpenAiIntentClassifier,
)
from ..constants import get_intent_labels, IntentLabels
from ..settings import settings
from dataclasses import dataclass, field


@dataclass_json
@dataclass
class IntentClassifierResponse:
    """Data class for the response of the intent classifier.

    Attributes:
        label (str): The predicted intent label.
        confidence (float): The confidence score of the prediction.
        meets_threshold (bool): Whether the confidence score meets the required
            threshold.
        is_shopping_related (bool): Whether the intent is shopping-related.
        error (str): An error message, if any.
        error_type (str): The type of the error, if any.
        classifier_type (str): The type of classifier used.
        input_text (str): The input text that was classified.
        all_scores (Dict): A dictionary of all scores for each label.
        model_info (Dict): Information about the model used for classification.
        supported_labels (List[str]): A list of all supported labels.
    """

    label: str
    confidence: float
    meets_threshold: bool
    is_shopping_related: bool
    error: str = ""
    error_type: str = ""
    classifier_type: str = ""
    input_text: str = ""
    all_scores: dict = field(default_factory=dict)
    model_info: dict = field(default_factory=dict)
    supported_labels: list[str] = field(default_factory=list)


class ClassifierInference(ABC):
    """Abstract base class for intent classification inference.

    This class defines the interface that all intent classifiers must implement.
    It provides a consistent API for different classification backends.
    """

    @abstractmethod
    def predict(
        self, input_text: str, labels: list[str] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Predicts the intent of the given input text.

        Args:
            input_text: The user input text to classify.
            labels: A list of possible intent labels to classify against. If
                None, the default labels from the constants are used.
            **kwargs: Additional parameters for specific classifier
                implementations.

        Returns:
            A dictionary containing the classification result.
        """
        pass


class IntentDetection(ClassifierInference):
    """Main intent detection class for the shopping assistant.

    This class orchestrates intent classification using different backends.

    Attributes:
        _classifier: The underlying classification model instance.
        _model: The name or identifier of the model being used.
        _labels: A list of intent labels for classification.
    """

    def __init__(self, classifier: str = "default", **kwargs: Any) -> None:
        """Initializes the intent detection system.

        Args:
            classifier: The classification backend to use (e.g., 'default',
                'openai').
            **kwargs: Additional configuration parameters, such as `openai_model`,
                `labels`, or `model`.

        Raises:
            ValueError: If an unsupported classifier type is specified.
            ConnectionError: If the OpenAI classifier is requested but the API key
                is missing.
        """
        self._classifier = self._get_classifier(classifier, **kwargs)
        self._model = kwargs.get("model", classifier)
        self._labels = kwargs.get("labels", get_intent_labels())

        if self._classifier is None:
            raise ValueError(f"Failed to initialize classifier: {classifier}")

    @staticmethod
    def _get_classifier(
        provider: str = "default", **kwargs: Any
    ) -> IntentClassifier | OpenAiIntentClassifier:
        """Factory method to create the appropriate classifier instance.

        Args:
            provider: The classification provider to use (e.g., 'default',
                'openai').
            **kwargs: Provider-specific configuration, such as `openai_model` or
                `openai_api_key`.

        Returns:
            A configured classifier instance.

        Raises:
            ValueError: If the provider is not supported.
            ConnectionError: If the OpenAI provider is selected but no API key is
                available.
            ImportError: If the required dependencies for the provider are not
                installed.
        """
        if provider == "local":
            try:
                return IntentClassifier()
            except Exception as e:
                raise ImportError(
                    f"Failed to initialize default classifier. "
                    f"Ensure transformers and torch are installed: {e}"
                )

        elif provider == "default":
            openai_key = kwargs.get("openai_api_key", settings.openai_apikey)

            if not openai_key:
                raise ConnectionError(
                    "OpenAI classifier requires an API key. "
                    "Set OPEN_AI_APIKEY in your .env file or pass "
                    "openai_api_key parameter."
                )

            model_name = kwargs.get("openai_model", "gpt-4o-mini")

            try:
                return OpenAiIntentClassifier(
                    model_name=model_name, openai_api_key=openai_key
                )
            except Exception as e:
                raise ConnectionError(f"Failed to initialize OpenAI classifier: {e}")

        else:
            raise ValueError(
                f"Unsupported classifier provider: {provider}. "
                f"Supported providers: 'default', 'openai'"
            )

    def predict(
        self, input_text: str, labels: list[str] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Classifies the intent of user input text.

        Args:
            input_text: The user's input text to analyze.
            labels: Specific labels to classify against. If None, the default
                labels from initialization are used.
            **kwargs: Additional parameters to pass to the underlying classifier.

        Returns:
            A dictionary containing the classification results.

        Raises:
            ValueError: If `input_text` is empty or invalid.
            RuntimeError: If classification fails due to model issues.
        """
        if not input_text or not input_text.strip():
            raise ValueError("Input text cannot be empty")

        classification_labels = labels or self._labels

        if not classification_labels:
            raise ValueError("No classification labels available")

        try:
            result = self._classifier.predict(
                input_text, classification_labels, **kwargs
            )

            if isinstance(result, dict):
                result.setdefault("model", self._model)
                return result
            else:
                return {
                    "label": str(result),
                    "score": 1.0,
                    "model": self._model,
                    "probabilities": {},
                }

        except Exception as e:
            raise RuntimeError(f"Intent classification failed: {e}")

    def get_supported_labels(self) -> list[str]:
        """Gets the list of intent labels this classifier can predict.

        Returns:
            A list of supported intent labels.
        """
        return list(self._labels)

    def get_model_info(self) -> dict[str, Any]:
        """Gets information about the current classification model.

        Returns:
            A dictionary containing model information.
        """
        return {
            "provider": (
                "openai"
                if "openai" in str(type(self._classifier)).lower()
                else "default"
            ),
            "model": self._model,
            "labels": self._labels,
            "capabilities": ["intent_classification", "confidence_scoring"],
        }


def classify_intent(
    text: str, classifier_type: str = "default", **kwargs: Any
) -> IntentClassifierResponse:
    """Driver function for intent classification with a simplified interface.

    Args:
        text: The user input text to classify.
        classifier_type: The type of classifier to use (e.g., 'default',
            'openai').
        **kwargs: Additional parameters for the classifier.

    Returns:
        An `IntentClassifierResponse` object containing the classification
        result.
    """
    try:
        detector = IntentDetection(classifier=classifier_type, **kwargs)

        prediction = detector.predict(text)

        confidence_threshold = kwargs.get("confidence_threshold", 70.0)

        confidence = prediction.get("score", prediction.get("confidence", 70.0))
        meets_threshold = confidence >= confidence_threshold

        intent_label = prediction.get("label", "")
        is_shopping_related = IntentLabels.is_shopping_related(intent_label)

        model_info = detector.get_model_info()

        return IntentClassifierResponse(
            label=intent_label,
            confidence=confidence,
            meets_threshold=meets_threshold,
            is_shopping_related=is_shopping_related,
            all_scores=prediction.get("probabilities", {}),
            model_info=model_info,
            classifier_type=classifier_type,
            input_text=text,
            supported_labels=detector.get_supported_labels(),
        )

    except Exception as e:
        return IntentClassifierResponse(
            label="error",
            confidence=0.0,
            meets_threshold=False,
            is_shopping_related=False,
            error=str(e),
            error_type=type(e).__name__,
            classifier_type=classifier_type,
            input_text=text,
            all_scores={},
            model_info={},
            supported_labels=[],
        )


def quick_intent_check(text: str) -> str:
    """Performs a quick intent classification and returns just the label.

    Args:
        text: The user input text to classify.

    Returns:
        The predicted intent label, or 'error' if classification fails.
    """
    try:
        classification_result = classify_intent(text)
        return classification_result.label or "error"
    except Exception:
        return "error"


def is_shopping_query(text: str, confidence_threshold: float = 0.5) -> bool:
    """Checks if a query is shopping-related with a confidence threshold.

    Args:
        text: The user input text to analyze.
        confidence_threshold: The minimum confidence required (0.0-1.0).

    Returns:
        `True` if the query is shopping-related and meets the confidence
        threshold, `False` otherwise.
    """
    try:
        classification_result = classify_intent(
            text, confidence_threshold=confidence_threshold
        )
        return (
            classification_result.is_shopping_related
            and classification_result.meets_threshold
        )
    except Exception:
        return False


if __name__ == "__main__":
    # Test the driver functions
    test_queries = [
        "I want to buy a new laptop",
        "Show me some winter jackets",
        "What's the weather like today?",
        "I'm looking for running shoes",
        "Can you help me find a good restaurant?",
        "I need a new phone with good camera",
    ]

    print("Testing Intent Classification Driver Functions")
    print("=" * 60)

    for query in test_queries:
        print(f"\nQuery: {query}")

        # Test full classification
        result = classify_intent(query)
        print(f"Intent: {result.label} (confidence: {result.confidence:.2f})")
        print(f"Shopping related: {result.is_shopping_related}")
        print(f"Model: {result.model_info.get('provider', 'unknown')}")

        # Test quick check
        quick_result = quick_intent_check(query)
        print(f"Quick check: {quick_result}")

        # Test shopping query check
        is_shopping = is_shopping_query(query, confidence_threshold=0.6)
        print(f"Is shopping (>60% confidence): {is_shopping}")
        print("-" * 40)
