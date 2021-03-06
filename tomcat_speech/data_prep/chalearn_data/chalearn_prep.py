# prepare chalearn for input into the model

import os
import pickle
import json
import sys
from collections import OrderedDict

import torch
from torch import nn
from torchtext.data import get_tokenizer

from tomcat_speech.data_prep.audio_extraction import (
    ExtractAudio,
)
import pandas as pd

from tomcat_speech.data_prep.data_prep_helpers import (
    get_gender_avgs,
    clean_up_word,
    get_max_num_acoustic_frames,
    transform_acoustic_item,
)


class ChalearnPrep:
    """
    A class to prepare meld for input into a generic Dataset
    """

    def __init__(
        self,
        chalearn_path,
        acoustic_length,
        glove,
        f_end="_IS10.csv",
        use_cols=None,
        add_avging=True,
        avgd=False,
    ):
        self.path = chalearn_path
        self.train_path = chalearn_path + "/train"
        self.dev_path = chalearn_path + "/val"
        self.test_path = chalearn_path + "/test"
        self.train = "{0}/gold_and_utts.tsv".format(self.train_path)
        self.dev = "{0}/gold_and_utts.tsv".format(self.dev_path)
        # self.test = "{0}/gold_and_utts.tsv".format(self.test_path)

        # get files containing gold labels/data
        self.train_data_file = pd.read_csv(self.train, sep="\t")
        self.dev_data_file = pd.read_csv(self.dev, sep="\t")
        # self.test_data_file = pd.read_csv(self.test)

        # get tokenizer
        self.tokenizer = get_tokenizer("basic_english")

        # get the number of acoustic features
        self.acoustic_length = acoustic_length

        # to determine whether incoming acoustic features are averaged
        self.avgd = avgd

        self.avgd = False
        self.train_dir = "IS10"
        self.dev_dir = "IS10"
        self.test_dir = "IS10"

        print("Collecting acoustic features")

        # ordered dicts of acoustic data
        # todo: is this screwed up?
        #   ordered dict--is it same order as acoustic_lengths
        (
            self.train_dict,
            self.train_acoustic_lengths,
        ) = make_acoustic_dict_chalearn(
            "{0}/{1}".format(self.train_path, self.train_dir),
            f_end,
            use_cols=use_cols,
            avgd=avgd,
        )
        self.train_dict = OrderedDict(self.train_dict)
        self.dev_dict, self.dev_acoustic_lengths = make_acoustic_dict_chalearn(
            "{0}/{1}".format(self.dev_path, self.dev_dir),
            f_end,
            use_cols=use_cols,
            avgd=avgd,
        )
        self.dev_dict = OrderedDict(self.dev_dict)
        # self.test_dict, self.test_acoustic_lengths = make_acoustic_dict_chalearn(
        #     "{0}/{1}".format(self.test_path, self.test_dir),
        #     f_end,
        #     use_cols=use_cols,
        #     avgd=avgd,
        # )
        # self.test_dict = OrderedDict(self.test_dict)

        # utterance-level dict
        self.longest_utt = self.get_longest_utt_chalearn()

        # get length of longest acoustic dataframe
        self.longest_acoustic = get_max_num_acoustic_frames(
            list(self.train_dict.values())
            + list(self.dev_dict.values())
            # + list(self.test_dict.values())
        )

        print("Finalizing acoustic organization")

        (
            self.train_acoustic,
            self.train_usable_utts,
        ) = make_acoustic_set_chalearn(
            self.train,
            self.train_dict,
            acoustic_length=acoustic_length,
            longest_acoustic=self.longest_acoustic,
            add_avging=add_avging,
            avgd=avgd,
        )
        self.dev_acoustic, self.dev_usable_utts = make_acoustic_set_chalearn(
            self.dev,
            self.dev_dict,
            acoustic_length=acoustic_length,
            longest_acoustic=self.longest_acoustic,
            add_avging=add_avging,
            avgd=avgd,
        )
        # self.test_acoustic, self.test_usable_utts = make_acoustic_set_chalearn(
        #     self.test,
        #     self.test_dict,
        #     acoustic_length=acoustic_length,
        #     longest_acoustic=self.longest_acoustic,
        #     add_avging=add_avging,
        #     avgd=avgd,
        # )

        # get utterance, speaker, y matrices for train, dev, and test sets
        (
            self.train_utts,
            self.train_genders,
            self.train_ethnicities,
            self.train_y_extr,
            self.train_y_neur,
            self.train_y_agree,
            self.train_y_openn,
            self.train_y_consc,
            self.train_y_inter,
            self.train_utt_lengths,
        ) = self.make_data_tensors(
            self.train_data_file, self.train_usable_utts, glove
        )

        (
            self.dev_utts,
            self.dev_genders,
            self.dev_ethnicities,
            self.dev_y_extr,
            self.dev_y_neur,
            self.dev_y_agree,
            self.dev_y_openn,
            self.dev_y_consc,
            self.dev_y_inter,
            self.dev_utt_lengths,
        ) = self.make_data_tensors(
            self.dev_data_file, self.dev_usable_utts, glove
        )

        # (
        #     self.test_utts,
        #     self.test_genders,
        #     self.test_ethnicities,
        #     self.test_y_extr,
        #     self.test_y_neur,
        #     self.test_y_agree,
        #     self.test_y_openn,
        #     self.test_y_consc,
        #     self.test_y_inter,
        #     self.test_utt_lengths,
        # ) = self.make_data_tensors(
        #     self.test_data_file, self.test_usable_utts, glove
        # )

        # set trait weights
        # todo: determine how we're binning and get class weights
        # self.median_openness = torch.median(self.train_y_openn)
        self.mean_openness = torch.mean(self.train_y_openn)
        # print(self.mean_openness)
        # sys.exit()
        # self.openness_weights = get_class_weights()

        # acoustic feature normalization based on train
        self.all_acoustic_means = self.train_acoustic.mean(
            dim=0, keepdim=False
        )
        self.all_acoustic_deviations = self.train_acoustic.std(
            dim=0, keepdim=False
        )

        self.male_acoustic_means, self.male_deviations = get_gender_avgs(
            self.train_acoustic, self.train_genders, gender=1
        )
        self.female_acoustic_means, self.female_deviations = get_gender_avgs(
            self.train_acoustic, self.train_genders, gender=2
        )

        # get the data organized for input into the NNs
        # self.train_data, self.dev_data, self.test_data = self.combine_xs_and_ys()
        self.train_data, self.dev_data = self.combine_xs_and_ys()

    def combine_xs_and_ys(self):
        """
        Combine all x and y data into list of tuples for easier access with DataLoader
        """
        train_data = []
        dev_data = []

        for i, item in enumerate(self.train_acoustic):
            # normalize
            if self.train_genders[i] == 2:
                item_transformed = transform_acoustic_item(
                    item, self.female_acoustic_means, self.female_deviations
                )
            else:
                item_transformed = transform_acoustic_item(
                    item, self.male_acoustic_means, self.male_deviations
                )
            train_data.append(
                (
                    item_transformed,
                    self.train_utts[i],
                    0,  # todo: eventually add speaker ?
                    self.train_genders[i],
                    self.train_ethnicities[i],
                    self.train_y_extr[i],
                    self.train_y_neur[i],
                    self.train_y_agree[i],
                    self.train_y_openn[i],
                    self.train_y_consc[i],
                    self.train_y_inter[i],
                    self.train_utt_lengths[i],
                    self.train_acoustic_lengths[i],
                )
            )

        for i, item in enumerate(self.dev_acoustic):
            if self.train_genders[i] == 2:
                item_transformed = transform_acoustic_item(
                    item, self.female_acoustic_means, self.female_deviations
                )
            else:
                item_transformed = transform_acoustic_item(
                    item, self.male_acoustic_means, self.male_deviations
                )
            dev_data.append(
                (
                    item_transformed,
                    self.dev_utts[i],
                    0,  # todo: eventually add speaker ?
                    self.dev_genders[i],
                    self.dev_ethnicities[i],
                    self.dev_y_extr[i],
                    self.dev_y_neur[i],
                    self.dev_y_agree[i],
                    self.dev_y_openn[i],
                    self.dev_y_consc[i],
                    self.dev_y_inter[i],
                    self.dev_utt_lengths[i],
                    self.dev_acoustic_lengths[i],
                )
            )

        # for i, item in enumerate(self.test_acoustic):
        #     if self.train_genders[i] == 2:
        #         item_transformed = transform_acoustic_item(
        #             item, self.female_acoustic_means, self.female_deviations
        #         )
        #     else:
        #         item_transformed = transform_acoustic_item(
        #             item, self.male_acoustic_means, self.male_deviations
        #         )
        #     test_data.append(
        #         (
        #             item_transformed,
        #             self.test_utts[i],
        #             0,  # todo: eventually add speaker ?
        #             self.test_genders[i],
        #             self.test_ethnicities[i],
        #             self.test_y_extr[i],
        #             self.test_y_neur[i],
        #             self.test_y_agree[i],
        #             self.test_y_openn[i],
        #             self.test_y_consc[i],
        #             self.test_y_inter[i],
        #             self.test_utt_lengths[i],
        #             self.test_acoustic_lengths[i],
        #         )
        #     )

        return train_data, dev_data  # , test_data

    def get_longest_utt_chalearn(self):
        """
        Get the length of the longest utterance and dialogue in the meld
        :return: length of longest utt, length of longest dialogue
        """
        longest = 0

        # get all data splits
        train_utts_df = self.train_data_file
        dev_utts_df = self.dev_data_file
        # test_utts_df = self.test_data_file

        # concatenate them and put utterances in array
        # all_utts_df = pd.concat([train_utts_df, dev_utts_df, test_utts_df], axis=0)
        all_utts_df = pd.concat([train_utts_df, dev_utts_df], axis=0)

        all_utts = all_utts_df["utterance"].tolist()

        for i, item in enumerate(all_utts):
            try:
                item = clean_up_word(item)
            except AttributeError:  # at least one item is blank and reads in as a float
                item = "<UNK>"
            item = self.tokenizer(item)
            if len(item) > longest:
                longest = len(item)

        return longest

    def make_data_tensors(self, all_utts_df, all_utts_list, glove):
        """
        Prepare the tensors of utterances + genders, gold labels
        :param all_utts_df: the df containing the text (in column 0)
        :param all_utts_list: a list of all usable utterances
        :param glove: an instance of class Glove
        :return:
        """
        # create holders for the data
        all_utts = []
        all_genders = []
        all_ethnicities = []
        all_extraversion = []
        all_neuroticism = []
        all_agreeableness = []
        all_openness = []
        all_conscientiousness = []
        all_interview = []

        # create holder for sequence lengths information
        utt_lengths = []

        for idx, row in all_utts_df.iterrows():

            # check to make sure this utterance is used
            audio_name = row["file"]
            audio_id = audio_name.split(".mp4")[0]
            if audio_id in all_utts_list:

                # create utterance-level holders
                utts = [0] * self.longest_utt

                # get values from row
                try:
                    utt = clean_up_word(row["utterance"])
                except AttributeError:  # at least one item is blank and reads in as a float
                    utt = "<UNK>"
                utt = self.tokenizer(utt)
                utt_lengths.append(len(utt))

                gen = row["gender"]
                eth = row["ethnicity"]
                extra = row["extraversion"]
                neur = row["neuroticism"]
                agree = row["agreeableness"]
                openn = row["openness"]
                consc = row["conscientiousness"]
                inter = row["invite_to_interview"]

                # convert words to indices for glove
                utt_indexed = glove.index(utt)
                for i, item in enumerate(utt_indexed):
                    utts[i] = item

                all_utts.append(torch.tensor(utts))
                all_genders.append(gen)
                all_ethnicities.append(eth)
                all_extraversion.append(extra)
                all_neuroticism.append(neur)
                all_agreeableness.append(agree)
                all_openness.append(openn)
                all_conscientiousness.append(consc)
                all_interview.append(inter)

        # create pytorch tensors for each
        all_genders = torch.tensor(all_genders)
        all_ethnicities = torch.tensor(all_ethnicities)
        all_extraversion = torch.tensor(all_extraversion)
        all_neuroticism = torch.tensor(all_neuroticism)
        all_agreeableness = torch.tensor(all_agreeableness)
        all_openness = torch.tensor(all_openness)
        all_conscientiousness = torch.tensor(all_conscientiousness)
        all_interview = torch.tensor(all_interview)

        # return data
        return (
            all_utts,
            all_genders,
            all_ethnicities,
            all_extraversion,
            all_neuroticism,
            all_agreeableness,
            all_openness,
            all_conscientiousness,
            all_interview,
            utt_lengths,
        )


