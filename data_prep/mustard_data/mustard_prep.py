# prepare the data from MUStARD dataset

import os
import json
from collections import OrderedDict

import torch
from torch import nn

from data_prep.audio_extraction import convert_mp4_to_wav, ExtractAudio
from data_prep.data_prep_helpers import (
    clean_up_word,
    get_speaker_to_index_dict,
    make_acoustic_dict,
    get_longest_utt,
    get_class_weights,
    make_acoustic_set,
)
from data_prep.meld_data.meld_prep import get_max_num_acoustic_frames
import pandas as pd


class MustardPrep:
    """
    A class to prepare mustard for input into a generic Dataset
    """

    def __init__(
        self,
        mustard_path,
        acoustic_length,
        train_prop=0.6,
        test_prop=0.2,
        utts_file_name="mustard_utts.tsv",
        f_end="_IS10.csv",
        use_cols=None,
        add_avging=True,
        avgd=False,
    ):
        # path to dataset
        self.path = mustard_path
        # path to file with utterances and gold labels
        self.utts_gold_file = os.path.join(mustard_path, utts_file_name)
        self.utterances = pd.read_csv(self.utts_gold_file, sep="\t")
        # path to acoustic files
        self.acoustic_path = os.path.join(mustard_path, "acoustic_feats")

        # train, dev, and test dataframes
        self.train, self.dev, self.test = create_data_folds(
            self.utterances, train_prop, test_prop
        )

        # train, dev, and test acoustic data
        self.train_dict = OrderedDict(
            make_acoustic_dict(
                self.acoustic_path,
                files_to_get=set(self.train["clip_id"].tolist()),
                f_end=f_end,
                use_cols=use_cols,
                data_type="mustard",
            )
        )
        self.dev_dict = OrderedDict(
            make_acoustic_dict(
                self.acoustic_path,
                files_to_get=set(self.dev["clip_id"].tolist()),
                f_end=f_end,
                use_cols=use_cols,
                data_type="mustard",
            )
        )
        self.test_dict = OrderedDict(
            make_acoustic_dict(
                self.acoustic_path,
                files_to_get=set(self.test["clip_id"].tolist()),
                f_end=f_end,
                use_cols=use_cols,
                data_type="mustard",
            )
        )

        self.longest_utt = get_longest_utt(self.utterances["utterance"])
        self.longest_dia = None  # mustard is not organized as dialogues

        self.longest_acoustic = get_max_num_acoustic_frames(
            list(self.train_dict.values())
            + list(self.dev_dict.values())
            + list(self.test_dict.values())
        )

        # get acoustic and usable utterance data
        self.train_acoustic, self.train_usable_utts = make_acoustic_set(
            self.train,
            self.train_dict,
            data_type="mustard",
            acoustic_length=acoustic_length,
            longest_acoustic=self.longest_acoustic,
            add_avging=add_avging,
            avgd=avgd,
        )
        self.dev_acoustic, self.dev_usable_utts = make_acoustic_set(
            self.dev,
            self.dev_dict,
            data_type="mustard",
            acoustic_length=acoustic_length,
            longest_acoustic=self.longest_acoustic,
            add_avging=add_avging,
            avgd=avgd,
        )
        self.test_acoustic, self.test_usable_utts = make_acoustic_set(
            self.test,
            self.test_dict,
            data_type="mustard",
            acoustic_length=acoustic_length,
            longest_acoustic=self.longest_acoustic,
            add_avging=add_avging,
            avgd=avgd,
        )

        # get utterance, speaker, and gold label information
        (
            self.train_utts,
            self.train_spkrs,
            self.train_y_sarcasm,
            self.train_utt_lengths,
        ) = self.make_mustard_data_tensors(self.train)
        (
            self.dev_utts,
            self.dev_spkrs,
            self.dev_y_sarcasm,
            self.dev_utt_lengths,
        ) = self.make_mustard_data_tensors(self.dev)
        (
            self.test_utts,
            self.test_spkrs,
            self.test_y_sarcasm,
            self.test_utt_lengths,
        ) = self.make_mustard_data_tensors(self.test)

        # set the sarcasm weights
        self.sarcasm_weights = get_class_weights(self.train_y_sarcasm)

        # get the data organized for input into the NNs
        self.train_data, self.dev_data, self.test_data = self.combine_xs_and_ys()

    def combine_xs_and_ys(self):
        # todo: get this into the individual dataset classes
        """
        Combine all x and y data into list of tuples for easier access with DataLoader
        """
        train_data = []
        dev_data = []
        test_data = []

        for i, item in enumerate(self.train_acoustic):
            # normalize
            item_transformed = item
            if self.train_genders[i] == 1:
                item_transformed = self.transform_acoustic_item(
                    item, self.train_genders[i]
                )
            train_data.append(
                (
                    item_transformed,
                    self.train_utts[i],
                    self.train_spkrs[i],
                    self.train_y_sarcasm[i],
                    self.train_utt_lengths[i],
                    self.train_acoustic_lengths[i],
                )
            )

        for i, item in enumerate(self.dev_acoustic):
            item_transformed = self.transform_acoustic_item(item, self.dev_genders[i])
            dev_data.append(
                (
                    item_transformed,
                    self.dev_utts[i],
                    self.dev_spkrs[i],
                    self.dev_y_sarcasm[i],
                    self.dev_utt_lengths[i],
                    self.dev_acoustic_lengths[i],
                )
            )

        for i, item in enumerate(self.test_acoustic):
            item_transformed = self.transform_acoustic_item(item, self.test_genders[i])
            test_data.append(
                (
                    item_transformed,
                    self.test_utts[i],
                    self.test_spkrs[i],
                    self.test_y_sarcasm[i],
                    self.test_utt_lengths[i],
                    self.test_acoustic_lengths[i],
                )
            )

        return train_data, dev_data, test_data

    def make_mustard_data_tensors(self, all_utts_df):
        """
        Prepare the tensors of utterances + speakers, emotion and sentiment scores
        :param all_utts_df: the dataframe of all utterances
        :return:
        """
        # create holders for the data
        all_utts = []
        all_speakers = []
        all_sarcasm = []

        # create holder for sequence lengths information
        utt_lengths = []

        for idx, row in all_utts_df.iterrows():

            # create utterance-level holders
            utts = [0] * self.longest_utt

            # get values from row
            utt = row["utterance"]
            utt = [clean_up_word(wd) for wd in utt.strip().split(" ")]
            utt_lengths.append(len(utt))

            spk_id = row["speaker"]
            sarc = row["sarcasm"]

            # convert words to indices for glove
            for ix, wd in enumerate(utt):
                if wd in self.glove.wd2idx.keys():
                    utts[ix] = self.glove.wd2idx[wd]
                else:
                    utts[ix] = self.glove.wd2idx["<UNK>"]

            all_utts.append(torch.tensor(utts))
            all_speakers.append(spk_id)
            all_sarcasm.append([sarc])

        # get set of all speakers, create lookup dict, and get list of all speaker IDs
        speaker_set = set([speaker for speaker in all_speakers])
        speaker2idx = get_speaker_to_index_dict(speaker_set)
        speaker_ids = [[speaker2idx[speaker]] for speaker in all_speakers]

        # create pytorch tensors for each
        speaker_ids = torch.tensor(speaker_ids)
        all_sarcasm = torch.tensor(all_sarcasm)

        # padd and transpose utterance sequences
        all_utts = nn.utils.rnn.pad_sequence(all_utts)
        all_utts = all_utts.transpose(0, 1)

        # return data
        return all_utts, speaker_ids, all_sarcasm, utt_lengths


