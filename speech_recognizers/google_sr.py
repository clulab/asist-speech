import sys
import os
import json


def transcribe_file(speech_file, sample_rate):
    """Transcribe the given audio file."""
    from google.cloud import speech
    import io

    client = speech.SpeechClient()

    with io.open(speech_file, "rb") as audio_file:
        content = audio_file.read()

    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=sample_rate,
        language_code="en-US",
        enable_word_time_offsets=True,
        # enable_word_confidence=True
    )

    response = client.recognize(config=config, audio=audio)

    # Each result is for a consecutive portion of the audio. Iterate through
    # them to get the transcripts for the entire audio file.

    all_results = ""
    all_text_confs = []

    for result in response.results:
        # The first alternative is the most likely one for this portion.
        all_results += str(result) + '\n'
        all_text_confs.append("%s\t%s" % (result.alternatives[0].transcript,
                                          result.alternatives[0].confidence))

    # print(response)
    # print(response.results)

    return all_results, all_text_confs
    # return text_conf


if __name__ == "__main__":
    # replace this with your credentials
    credentials = "your_credentials_here.json"
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials

    sample_rate = int(sys.argv[1])
    input_file = sys.argv[2]

    unformatted_results, utt_result = transcribe_file(input_file, sample_rate)
    print(utt_result[0])
