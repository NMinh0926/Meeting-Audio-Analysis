"""ECAPA-TDNN voice gender classifier.

Architecture from https://github.com/JaesungHuh/voice-gender-classifier (MIT License, Copyright (c) 2024
Jaesung Huh), itself based on https://github.com/TaoRuijie/ECAPA-TDNN. Weights:
https://huggingface.co/JaesungHuh/voice-gender-classifier (ECAPA-TDNN fine-tuned on VoxCeleb2).
Layer names and shapes must stay as they are to load the published weights; only the file and audio
loading helpers were left out.
"""
import math

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchaudio
from huggingface_hub import PyTorchModelHubMixin

MALE, FEMALE = 0, 1  # output indices


class SEModule(nn.Module):
    def __init__(self, channels: int, bottleneck: int = 128) -> None:
        super().__init__()
        self.se = nn.Sequential(
            nn.AdaptiveAvgPool1d(1),
            nn.Conv1d(channels, bottleneck, kernel_size=1, padding=0),
            nn.ReLU(),
            nn.Conv1d(bottleneck, channels, kernel_size=1, padding=0),
            nn.Sigmoid(),
        )

    def forward(self, input: torch.Tensor) -> torch.Tensor:
        return input * self.se(input)


class Bottle2neck(nn.Module):
    def __init__(self, inplanes: int, planes: int, kernel_size: int, dilation: int, scale: int = 8) -> None:
        super().__init__()
        width = int(math.floor(planes / scale))
        self.conv1 = nn.Conv1d(inplanes, width * scale, kernel_size=1)
        self.bn1 = nn.BatchNorm1d(width * scale)
        self.nums = scale - 1
        num_pad = math.floor(kernel_size / 2) * dilation
        self.convs = nn.ModuleList(
            nn.Conv1d(width, width, kernel_size=kernel_size, dilation=dilation, padding=num_pad)
            for _ in range(self.nums)
        )
        self.bns = nn.ModuleList(nn.BatchNorm1d(width) for _ in range(self.nums))
        self.conv3 = nn.Conv1d(width * scale, planes, kernel_size=1)
        self.bn3 = nn.BatchNorm1d(planes)
        self.relu = nn.ReLU()
        self.width = width
        self.se = SEModule(planes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        out = self.bn1(self.relu(self.conv1(x)))

        spx = torch.split(out, self.width, 1)
        for i in range(self.nums):
            sp = spx[i] if i == 0 else sp + spx[i]
            sp = self.bns[i](self.relu(self.convs[i](sp)))
            out = sp if i == 0 else torch.cat((out, sp), 1)
        out = torch.cat((out, spx[self.nums]), 1)

        out = self.bn3(self.relu(self.conv3(out)))
        return self.se(out) + residual


class ECAPAGender(nn.Module, PyTorchModelHubMixin):
    """Two logits, male then female, for a batch of 16 kHz mono waveforms in [-1, 1]."""

    def __init__(self, C: int = 1024) -> None:
        super().__init__()
        self.C = C
        self.conv1 = nn.Conv1d(80, C, kernel_size=5, stride=1, padding=2)
        self.relu = nn.ReLU()
        self.bn1 = nn.BatchNorm1d(C)
        self.layer1 = Bottle2neck(C, C, kernel_size=3, dilation=2, scale=8)
        self.layer2 = Bottle2neck(C, C, kernel_size=3, dilation=3, scale=8)
        self.layer3 = Bottle2neck(C, C, kernel_size=3, dilation=4, scale=8)
        self.layer4 = nn.Conv1d(3 * C, 1536, kernel_size=1)
        self.attention = nn.Sequential(
            nn.Conv1d(4608, 256, kernel_size=1),
            nn.ReLU(),
            nn.BatchNorm1d(256),
            nn.Tanh(),
            nn.Conv1d(256, 1536, kernel_size=1),
            nn.Softmax(dim=2),
        )
        self.bn5 = nn.BatchNorm1d(3072)
        self.fc6 = nn.Linear(3072, 192)
        self.bn6 = nn.BatchNorm1d(192)
        self.fc7 = nn.Linear(192, 2)

    def logtorchfbank(self, x: torch.Tensor) -> torch.Tensor:
        # Pre-emphasis
        flipped_filter = torch.tensor([-0.97, 1.0], device=x.device).unsqueeze(0).unsqueeze(0)
        x = F.pad(x.unsqueeze(1), (1, 0), "reflect")
        x = F.conv1d(x, flipped_filter).squeeze(1)
        # Log mel spectrogram, mean-normalised over time
        mel = torchaudio.transforms.MelSpectrogram(
            sample_rate=16000, n_fft=512, win_length=400, hop_length=160,
            f_min=20, f_max=7600, window_fn=torch.hamming_window, n_mels=80,
        ).to(x.device)
        x = (mel(x) + 1e-6).log()
        return x - torch.mean(x, dim=-1, keepdim=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.bn1(self.relu(self.conv1(self.logtorchfbank(x))))

        x1 = self.layer1(x)
        x2 = self.layer2(x + x1)
        x3 = self.layer3(x + x1 + x2)
        x = self.relu(self.layer4(torch.cat((x1, x2, x3), dim=1)))

        t = x.size()[-1]
        global_x = torch.cat(
            (x, torch.mean(x, dim=2, keepdim=True).repeat(1, 1, t),
             torch.sqrt(torch.var(x, dim=2, keepdim=True).clamp(min=1e-4)).repeat(1, 1, t)),
            dim=1,
        )
        w = self.attention(global_x)
        mu = torch.sum(x * w, dim=2)
        sg = torch.sqrt((torch.sum((x ** 2) * w, dim=2) - mu ** 2).clamp(min=1e-4))

        x = self.bn6(self.fc6(self.bn5(torch.cat((mu, sg), 1))))
        return self.fc7(self.relu(x))
