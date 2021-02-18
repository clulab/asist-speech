# transcribe all datasets using sphinx with speech_recognizers/sphinx_sr.py
# assumes data files are WAV formatted and organized in directories

from speech_recognizers import sphinx_sr

import os
import pandas as pd
import warnings
import sys


class DatasetTranscriber:
    """
    Transcribes wav files for datasets using pocketsphinx
    currently written for MELD, MUStARD, and ChaLearn
    dataset : a string of name of dataset
    location : full path to dataset directory
    extensions : directory extensions needed to access wav files
    """
    def __init__(self, dataset, location, extensions=None):
        self.dataset = dataset.lower()  # options: 'meld', 'mustard', 'chalearn'
        self.location = location
        # get list of extensions
        if type(extensions) is not str:
            self.extensions = extensions
        else:
            self.extensions = []
            self.extensions.append(extensions)
        self.save_location = f"{location}/{self.dataset}_transcribed"

    def convert_and_save_transcriptions(self, data_dict, transcript_dict):
        """
        takes a dictionary of current gold files with text
        and a dictionary of new transcriptions
        and replaces gold with new transcriptions
        saves updated files in new location
        """
        # find dataset type
        if self.dataset == "meld":
            pass
        elif self.dataset == "mustard":

            pass
        elif self.dataset == "chalearn":
            pass

    def read_in_current_files(self, current_file_location):
        """
        read in files containing gold transcriptions
        files are in different formats depending upon the dataset
        """
        # create dict for label : utt/other-info pairs
        data_dict = {}
        if self.dataset == "meld":
            # all utterances in a single csv file
            all_utts = pd.read_csv(current_file_location)
        elif self.dataset == "mustard" or self.dataset == "chalearn":
            # all utterances are in a single tsv file
            all_utts = pd.read_csv(current_file_location, sep='\t')

        return all_utts

    def save_transcriptions(self, transcriptions_dict, current_files, save_name):
        """
        Save transcriptions alongside other info currently
        required for each dataset
        Saves to location self.location
        """
        sname = ""
        if save_name.endswith(".tsv"):
            sname = save_name
        elif save_name.endswith(".csv"):
            sname = save_name.split(".csv")[0]
        else:
            sname = f"{save_name}.tsv"

        # convert transcriptions dict to pandas df
        transcriptions_df = pd.DataFrame.from_dict(transcriptions_dict)
        # delete utterance from current_files
        current_files = current_files.loc[:, ~(current_files.columns.str.lower() == 'utterance')]

        # merge dfs on id
        if self.dataset == "meld":
            transcriptions_df.rename(columns={'id': 'DiaID_UttID'}, inplace=True)
            transcriptions_df = transcriptions_df.merge(current_files, on='DiaID_UttID')
        elif self.dataset == "mustard":
            transcriptions_df.rename(columns={'id': 'clip_id'}, inplace=True)
            print(transcriptions_df.columns.values.tolist())
            print(current_files.columns.values.tolist())
            transcriptions_df = transcriptions_df.merge(current_files, on='clip_id')
        elif self.dataset == "chalearn":
            transcriptions_df.rename(columns={'id': 'file'}, inplace=True)
            transcriptions_df = transcriptions_df.merge(current_files, on='file')

        transcriptions_df.to_csv(f"{self.location}/{sname}", index=False,
                                 sep="\t")

    def transcribe(self):
        """
        transcribe all available files in the specified location
        """
        # save dict of [name -> [list]]
        transcript_dict = {'id': [], 'utterance': []}

        if self.extensions is not None:
            for ext in self.extensions:
                # get the location of each dir with files
                location = f"{self.location}/{ext}"
                # find wav files
                for wavfile in os.listdir(location):
                    ending = ".wav"
                    if self.dataset == "meld":
                        ending = "_2.wav"
                    if wavfile.endswith(ending):
                        wavname = wavfile.split(ending)[0]
                        if self.dataset == "chalearn":
                            wavname = wavname + ".mp4"
                        print(f"Now transcribing {wavname}")
                        # transcribe wav files
                        full_path = os.path.join(location, wavfile)
                        transcription = sphinx_sr.transcribe_file(full_path)
                        print(transcription)
                        # add wavname, transcription pairs to transcript_dict
                        transcript_dict['id'].append(wavname)
                        transcript_dict['utterance'].append(transcription)
        # return completed dict
        return transcript_dict


