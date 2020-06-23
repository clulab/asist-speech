# implement training and testing for models

from collections import OrderedDict

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np

# import parameters for model
from torch.utils.data import DataLoader

from models.bimodal_models import BimodalCNN
from models.parameters.bimodal_params import *
from models.plot_training import *


# adapted from https://github.com/joosthub/PyTorchNLPBook/blob/master/chapters/chapter_6/classifying-surnames/Chapter-6-Surname-Classification-with-RNNs.ipynb
def make_train_state(learning_rate, model_save_path, model_save_file):
    # makes a train state to save information on model during training/testing
    return {'stop_early': False,
            'early_stopping_step': 0,
            'early_stopping_best_val': 1e8,
            'learning_rate': learning_rate,
            'epoch_index': 0,
            'train_loss': [],
            'train_acc': [],
            'val_loss': [],
            'val_acc': [],
            'best_val_loss': [],
            'best_val_acc': [],
            'best_loss': 100,
            'test_loss': -1,
            'test_acc': -1,
            'model_filename': model_save_path + model_save_file}


def update_train_state(model, train_state):
    """Handle the training state updates.

    Components:
     - Early Stopping: Prevent overfitting.
     - Model Checkpoint: Model is saved if the model is better

    :param args: main arguments
    :param model: model to train
    :param train_state: a dictionary representing the training state values
    :returns:
        a new train_state
    """

    # Save one model at least
    if train_state['epoch_index'] == 0:
        torch.save(model.state_dict(), train_state['model_filename'])
        train_state['stop_early'] = False

        # use best validation accuracy for early stopping
        train_state['early_stopping_best_val'] = train_state['val_loss'][-1]
        train_state['best_val_acc'] = train_state['val_acc'][-1]

    # Save model if performance improved
    elif train_state['epoch_index'] >= 1:
        loss_t = train_state['val_loss'][-1]

        # If loss worsened relative to BEST
        if loss_t >= train_state['early_stopping_best_val']:
            # Update step
            train_state['early_stopping_step'] += 1
        # Loss decreased
        else:
            # Save the best model
            if loss_t < train_state['early_stopping_best_val']:
                torch.save(model.state_dict(), train_state['model_filename'])
                train_state['early_stopping_best_val'] = loss_t
                train_state['best_val_acc'] = train_state['val_acc'][-1]

            # Reset early stopping step
            train_state['early_stopping_step'] = 0

        # Stop early ?
        train_state['stop_early'] = \
            train_state['early_stopping_step'] >= params.early_stopping_criteria

    return train_state


def generate_batches(data, batch_size, shuffle=True, device="cpu"):
    # feed data into dataloader for automatic batch splitting and shuffling
    batched_split = DataLoader(data, batch_size=batch_size, shuffle=shuffle)

    # holders for final data
    acoustic = []
    embedding = []
    speaker = []
    y = []
    lengths = []

    acoustic_batches = [item[0] for item in batched_split]
    embedding_batches = [item[1] for item in batched_split]
    speaker_batches = [item[2] for item in batched_split]
    y_batches = [item[3] for item in batched_split]
    length_batches = [item[5] for item in batched_split]

    [acoustic.append(item.to(device)) for item in acoustic_batches]
    [embedding.append(item.to(device)) for item in embedding_batches]
    [speaker.append(item.to(device)) for item in speaker_batches]
    [y.append(item.to(device)) for item in y_batches]
    [lengths.append(item.to(device)) for item in length_batches]

    return acoustic, embedding, speaker, y, lengths