def organize_labels_from_json(jsonfile, savepath, save_name):
    """
    Take the jsonfile containing the text, speaker, and y values
    Prepares relevant information as a csv file
    """
    with open(jsonfile, "r") as jfile:
        json_data = json.load(jfile)

    # create holder for relevant information
    data_holder = [["clip_id", "utterance", "speaker", "sarcasm"]]

    # get utterance, speaker, clip ID, and gold labels
    for clip in json_data.keys():
        clip_id = clip
        utt = json_data[clip]["utterance"]
        spk = json_data[clip]["speaker"]
        sarc = str(1 if json_data[clip]["sarcasm"] else 0)

        data_holder.append([clip_id, utt, spk, sarc])

    # save the data to a new csv file
    with open(os.path.join(savepath, save_name), "w") as savefile:
        for item in data_holder:
            savefile.write("\t".join(item))
            savefile.write("\n")


def create_data_folds(data, perc_train, perc_test):
    """
    Create train, dev, and test folds for a dataset without them
    Specify the percentage of the data that goes into each fold
    data : a Pandas dataframe with (at a minimum) gold labels for all data
    perc_* : the percentage for each fold
    Percentage not included in train or test fold allocated to dev
    """
    # shuffle the rows of the dataframe
    shuffled = data.sample(frac=1).reset_index(drop=True)

    # get length of df
    length = shuffled.shape[0]

    # calculate length of each split
    train_len = perc_train * length
    test_len = perc_test * length

    # get slices of dataset
    train_data = shuffled.iloc[: int(train_len)]
    test_data = shuffled.iloc[int(train_len) : int(train_len) + int(test_len)]
    dev_data = shuffled.iloc[int(train_len) + int(test_len) :]

    # return data
    return train_data, dev_data, test_data


def preprocess_mustard_data(
    base_path,
    gold_save_name,
    acoustic_save_dir,
    smile_path,
    acoustic_feature_set="IS10",
):
    """
    Preprocess the mustard data by getting an organized CSV from the json gold file,
    converting mp4 clips to wav files and extracting acoustic features from the wavs
    base_path : the path to the base MUStARD directory
    gold_save_name : the name of the tsv file to save gold labels + utterances to
    acoustic_save_dir : the directory in which to save acoustic feature files
    smile_path : the path to OpenSMILE
    acoustic_feature_set : the feature set to use with ExtractAudio
    """
    # set path to the json file (named by dataset authors)
    json_path = os.path.join(base_path, "sarcasm_data.json")

    # extract relevant info from json files and save as csv
    organize_labels_from_json(json_path, base_path, gold_save_name)

    # set path to mp4 files
    path_to_files = os.path.join(base_path, "utterances_final")

    # convert mp4 files to wav
    for clip in os.listdir(path_to_files):
        convert_mp4_to_wav(os.path.join(path_to_files, clip))

    # set path to acoustic feats
    acoustic_save_path = os.path.join(json_path, acoustic_save_dir)
    # create the save directory if it doesn't exist
    if not os.path.exists(acoustic_save_path):
        os.makedirs(acoustic_save_path)

    # extract features using opensmile
    for audio_file in os.listdir(path_to_files):
        if audio_file.endswith(".wav"):
            audio_name = audio_file.split(".wav")[0]
            audio_save_name = str(audio_name) + "_" + acoustic_feature_set + ".csv"
            extractor = ExtractAudio(
                path_to_files, audio_file, acoustic_save_path, smile_path
            )
            extractor.save_acoustic_csv(
                feature_set=acoustic_feature_set, savename=audio_save_name
            )