def convert_chalearn_pickle_to_json(path, file):
    """
    Convert the pickled data files for chalearn into json files
    """
    fname = file.split(".pkl")[0]
    pickle_file = os.path.join(path, file)
    with open(pickle_file, "rb") as pfile:
        # use latin-1 enecoding to avoid readability issues
        data = pickle.load(pfile, encoding="latin1")

    json_file = os.path.join(path, fname + ".json")
    with open(json_file, "w") as jfile:
        json.dump(data, jfile)


def preprocess_chalearn_data(
    base_path, acoustic_save_dir, smile_path, acoustic_feature_set="IS10"
):
    """
    Preprocess the ravdess data by extracting acoustic features from wav files
    base_path : the path to the base RAVDESS directory
    paths : list of paths where audio is located
    acoustic_save_dir : the directory in which to save acoustic feature files
    smile_path : the path to OpenSMILE
    acoustic_feature_set : the feature set to use with ExtractAudio
    """
    path_to_train = os.path.join(base_path, "train")
    path_to_dev = os.path.join(base_path, "val")
    paths = [path_to_train, path_to_dev]

    for p in paths:
        # set path to audio files
        path_to_files = os.path.join(p, "mp4")
        # set path to acoustic feats
        acoustic_save_path = os.path.join(p, acoustic_save_dir)
        # create the save directory if it doesn't exist
        if not os.path.exists(acoustic_save_path):
            os.makedirs(acoustic_save_path)

        # extract features using opensmile
        for audio_file in os.listdir(path_to_files):
            audio_name = audio_file.split(".wav")[0]
            audio_save_name = (
                str(audio_name) + "_" + acoustic_feature_set + ".csv"
            )
            extractor = ExtractAudio(
                path_to_files, audio_file, acoustic_save_path, smile_path
            )
            extractor.save_acoustic_csv(
                feature_set=acoustic_feature_set, savename=audio_save_name
            )


