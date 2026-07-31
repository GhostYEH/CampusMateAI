from __future__ import annotations

CLASS_NAMES = ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"]
CLASS_TO_INDEX = {name: index for index, name in enumerate(CLASS_NAMES)}
NUM_CLASSES = len(CLASS_NAMES)
LABEL_TO_ANDROID = {
    "angry": "ANGRY",
    "disgust": "DISGUST",
    "fear": "FEAR",
    "happy": "HAPPY",
    "neutral": "NEUTRAL",
    "sad": "SAD",
    "surprise": "SURPRISE",
}
