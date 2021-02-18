# transcribe datasets using google speech-to-text

import os
import sys
import wave
from speech_recognizers.google_sr import transcribe_file


def transcribe_and_save(dataset, base_location, wav_location, save_unformatted_location,
                        save_name="google_transcriptions.txt"):
    formatted_results = []
    skipped_audio = []

    for item in os.listdir(wav_location):
        if item.endswith('.wav'):
            filesize = os.path.getsize(f"{wav_location}/{item}")
            if filesize >= 10000000:
                skipped_audio.append(item)
            else:
                with wave.open(f"{wav_location}/{item}", "rb") as wave_file:
                    frame_rate = wave_file.getframerate()
                if dataset.lower() == "mustard":
                    item_name = item.split(".wav")[0]
                elif dataset.lower() == "meld":
                    item_name = item.split("_2.wav")[0]
                elif dataset.lower() == "chalearn":
                    item_name = item.split(".wav")[0] + ".mp4"
                unformatted_results, utt_results = transcribe_file(f"{wav_location}/{item}", frame_rate)
                with open(f"{save_unformatted_location}/{item_name}_unformatted.txt", 'w') as unformatted_file:
                    unformatted_file.write(unformatted_results)
                for utt in utt_results:
                    line = f"{item}\t{utt}"
                    formatted_results.append(line)

    with open(f"{base_location}/{save_name}", 'w') as gfile:
        gfile.write("\n".join(formatted_results))

    with open(f"{base_location}/skipped_files.txt", 'w') as skipped:
        skipped.write("\n".join(skipped_audio))


if __name__ == "__main__":
    # replace with your credentials
    credentials = "your_credentials_here.json"
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials

    # sample_rate = 44100

    if sys.argv[1] == "mustard":
        # access the data
        mustard_base_location = "/Users/jculnan/datasets/multimodal_datasets/MUStARD"
        mustard_wav_location = os.path.join(mustard_base_location, "wav")
        # save unformatted objsects
        mustard_save_unformatted_location = os.path.join(mustard_base_location, "google-unformatted")
        # create this directory if it doesn't exist
        os.system(f'if [ ! -d "{mustard_save_unformatted_location}" ]; then mkdir -p {mustard_save_unformatted_location}; fi')

        formatted_results = []

        for item in os.listdir(mustard_wav_location):
            if item.endswith('.wav'):
                with wave.open(f"{mustard_wav_location}/{item}", "rb") as wave_file:
                    frame_rate = wave_file.getframerate()
                item_name = item.split(".wav")[0]
                unformatted_results, utt_results = transcribe_file(f"{mustard_wav_location}/{item}", frame_rate)
                with open(f"{mustard_save_unformatted_location}/{item_name}_unformatted.txt", 'w') as unformatted_file:
                    unformatted_file.write(unformatted_results)
                for utt in utt_results:
                    line = f"{item}\t{utt}"
                    formatted_results.append(line)

        with open(f"{mustard_base_location}/google_transcriptions.txt", 'w') as gfile:
            gfile.write("\n".join(formatted_results))

    elif sys.argv[1] == "meld":
        # access the data
        meld_train_base_location = "/Users/jculnan/datasets/multimodal_datasets/MELD_formatted/train"
        meld_dev_base_location = "/Users/jculnan/datasets/multimodal_datasets/MELD_formatted/dev"
        meld_test_base_location = "/Users/jculnan/datasets/multimodal_datasets/MELD_formatted/test"
        # todo: change this once you've tested it
        meld_train_wav_location = os.path.join(meld_train_base_location, "train_audio_mono")
        meld_dev_wav_location = os.path.join(meld_dev_base_location, "dev_audio_mono")
        meld_test_wav_location = os.path.join(meld_test_base_location, "test_audio_mono")
        # save unformatted objects
        meld_train_save_unformatted_location = os.path.join(meld_train_base_location, "google-unformatted-test")
        meld_dev_save_unformatted_location = os.path.join(meld_dev_base_location, "google-unformatted")
        meld_test_save_unformatted_location = os.path.join(meld_test_base_location, "google-unformatted")
        # create this directory if it doesn't exist
        os.system(f'if [ ! -d "{meld_train_save_unformatted_location}" ]; then mkdir -p {meld_train_save_unformatted_location}; fi')
        os.system(
            f'if [ ! -d "{meld_dev_save_unformatted_location}" ]; then mkdir -p {meld_dev_save_unformatted_location}; fi')
        os.system(
            f'if [ ! -d "{meld_test_save_unformatted_location}" ]; then mkdir -p {meld_test_save_unformatted_location}; fi')

        transcribe_and_save("meld", meld_train_base_location, meld_train_wav_location,
                            meld_train_save_unformatted_location, save_name="dia644_utt4_retest.txt")

        transcribe_and_save("meld", meld_dev_base_location, meld_dev_wav_location,
                            meld_dev_save_unformatted_location)

        transcribe_and_save("meld", meld_test_base_location, meld_test_wav_location,
                            meld_test_save_unformatted_location)

    elif sys.argv[1] == "chalearn":
        # access the data
        chalearn_train_base_location = "/Users/jculnan/datasets/multimodal_datasets/Chalearn/train"
        chalearn_dev_base_location = "/Users/jculnan/datasets/multimodal_datasets/Chalearn/val"
        chalearn_test_base_location = "/Users/jculnan/datasets/multimodal_datasets/Chalearn/test"
        # todo: change this once you've tested it
        chalearn_train_wav_location = os.path.join(chalearn_train_base_location, "wav")
        chalearn_dev_wav_location = os.path.join(chalearn_dev_base_location, "wav")
        chalearn_test_wav_location = os.path.join(chalearn_test_base_location, "wav")
        # save unformatted objsects
        chalearn_train_save_unformatted_location = os.path.join(chalearn_train_base_location, "google-unformatted")
        chalearn_dev_save_unformatted_location = os.path.join(chalearn_dev_base_location, "google-unformatted")
        chalearn_test_save_unformatted_location = os.path.join(chalearn_test_base_location, "google-unformatted")
        # create this directory if it doesn't exist
        os.system(f'if [ ! -d "{chalearn_train_save_unformatted_location}" ]; then mkdir -p {chalearn_train_save_unformatted_location}; fi')
        os.system(
            f'if [ ! -d "{chalearn_dev_save_unformatted_location}" ]; then mkdir -p {chalearn_dev_save_unformatted_location}; fi')
        os.system(
            f'if [ ! -d "{chalearn_test_save_unformatted_location}" ]; then mkdir -p {chalearn_test_save_unformatted_location}; fi')

        transcribe_and_save("chalearn", chalearn_train_base_location, chalearn_train_wav_location,
                            chalearn_train_save_unformatted_location)

        transcribe_and_save("chalearn", chalearn_dev_base_location, chalearn_dev_wav_location,
                            chalearn_dev_save_unformatted_location)

        transcribe_and_save("chalearn", chalearn_test_base_location, chalearn_test_wav_location,
                            chalearn_test_save_unformatted_location)
