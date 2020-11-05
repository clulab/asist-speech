# test the models created in py_code directory with ASIST dataset
# currently the main entry point into the system
# add "prep_data" as an argument when running this from command line
#       if your acoustic features have not been extracted from audio
##########################################################
from tomcat_speech.data_prep.asist_data.asist_dataset_creation import (
    AsistDataset,
)
from tomcat_speech.models.train_and_test_models import *
from tomcat_speech.models.input_models import *

from tomcat_speech.data_prep.data_prep_helpers import *

# import parameters for model
# comment or uncomment as needed
# from tomcat_speech.models.parameters.bimodal_params import params
from tomcat_speech.models.parameters.multitask_params import params
# from tomcat_speech.data_prep.asist_data.gender_classifier import genderclassifier

# from tomcat_speech.models.parameters.multitask_params import params
# from tomcat_speech.models.parameters.lr_baseline_1_params import params
# from tomcat_speech.models.parameters.multichannel_cnn_params import params

import numpy as np
import random
import torch
import sys

p = "~"

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input_dir",
        help="Directory in which the input data resides",
        default="output/asist_audio",  # check if default needed
    )
    parser.add_argument(
        "--glove_file",
        help="Path to Glove file",
        default="glove.short.300d.punct.txt",
    )

    # to test the data--this doesn't contain real outcomes
    parser.add_argument(
        "--ys_path",
        help="Path to ys file",
        default=None, # exit condition
    )
    parser.add_argument(
        "--media_type",
        help="mp3, m4a, mp4 or wav",
        default=None,  # check this
    )
    parser.add_argument(
        "--saved-model",
        help="enter the path to saved model you would like to use in testing",
        default="tomcat_speech/EMOTION_MODEL_FOR_ASIST_batch100_100hidden_2lyrs_lr0.01.pth"
    )
    parser.add_argument(
        "--acoustic_dict",
        help="choose type of transcript used: aws or zoom",
        default="aws",
    )

    args = parser.parse_args()

    # set device
    cuda = True
    # Check CUDA
    if not torch.cuda.is_available():
        cuda = False
    device = torch.device("cuda" if cuda else "cpu")

    # set random seed
    seed = params.seed
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    if cuda:
        torch.cuda.manual_seed_all(seed)

    # set parameters for data prep
    # If error in glove path, switch with:
    ## If calling this from another pthon script:

    # set number of splits
    num_splits = 1
    # set model name and model type
    model = params.model
    model_type = "BimodalCNN_k=4"
    # set number of columns to skip in data input files
    cols_to_skip = 4  # 2 for Zoom, 4 for AWS

    # path to directory where best models are saved
    model_save_path = "output/models/"  # pass parameter!

    # make sure the full save path exists; if not, create it
    os.makedirs(model_save_path, exist_ok=True)

    # decide if you want to plot the loss/accuracy curves for training
    # get_plot = True
    # model_plot_path = "output/plots/"
    # os.system(
    #     'if [ ! -d "{0}" ]; then mkdir -p {0}; fi'.format(model_plot_path)
    # )

    # decide if you want to use avgd feats
    avgd_acoustic = params.avgd_acoustic or params.add_avging
    # avgd_acoustic_in_network = params.add_avging
    # set the path to the trained model

    # 0. RUN ASIST DATA PREP AND REORGANIZATION FOR INPUT INTO THE MODEL
    # use argparse instead: see if this is even needed. Important to use one method.
    # see if this can be moved to asist_prep.py instead
    if args.media_type == "mp4":
        os.system(
            "time python tomcat_speech/data_prep/asist_data/asist_prep.py mp4_data"
        )  # fixme
    elif args.media_type == "m4a":
        os.system(
            "time python tomcat_speech/data_prep/asist_data/asist_prep.py m4a_data"
        )  # fixme
    elif args.media_type == "mp3":
        os.system(
            "time python tomcat_speech/data_prep/asist_data/asist_prep.py mp3_data"
        )  # fixme
    elif args.media_type == "wav":
        os.system(
            "time python tomcat_speech/data_prep/asist_data/asist_prep.py"
        )  # fixme

    # 1. IMPORT AUDIO AND TEXT
    # make acoustic dict
    if args.acoustic_dict == "aws":
        acoustic_dict = make_acoustic_dict(
            args.input_dir,
            "_avgd.csv",
            use_cols=[
                "word",
                "speaker",
                "utt_num",
                "word_num",
                "pcm_loudness_sma",
                "F0finEnv_sma",
                "voicingFinalUnclipped_sma",
                "jitterLocal_sma",
                "shimmerLocal_sma",
                "pcm_loudness_sma_de",
                "F0finEnv_sma_de",
                "voicingFinalUnclipped_sma_de",
                "jitterLocal_sma_de",
                "shimmerLocal_sma_de",
            ],
            data_type="asist",
        )
    elif args.acoustic_dict == "zoom":
        acoustic_dict = make_acoustic_dict(
            input_dir,
            "_avgd.csv",
            use_cols=[
                "speaker",
                "utt",
                "pcm_loudness_sma",
                "F0finEnv_sma",
                "voicingFinalUnclipped_sma",
                "jitterLocal_sma",
                "shimmerLocal_sma",
                "pcm_loudness_sma_de",
                "F0finEnv_sma_de",
                "voicingFinalUnclipped_sma_de",
                "jitterLocal_sma_de",
                "shimmerLocal_sma_de",
            ],
                data_type="asist",
        )
    print("Acoustic dict created")

    # 2. IMPORT GLOVE + MAKE GLOVE OBJECT
    glove_dict = make_glove_dict(args.glove_file)
    glove = Glove(glove_dict)
    print("Glove object created")

    # 3. MAKE DATASET
    data = AsistDataset(
        acoustic_dict,
        glove,
        cols_to_skip=cols_to_skip,
        splits=1,
        sequence_prep="pad",
        truncate_from="start",
        norm=None,
        add_avging=params.add_avging,
    )

    # get data for testing
    test_data = data.current_split
    test_ds = DatumListDataset(test_data, None)
    print("Dataset created")
    # 6. CREATE NN
    # get set of pretrained embeddings and their shape
    pretrained_embeddings = glove.data
    num_embeddings = pretrained_embeddings.size()[0]
    print(
        f"shape of pretrained embeddings is: {data.glove.data.size()}"
    )
    # create test model
    classifier = EarlyFusionMultimodalModel(
        params=params,
        num_embeddings=num_embeddings,
        pretrained_embeddings=pretrained_embeddings,
    )
    # get saved parameters
    classifier.load_state_dict(torch.load(args.saved_model))
    classifier.to(device)
    # test the model
    ordered_predictions = predict_without_gold_labels(
        classifier,
        test_ds,
        params.batch_size,
        device,
        avgd_acoustic=avgd_acoustic,
        use_speaker=params.use_speaker,
        use_gender=params.use_gender,
    )
    print(ordered_predictions)
    # todo: add function to save predictions to json