def create_gold_tsv_chalearn(gold_file, utts_file, gender_file, save_name):
    """
    Create the gold tsv file from a json file
    gold_file : path to JSON file containing y values
    utts_file : path to JSON transcription file
    gender_file : the path to a CSV file with gender info
    """
    with open(gold_file, "r") as jfile:
        data = json.load(jfile)

    with open(utts_file, "r") as j2file:
        utts_dict = json.load(j2file)

    genders = pd.read_csv(gender_file)
    genders_dict = dict(zip(genders["VideoName"], genders["Gender"]))
    ethnicity_dict = dict(zip(genders["VideoName"], genders["Ethnicity"]))

    all_files_utts = sorted(utts_dict.keys())
    all_files = sorted(data["extraversion"].keys())

    if all_files != all_files_utts:
        print("utts dict and gold labels don't contain the same set of files")
    if all_files != sorted(genders_dict.keys()):
        print(
            "gold labels and gender labels don't contain the same set of files"
        )

    with open(save_name, "w") as tsvfile:
        tsvfile.write(
            "file\tgender\tethnicity\textraversion\tneuroticism\t"
            "agreeableness\topenness\tconscientiousness\tinvite_to_interview\tutterance\n"
        )
        for item in all_files:
            gender = genders_dict[item]
            ethnicity = ethnicity_dict[item]
            extraversion = data["extraversion"][item]
            neuroticism = data["neuroticism"][item]
            agreeableness = data["agreeableness"][item]
            openness = data["openness"][item]
            conscientiousness = data["conscientiousness"][item]
            interview = data["interview"][item]
            try:
                utterance = utts_dict[item]
            except KeyError:
                utterance = ""
            tsvfile.write(
                f"{item}\t{gender}\t{ethnicity}\t{extraversion}\t{neuroticism}\t{agreeableness}\t"
                f"{openness}\t{conscientiousness}\t{interview}\t{utterance}\n"
            )


