import json

from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
#
# model = AutoModelForSequenceClassification.from_pretrained("yeniguno/bert-uncased-intent-classification")
# tokenizer = AutoTokenizer.from_pretrained("yeniguno/bert-uncased-intent-classification")
#
# pipe = pipeline("text-classification", model=model, tokenizer=tokenizer)
#
# text = "I am looking for a nice shirt for a wedding"
# prediction = pipe(text)
#
# print(prediction)


# [{'label': 'play_music', 'score': 0.9997674822807312}]
# from transformers import pipeline
# candidate_labels=["shopping_intent","not_shopping_intent"]
# classifier = pipeline("text-classification", model="Falconsai/intent_classification")
# text = "I am looking for a nice shirt for a wedding"
# result = classifier(text,candidate_labels=candidate_labels)
# print(result)
# from transformers import pipeline
#
# # Initialize the zero-shot classification pipeline
pipe = pipeline(model="facebook/bart-large-mnli")

# Perform zero-shot classification
text = [
  { "Person": "I am looking for a nice shirt for a wedding." },
  { "Chatbot": "Great! Do you have a style in mind—classic, modern, or something bold?" },
  { "Person": "Oh, this one does not look good." },
  { "Chatbot": "No worries, let’s skip that one. Want me to pull some options that might feel sharper?" },
  {"Person": "Never mind lets talk about something else"},
]

text_str= json.dumps(text[:-2])
result = pipe(
text_str,
candidate_labels=["shopping_intent","not_shopping_intent","shopping_continuation","digression"]
)
print(result)