if __name__ == "__main__":
    if sys.argv[1] == "mustard":
        # assumes that datasets are in the untracked 'data' directory
        mustard_location = "../../data/multimodal_datasets/MUStARD"
        mustard_extensions = "utterances_final"
        current_file_path = f"{mustard_location}/mustard_utts.tsv"

        mustard_transcriber = DatasetTranscriber("MUStARD", mustard_location, mustard_extensions)

        # get current label file
        current_file = mustard_transcriber.read_in_current_files(current_file_path)
        print("Current file read")
        print(current_file.head(5))

        # transcribe data
        transcripts = mustard_transcriber.transcribe()

        # save transcriptions
        mustard_transcriber.save_transcriptions(transcripts, current_file, "mustard_sphinx.tsv")

    elif sys.argv[1] == "meld":
        # assumes that datasets are in the untracked 'data' directory
        meld_location = "../../data/multimodal_datasets/MELD_formatted"

        meld_train_extensions = "train/train_audio"
        meld_dev_extensions = "dev/dev_audio"
        meld_test_extensions = "test/test_audio"

        current_train_path = f"{meld_location}/train/train_sent_emo.csv"
        current_dev_path = f"{meld_location}/dev/dev_sent_emo.csv"
        current_test_path = f"{meld_location}/test/test_sent_emo.csv"

        meld_train_transcriber = DatasetTranscriber("MELD", meld_location, meld_train_extensions)
        meld_dev_transcriber = DatasetTranscriber("MELD", meld_location, meld_dev_extensions)
        meld_test_transcriber = DatasetTranscriber("MELD", meld_location, meld_test_extensions)

        # get paths
        current_train_file = meld_train_transcriber.read_in_current_files(current_train_path)
        current_dev_file = meld_dev_transcriber.read_in_current_files(current_dev_path)
        current_test_file = meld_test_transcriber.read_in_current_files(current_test_path)

        # transcribe data
        train_transcripts = meld_train_transcriber.transcribe()
        dev_transcripts = meld_dev_transcriber.transcribe()
        test_transcripts = meld_test_transcriber.transcribe()

        # save transcriptions
        meld_train_transcriber.save_transcriptions(train_transcripts, current_train_file, "train/meld_sphinx.tsv")
        meld_dev_transcriber.save_transcriptions(dev_transcripts, current_dev_file, "dev/meld_sphinx.tsv")
        meld_test_transcriber.save_transcriptions(test_transcripts, current_test_file, "test/meld_sphinx.tsv")

    elif sys.argv[1] == "chalearn":
        # assumes that datasets are in the untracked 'data' directory
        chalearn_location = "/Users/jculnan/datasets/multimodal_datasets/Chalearn"

        chalearn_train_extension = "train/mp4"
        chalearn_dev_extension = "val/mp4"
        chalearn_test_extension = "test/wav"

        current_train_path = f"{chalearn_location}/train/gold_and_utts.tsv"
        current_dev_path = f"{chalearn_location}/val/gold_and_utts.tsv"
        current_test_path = f"{chalearn_location}/test/gold_and_utts.tsv"

        chalearn_train_transcriber = DatasetTranscriber("Chalearn", chalearn_location, chalearn_train_extension)
        current_train_file = chalearn_train_transcriber.read_in_current_files(current_train_path)
        train_transcripts = chalearn_train_transcriber.transcribe()

        # save transcriptions
        chalearn_train_transcriber.save_transcriptions(train_transcripts, current_train_file, "train/chalearn_sphinx.tsv")

        chalearn_dev_transcriber = DatasetTranscriber("Chalearn", chalearn_location, chalearn_dev_extension)
        current_dev_file = chalearn_dev_transcriber.read_in_current_files(current_dev_path)
        dev_transcripts = chalearn_dev_transcriber.transcribe()

        # save transcriptions
        chalearn_dev_transcriber.save_transcriptions(dev_transcripts, current_dev_file, "val/chalearn_sphinx.tsv")

        chalearn_test_transcriber = DatasetTranscriber("Chalearn", chalearn_location, chalearn_test_extension)
        current_test_file = chalearn_test_transcriber.read_in_current_files(current_test_path)
        test_transcripts = chalearn_test_transcriber.transcribe()

        # save transcriptions
        chalearn_test_transcriber.save_transcriptions(test_transcripts, current_test_file, "test/chalearn_sphinx.tsv")