def make_acoustic_dict_chalearn(
    acoustic_path, f_end="_IS10.csv", use_cols=None, avgd=True
):
    """
    makes a dict of clip_id: data for use in MELD objects
    f_end: end of acoustic file names
    use_cols: if set, should be a list [] of column names to include
    n_to_skip : the number of columns at the start to ignore (e.g. name, time)
    """
    acoustic_dict = {}
    # acoustic_lengths = []
    acoustic_lengths = {}
    # find acoustic features files
    for f in os.listdir(acoustic_path):
        if f.endswith(f_end):
            # set the separator--non-averaged files are ;SV
            separator = ";"

            # read in the file as a dataframe
            if use_cols is not None:
                feats = pd.read_csv(
                    acoustic_path + "/" + f, usecols=use_cols, sep=separator
                )
            else:
                feats = pd.read_csv(acoustic_path + "/" + f, sep=separator)
                if not avgd:
                    feats.drop(["name", "frameTime"], axis=1, inplace=True)

            # get the dialogue and utterance IDs
            id = f.split("_IS10")[0]

            # save the dataframe to a dict with (dialogue, utt) as key
            if feats.shape[0] > 0:
                acoustic_dict[id] = feats.values.tolist()
                acoustic_lengths[id] = feats.shape[0]

    # sort acoustic lengths so they are in the same order as other data
    acoustic_lengths = [
        value for key, value in sorted(acoustic_lengths.items())
    ]

    return acoustic_dict, acoustic_lengths


