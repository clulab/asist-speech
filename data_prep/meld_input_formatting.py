# read meld into the system
import os
import pprint
import sys

import pandas as pd
import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset

from data_prep.data_prep import clean_up_word
from collections import OrderedDict


class MELDData(Dataset):
    # a dataset to hold the MELD data in before passing to NNs
    def __init__(self, meld_path, glove, acoustic_length, f_end="_IS10.csv", use_cols=None):
        # self.f_end = f_end
        self.train_path = meld_path + "/train"
        self.dev_path = meld_path + "/dev"
        self.test_path = meld_path + "/test"
        self.meld_train = "{0}/train_sent_emo.csv".format(self.train_path)
        self.meld_dev = "{0}/dev_sent_emo.csv".format(self.dev_path)
        self.meld_test = "{0}/test_sent_emo.csv".format(self.test_path)

        # get the number of acoustic features
        self.acoustic_length = acoustic_length

        # Glove object
        self.glove = glove

        print("Collecting acoustic features")

        # ordered dicts of acoustic data
        self.train_dict = OrderedDict(self.make_acoustic_dict_meld("{0}/audios".format(self.train_path), f_end, use_cols))
        self.dev_dict = OrderedDict(self.make_acoustic_dict_meld("{0}/audios".format(self.dev_path), f_end, use_cols))
        self.test_dict = OrderedDict(self.make_acoustic_dict_meld("{0}/audios".format(self.test_path), f_end, use_cols))

        # utterance-level dict
        self.longest_utt, self.longest_dia = self.get_longest_utt_meld()

        print("Finalizing acoustic organization")

        self.train_acoustic, self.train_usable_utts = self.make_acoustic_set(self.meld_train, self.train_dict)
        # print(type(self.train_acoustic))
        # sys.exit(1)
        self.dev_acoustic, self.dev_usable_utts = self.make_acoustic_set(self.meld_dev, self.dev_dict)
        self.test_acoustic, self.test_usable_utts = self.make_acoustic_set(self.meld_test, self.test_dict)

        print("Getting text, speaker, and y features")

        # get utterance, speaker, y matrices for train, dev, and test sets
        self.train_utts, self.train_spkrs, self.train_y_emo, self.train_y_sent = self.make_utt_dict_meld(self.meld_train,
                                                                                                         self.train_usable_utts)
        self.dev_utts, self.dev_spkrs, self.dev_y_emo, self.dev_y_sent = self.make_utt_dict_meld(self.meld_dev,
                                                                                                 self.dev_usable_utts)
        self.test_utts, self.test_spkrs, self.test_y_emo, self.test_y_sent = self.make_utt_dict_meld(self.meld_test,
                                                                                                     self.test_usable_utts)

        # get the data organized for input into the NNs
        self.train_data, self.dev_data, self.test_data = self.combine_xs_and_ys()

    def combine_xs_and_ys(self):
        # combine all x and y data into list of tuples for easier access with DataLoader
        train_data = []
        dev_data = []
        test_data = []

        # print(len(self.train_acoustic))
        # print(len(self.train_utts))
        # print(len(self.train_spkrs))
        # print(len(self.train_y_emo))
        # print(len(self.train_y_sent))
        # print(type(self.train_acoustic))

        for i, item in enumerate(self.train_acoustic):
            # print(i)
            # print(type(item))
            # print(item)
            # sys.exit(1)
            train_data.append((item, self.train_utts[i], self.train_spkrs[i], self.train_y_emo[i], self.train_y_sent[i]))

        for i, item in enumerate(self.dev_acoustic):
            dev_data.append((item, self.dev_utts[i], self.dev_spkrs[i], self.dev_y_emo[i], self.dev_y_sent[i]))

        for i, item in enumerate(self.test_acoustic):
            test_data.append((item, self.test_utts[i], self.test_spkrs[i], self.test_y_emo[i], self.test_y_sent[i]))

        # print(type(train_data))
        # sys.exit(1)
        return train_data, dev_data, test_data

    def get_longest_utt_meld(self):
        """
        Get the length of the longest utterance and dialogue in the meld
        :return: length of longest utt, length of longest dialogue
        """
        longest = 0

        # get all data splits
        train_utts_df = pd.read_csv(self.meld_train)
        dev_utts_df = pd.read_csv(self.meld_dev)
        test_utts_df = pd.read_csv(self.meld_test)

        # concatenate them and put utterances in array
        all_utts_df = pd.concat([train_utts_df, dev_utts_df, test_utts_df], axis=0)
        all_utts = all_utts_df["Utterance"].tolist()

        # get longest dialogue length
        longest_dia = max(all_utts_df['Utterance_ID'].tolist()) + 1  # because 0-indexed

        # check lengths and return len of longest
        for utt in all_utts:
            split_utt = utt.strip().split(" ")
            utt_len = len(split_utt)
            if utt_len > longest:
                longest = utt_len

        return longest, longest_dia

    def make_utt_dict_meld(self, text_path, all_utts_list):
        """
        Make a dict of (dia, utt): [words]
        :param text_path: the FULL path to a csv containing the text (in column 0)
        :param all_utts_list: a list of all usable utterances
        :return:
        """
        # holders for the data
        all_utts = []
        all_speakers = []
        all_emotions = []
        all_sentiments = []

        all_utts_df = pd.read_csv(text_path)
        dialogue = 0

        # dialogue-level holders
        utts = [[0] * self.longest_utt] * self.longest_dia
        spks = [0] * self.longest_dia
        emos = [0] * self.longest_dia
        sents = [0] * self.longest_dia

        for idx, row in all_utts_df.iterrows():

            # check to make sure this utterance is used
            dia_num, utt_num = row['DiaID_UttID'].split("_")[:2]
            if (dia_num, utt_num) in all_utts_list:

                dia_id = row['Dialogue_ID']
                utt_id = row['Utterance_ID']
                utt = row["Utterance"]
                utt = [clean_up_word(wd) for wd in utt.strip().split(" ")]

                spk_id = row['Speaker']
                emo = row['Emotion']
                sent = row['Sentiment']

                # utterance-level holder
                idxs = [0] * self.longest_utt

                # convert words to indices for glove
                for ix, wd in enumerate(utt):
                    # print(ix, wd)
                    if wd in self.glove.wd2idx.keys():
                        # print(glove.wd2idx[wd])
                        # idxs.append(glove.wd2idx[wd])
                        idxs[ix] = self.glove.wd2idx[wd]
                    else:
                        # idxs.append(glove.wd2idx['<UNK>'])
                        idxs[ix] = self.glove.wd2idx['<UNK>']

                if dialogue == dia_id:
                    # utts.append(idxs)
                    # print(len(utts), utt_id, utt)
                    utts[utt_id] = idxs
                    spks[utt_id] = spk_id
                    emos[utt_id] = emo
                    sents[utt_id] = sent
                    # print("actually finished this")
                else:
                    # all_utts.append(torch.tensor(utts))
                    # print(utts)
                    # sys.exit(1)
                    all_utts.append(torch.tensor(utts))
                    all_speakers.append(spks)
                    all_emotions.append(emos)
                    all_sentiments.append(sents)

                    # utt_dict[dia_id] = utts
                    dialogue = dia_id

                    # dialogue-level holders
                    utts = [[0] * self.longest_utt] * self.longest_dia
                    spks = [0] * self.longest_dia
                    emos = [0] * self.longest_dia
                    sents = [0] * self.longest_dia

                    # # re-zero utterance-level holder
                    # idxs = [0] * self.longest_utt

                    # utts.append(idxs)
                    utts[utt_id] = idxs
                    spks[utt_id] = spk_id
                    emos[utt_id] = emo
                    sents[utt_id] = sent

        # print(len(all_utts))
        # print(len(all_utts[0]))
        # print(len(all_utts[-1][0]))
        # utt_dict = torch.tensor(utt_dict)
        # utt_dict = nn.utils.rnn.pad_sequence(utt_dict)
        # all_utts = np.asarray(all_utts)
        # all_speakers = np.asarray(all_speakers)
        # all_emotions = np.asarray(all_emotions)
        # all_sentiments = np.asarray(all_sentiments)

        all_speakers = torch.tensor(all_speakers)
        all_emotions = torch.tensor(all_emotions)
        all_sentiments = torch.tensor(all_sentiments)

        all_utts = nn.utils.rnn.pad_sequence(all_utts)
        # all_speakers = nn.utils.rnn.pad_sequence(all_speakers)
        # all_emotions = nn.utils.rnn.pad_sequence(all_emotions)
        # all_sentiments = nn.utils.rnn.pad_sequence(all_sentiments)

        all_utts = all_utts.transpose(0, 1)
        # all_speakers = all_speakers.transpose(0, 1)
        # all_emotions = all_emotions.transpose(0, 1)
        # all_sentiments = all_sentiments.transpose(0, 1)

        print(all_speakers.shape)
        print(all_emotions.shape)
        print(all_sentiments.shape)
        print(all_utts.shape)
        # sys.exit(1)

        # return data
        return all_utts, all_speakers, all_emotions, all_sentiments

    def make_acoustic_dict_meld(self, acoustic_path, f_end="_IS10.csv", use_cols=None):
        """
        makes a dict of (sid, call): data for use in ClinicalDataset objects
        f_end: end of acoustic file names
        use_cols: if set, should be a list [] of column names to include
        """
        acoustic_dict = {}
        for f in os.listdir(acoustic_path):
            if f.endswith(f_end):
                if use_cols is not None:
                    feats = pd.read_csv(acoustic_path + "/" + f, usecols=use_cols)
                else:
                    feats = pd.read_csv(acoustic_path + "/" + f)
                dia_id = f.split("_")[0]
                utt_id = f.split("_")[1]
                acoustic_dict[(dia_id, utt_id)] = feats.values.tolist()[0]
        return acoustic_dict

    def make_acoustic_set(self, text_path, acoustic_dict):
        """
        Prep the acoustic data using the acoustic dict
        :param text_path: FULL path to file containing utterances + labels
        :param acoustic_dict:
        :return:
        """
        all_utts_df = pd.read_csv(text_path)
        valid_dia_utt = all_utts_df['DiaID_UttID'].tolist()
        valid_dia = all_utts_df['Dialogue_ID'].tolist()
        valid_utt = all_utts_df['Utterance_ID'].tolist()

        # make sure this works
        # print(valid_dia_utt)
        # print(sorted(acoustic_dict.keys()))

        # for i, item in enumerate(valid_dia_utt):
        #     print("{0}\t{1}\t{2}".format(item, valid_dia[i], valid_utt[i]))

        dialogue = 0

        all_acoustic = []
        usable_utts = []

        intermediate_acoustic = [[0] * self.acoustic_length] * self.longest_dia
        # print(len(intermediate_acoustic))
        # print(len(intermediate_acoustic[0]))
        # print(len(intermediate_acoustic))
        # print(len(valid_dia_utt))
        # print(len(valid_dia))
        # sys.exit(1)
        # c = 0

        for idx, item in enumerate(valid_dia_utt):
            # print(item.split("_")[0], item.split("_")[1])
            if (item.split("_")[0], item.split("_")[1]) in acoustic_dict.keys():
                acoustic_data = acoustic_dict[(item.split("_")[0], item.split("_")[1])]
                usable_utts.append((item.split("_")[0], item.split("_")[1]))

                # print(acoustic_data)
                # sys.exit(1)

                if dialogue == valid_dia[idx]:
                    utt_num = valid_utt[idx]
                    # intermediate_acoustic[utt_num] = acoustic_data
                    for i, feat in enumerate(acoustic_data):
                        intermediate_acoustic[utt_num][i] = feat
                    # print("This is working")
                    # c += 1
                else:
                    # print(intermediate_acoustic)
                    # print(type(intermediate_acoustic))
                    # print(len(intermediate_acoustic))
                    # print(len(intermediate_acoustic[0]))
                    all_acoustic.append(torch.tensor(intermediate_acoustic))
                    # sys.exit(1)
                    # print(len(all_acoustic))

                    dialogue = valid_dia[idx]

                    intermediate_acoustic = [[0] * self.acoustic_length] * self.longest_dia

                    utt_num = valid_utt[idx]
                    # intermediate_acoustic[utt_num] = acoustic_data
                    for i, feat in enumerate(acoustic_data):
                        intermediate_acoustic[utt_num][i] = feat

        all_acoustic = nn.utils.rnn.pad_sequence(all_acoustic)
        all_acoustic = all_acoustic.transpose(0, 1)
        # print(c)
        # all_acoustic = np.asarray(all_acoustic)
        # print(type(all_acoustic))
        # print(all_acoustic.shape)
        # print(type(all_acoustic[0]))
        # print(all_acoustic[0].shape)
        # sys.exit(1)

        return all_acoustic, usable_utts
