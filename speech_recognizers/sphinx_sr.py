import speech_recognition as sr
import sys


def transcribe_file(input_file):

    r = sr.Recognizer()
    stim = sr.AudioFile(input_file)
    with stim as source:
        audio = r.record(source)

    try:
        transcription = r.recognize_sphinx(audio)
    except:
        transcription = None

    return transcription


if __name__ == "__main__":
    input_file = sys.argv[1]
    result = transcribe_file(input_file)
    print(result)