def make_acoustic_set_chalearn(
    text_path,
    acoustic_dict,
    acoustic_length,
    longest_acoustic,
    add_avging=True,
    avgd=False,
):
    """
    Prep the acoustic data using the acoustic dict
    :param text_path: FULL path to file containing utterances + labels
    :param acoustic_dict:
    :param add_avging: whether to average the feature sets
    :return:
    """
    # read in the acoustic csv
    if type(text_path) == str:
        all_utts_df = pd.read_csv(text_path, sep="\t")
    elif type(text_path) == pd.core.frame.DataFrame:
        all_utts_df = text_path
    else:
        sys.exit("text_path is of unaccepted type.")

    # get lists of valid dialogues and utterances
    valid_utts = all_utts_df["file"].tolist()

    # set holders for acoustic data
    all_acoustic = []
    usable_utts = []

    # for all items with audio + gold label
    for idx, item in enumerate(valid_utts):
        item_id = item.split(".mp4")[0]
        # if that dialogue and utterance appears has an acoustic feats file
        if item_id in acoustic_dict.keys():

            # pull out the acoustic feats dataframe
            acoustic_data = acoustic_dict[item_id]

            # add this dialogue + utt combo to the list of possible ones
            usable_utts.append(item_id)

            if not avgd and not add_avging:
                # set intermediate acoustic holder
                acoustic_holder = [[0] * acoustic_length] * longest_acoustic

                # add the acoustic features to the holder of features
                for i, feats in enumerate(acoustic_data):
                    # for now, using longest acoustic file in TRAIN only
                    if i >= longest_acoustic:
                        break
                    # needed because some files allegedly had length 0
                    for j, feat in enumerate(feats):
                        acoustic_holder[i][j] = feat
            else:
                if avgd:
                    acoustic_holder = acoustic_data
                elif add_avging:
                    acoustic_holder = torch.mean(
                        torch.tensor(acoustic_data), dim=0
                    )

            # add features as tensor to acoustic data
            all_acoustic.append(torch.tensor(acoustic_holder))

    # pad the sequence and reshape it to proper format
    # this is here to keep the formatting for acoustic RNN
    all_acoustic = nn.utils.rnn.pad_sequence(all_acoustic)
    all_acoustic = all_acoustic.transpose(0, 1)

    return all_acoustic, usable_utts