def train_and_predict(classifier, train_state, train_splits, val_data, batch_size, num_epochs,
                      loss_func, optimizer, device="cpu", scheduler=None, model2=None,
                      train_state2=None):

    for epoch_index in range(num_epochs):
        print("Now starting epoch {0}".format(epoch_index))

        train_state['epoch_index'] = epoch_index

        # Iterate over training dataset
        running_loss = 0.0
        running_acc = 0.0

        # set classifier(s) to training mode
        classifier.train()

        if model2 is not None:
            train_state2['epoch_index'] = epoch_index
            model2.train()

        acoustic_batches, embedding_batches, speaker_batches, y_batches, length_batches = \
            generate_batches(train_splits, batch_size, shuffle=True, device=device)

        # for each batch in the list of batches created by the dataloader
        for batch_index, batch_array in enumerate(acoustic_batches):
            # get the gold labels
            y_gold = y_batches[batch_index].float()

            # step 1. zero the gradients
            optimizer.zero_grad()

            # step 2. compute the output
            class_pred = classifier(acoustic_input=batch_array, text_input=embedding_batches[batch_index],
                                    speaker_input=speaker_batches[batch_index],
                                    length_input=length_batches[batch_index])

            # if we're using multitask, include the decoder
            if model2 is not None:
                # get output of model 2, if using
                y_pred = model2(class_pred)
            else:
                y_pred = class_pred

            # uncomment for prediction spot-checking during training
            # print(y_pred)
            # print(y_gold)
            # sys.exit(1)

            # step 3. compute the loss
            y_gold = torch.tensor([item.index(max(item)) for item in y_gold.tolist()])

            # print(y_pred)

            loss = loss_func(y_pred, y_gold)
            loss_t = loss.item()  # loss for the item

            if len(list(y_pred.size())) > 1:
                y_pred = torch.tensor([item.index(max(item)) for item in y_pred.tolist()])
            else:
                y_pred = torch.round(y_pred)

            # calculate running loss
            running_loss += (loss_t - running_loss) / (batch_index + 1)

            # step 4. use loss to produce gradients
            loss.backward()

            # step 5. use optimizer to take gradient step
            optimizer.step()

            # compute the accuracy
            acc_t = torch.eq(y_pred, y_gold).sum().item() / len(y_gold)

            running_acc += (acc_t - running_acc) / (batch_index + 1)

            # uncomment to see loss and accuracy measures for every minibatch
            # print("loss: {0}, running_loss: {1}, acc: {0}, running_acc: {1}".format(loss_t, running_loss,
            #                                                                       acc_t, running_acc))

        # add loss and accuracy information to the train state
        train_state['train_loss'].append(running_loss)
        train_state['train_acc'].append(running_acc)

        # print("Training loss: {0}, training acc: {1}".format(running_loss, running_acc))

        # Iterate over validation set--put it in a dataloader
        acoustic_batches, embedding_batches, speaker_batches, y_batches, length_batches = \
            generate_batches(val_data, batch_size, shuffle=True, device=device)

        # reset loss and accuracy to zero
        running_loss = 0.
        running_acc = 0.

        # set classifier to evaluation mode
        classifier.eval()

        # set holders to use for error analysis
        # ys_holder = []
        # preds_holder = []

        # for each batch in the dataloader
        for batch_index, batch_array in enumerate(acoustic_batches):
            # compute the output
            class_pred = classifier(acoustic_input=batch_array, text_input=embedding_batches[batch_index],
                                    speaker_input=speaker_batches[batch_index],
                                    length_input=length_batches[batch_index])

            # if we're using multitask, include the decoder
            if model2 is not None:
                # get output of model 2, if using
                y_pred = model2(class_pred)
            else:
                y_pred = class_pred

            # get the gold labels
            y_gold = y_batches[batch_index].float()

            # add ys to holder for error analysis
            # preds_holder.extend(y_pred)
            # ys_holder.extend(y_gold)

            y_gold = torch.tensor([item.index(max(item)) for item in y_gold.tolist()])

            loss = loss_func(y_pred, y_gold)
            running_loss += (loss.item() - running_loss) / (batch_index + 1)

            # compute the loss
            if len(list(y_pred.size())) > 1:
                y_pred = torch.tensor([item.index(max(item)) for item in y_pred.tolist()])
            else:
                y_pred = torch.round(y_pred)

            # compute the accuracy
            acc_t = torch.eq(y_pred, y_gold).sum().item() / len(y_gold)
            running_acc += (acc_t - running_acc) / (batch_index + 1)

            # uncomment to see loss and accuracy for each minibatch
            # print("val_loss: {0}, running_val_loss: {1}, val_acc: {0}, running_val_acc: {1}".format(loss_t, running_loss,
            #                                                                       acc_t, running_acc))

        # print("Overall val loss: {0}, overall val acc: {1}".format(running_loss, running_acc))

        # add loss and accuracy to train state
        train_state['val_loss'].append(running_loss)
        train_state['val_acc'].append(running_acc)

        # update the train state now that our epoch is complete
        train_state = update_train_state(model=classifier,
                                         train_state=train_state)

        # update scheduler if there is one
        if scheduler is not None:
            scheduler.step(train_state['val_loss'][-1])

        # if it's time to stop, end the training process
        if train_state['stop_early']:
            break


def test(model, state_loadpath, test_data, loss_func):
    """
    Test the best model on the held-out data fold
    :param model: the model (class)
    :param state_loadpath: the path to the saved .pth file for trained state dict
    :param test_data: the held-out data fold
    :param loss_func: the loss function
    :return: loss, accuracy on test set
    """
    # load the state dict into model and set to evaluate
    model.load_state_dict(torch.load(state_loadpath))
    model.eval()

    # split test data
    test_split = DataLoader(test_data)
    acoustic = [item[0] for item in test_split]
    embedding = [item[1] for item in test_split]
    speaker = [item[2] for item in test_split]
    gold_labels = [item[3] for item in test_split]

    # initialize loss and accuracy
    running_loss = 0.
    running_acc = 0.

    for index, acoustic_batch in enumerate(acoustic):
        y_pred = model(acoustic_input=acoustic_batch, text_input=embedding[index], speaker_input=speaker[index])
        y_gold = gold_labels[index].float()

        loss = loss_func(y_pred, y_gold)
        running_loss += (loss.item() - running_loss) / (index + 1)

        y_pred = torch.round(y_pred)

        acc_t = torch.eq(y_pred, y_gold).sum().item() / len(y_gold)
        running_acc += (acc_t - running_acc) / (index + 1)

    return running_loss, running_acc