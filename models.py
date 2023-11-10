from abc import ABC

import torch.nn as nn
import torch
from torch import Tensor
from transformers import Dinov2PreTrainedModel, Dinov2Model


def calc_shape(in_shape, padding, dilation, k_size, stride):
    h = (in_shape[0] + 2 * padding - dilation * (k_size - 1) - 1) / stride + 1
    w = (in_shape[1] + 2 * padding - dilation * (k_size - 1) - 1) / stride + 1
    return (int(h), int(w))


class CNNModel(nn.Module):
    def __init__(self, n_filters, input_shape):
        """ """
        super(CNNModel, self).__init__()

        # In one channel, out n_filters
        self.conv1 = nn.Conv2d(
            in_channels=1,
            out_channels=n_filters,
            kernel_size=3,
            stride=1,
            padding=0,
        )

        self.relu = nn.ReLU()
        self.maxpool = nn.MaxPool2d(kernel_size=2, stride=1)

        # Calculate next layer input size
        conv_out = calc_shape([input_shape[0], input_shape[1]], 0, 1, 3, 1)
        maxp_out = calc_shape([conv_out[0], conv_out[1]], 0, 1, 2, 1)

        self.fc1 = nn.Linear(maxp_out[0] * maxp_out[1] * n_filters, 256)
        self.fc2 = nn.Linear(256, 2)

        # Not needed
        # self.softmax = nn.Softmax(dim=1)

    def forward(self, x):
        x = self.conv1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        # Flatten
        x = torch.flatten(x, 1)

        x = self.fc1(x)

        x = self.fc2(x)

        # Not needed
        # x = self.softmax(x)

        return x


class CNN_LSTM_Model(nn.Module):
    """CNN with LSTM

    Input shape of LSTM layers: [batch_size, sequence_len, input_size]
    All intermediate hidden states are passed to linear layers.
    Input size of dense layers: [num_layers * hidden_size]

    """

    def __init__(self, n_filters, input_shape, hidden_size, num_layers):
        super(CNN_LSTM_Model, self).__init__()

        self.n_filters = n_filters
        self.hidden_size = hidden_size

        self.conv1 = nn.Conv2d(
            in_channels=1,
            out_channels=n_filters,
            kernel_size=3,
            stride=1,
            padding=0,
        )
        self.relu = nn.ReLU()
        self.maxpool = nn.MaxPool2d(kernel_size=2, stride=1)

        conv_out = calc_shape([input_shape[0], input_shape[1]], 0, 1, 3, 1)
        self.maxp_out = calc_shape([conv_out[0], conv_out[1]], 0, 1, 2, 1)

        self.lstm1 = nn.LSTM(
            input_size= n_filters * self.maxp_out[0],
            hidden_size=hidden_size,
            num_layers=self.maxp_out[1],
        )
        self.fc1 = nn.Linear(self.maxp_out[1]* hidden_size, 256)
        self.fc2 = nn.Linear(256, 2)
        self.softmax = nn.Softmax(dim=1)

    def forward(self, x):
        x = self.conv1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        # Reshape for LSTM -> [batch, sequence_len, data]
        x = x.view(x.size(0), x.size(3), -1)

        x, _ = self.lstm1(x)

        # Flatten the output for the Linear layer
        x = x.view(x.size(0), -1)

        x = self.fc1(x)
        x = self.fc2(x)
        x = self.softmax(x)

        return x


class DenseClassifier(nn.Module):
    def __init__(self):
        super(DenseClassifier, self).__init__()
        self.Dense_A = nn.Linear(28 * 768, 14 * 768)
        self.Dense_B = nn.Linear(14 * 768, 7 * 768)
        self.Output_Dense = nn.Linear(7 * 768, 2)
        self.relu = nn.ReLU()

    def forward(self, patch_embeddings: Tensor):
        x = self.relu(
            self.Dense_A(
                patch_embeddings.reshape(patch_embeddings.shape[0], -1)
            )
        )
        x = self.relu(self.Dense_B(x))
        x = self.Output_Dense(x)
        return x


class DinoV2TransformerBasedModel(Dinov2PreTrainedModel, ABC):
    def __init__(self, dinoV2_config):
        super().__init__(dinoV2_config)
        self.dinoV2 = Dinov2Model(dinoV2_config)
        self.classifier = DenseClassifier()

    def forward(self, spectrograms: Tensor):
        outputs = self.dinoV2(spectrograms, output_attentions=False)
        patch_embeddings = outputs.last_hidden_state[:, 1:, :]

        logits = self.classifier(patch_embeddings)
        return logits