def reorganize_gender_annotations_chalearn(path, genderfile, transcriptfile):
    """
    Use the file containing transcriptions of utterances to compare files
    and separate gender annotation val file into 2 csv files
    path : the path to the dataset
    genderfile : the path to the file containing the val gender key
    transcriptfile : the path to the file containing transcriptions for val set
    """
    # get gender dataframe
    genf = pd.read_csv(genderfile, sep=";")

    # get transcription json
    with open(transcriptfile, "r") as tfile:
        dev_data = json.load(tfile)

    # get list of files in dev set
    dev_files = dev_data.keys()

    print(len(dev_files))

    # get gender dataframes for dev and train
    genf_dev = genf[genf["VideoName"].isin(dev_files)]
    genf_train = genf[~genf["VideoName"].isin(dev_files)]

    print(genf.shape)
    print(genf_train.shape)
    print(genf_dev.shape)

    val_saver = os.path.join(path, "val/gender_annotations_val.csv")
    train_saver = os.path.join(path, "train/gender_annotations_train.csv")

    genf_dev.to_csv(val_saver, index=False)
    genf_train.to_csv(train_saver, index=False)


if __name__ == "__main__":
    # path to data
    path = "../../datasets/multimodal_datasets/Chalearn/"
    train_path = os.path.join(path, "train/mp4")
    val_path = os.path.join(path, "val/mp4")
    paths = [train_path, val_path]
    # path to opensmile
    smile_path = "~/opensmile-2.3.0"
    # acoustic set to extract
    acoustic_set = "IS10"

    # # 1. convert pickle to json
    # file_1 = "annotation_validation.pkl"
    # file_2 = "transcription_validation.pkl"
    #
    # convert_chalearn_pickle_to_json(path, file_1)
    # convert_chalearn_pickle_to_json(path, file_2)

    # # 2. convert mp4 to wav
    # for p in paths:
    #     print(p)
    #     print("====================================")
    #     for f in os.listdir(p):
    #         if f.endswith(".mp4"):
    #             print(f)
    #             convert_mp4_to_wav(os.path.join(p, f))

    # 3. preprocess files
    # preprocess_chalearn_data(path, "IS10", smile_path, acoustic_set)

    # 3.1 reorganize gender annotations file
    # gender_file = os.path.join(path, "val/gender_anntoations_val.csv")
    # anno_file = os.path.join(path, "val/transcription_validation.json")
    # reorganize_gender_annotations_chalearn(path, gender_file, anno_file)

    # 4. create a gold CSV to examine data more closely by hand
    # dev_gold_json_path = os.path.join(path, "val/annotation_validation.json")
    # dev_utts_json_path = os.path.join(path, "val/transcription_validation.json")
    # dev_gender_file = os.path.join(path, "val/gender_annotations_val.csv")
    # dev_save_name = os.path.join(path, "val/gold_and_utts.tsv")
    # create_gold_tsv_chalearn(
    #     dev_gold_json_path, dev_utts_json_path, dev_gender_file, dev_save_name
    # )
    #
    # train_gold_json_path = os.path.join(path, "train/annotation_training.json")
    # train_utts_json_path = os.path.join(path, "train/transcription_training.json")
    # train_gender_file = os.path.join(path, "train/gender_annotations_train.csv")
    # train_save_name = os.path.join(path, "train/gold_and_utts.tsv")
    # create_gold_tsv_chalearn(
    #     train_gold_json_path, train_utts_json_path, train_gender_file, train_save_name
    # )
