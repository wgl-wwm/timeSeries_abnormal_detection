import math
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from block import ConvBlock, GRUBlock, ResBlock, SelfAttention
import numpy as np
import sklearn.metrics

class MyNet(nn.Module):
    """Some Information about MyNet"""
    def __init__(self,time_length=100):
        super(MyNet, self).__init__()
        self.time_length = time_length

        self.net = nn.Sequential(
            # GRUBlock(input_size = 1, hidden_size = 32),
            # ConvBlock(in_channels=1, out_channels=32,mid_channels=32,time_length=self.time_length),
            # SelfAttention(32),
            ResBlock(input_channels=1, num_channels=32,time_length=self.time_length),
            ResBlock(input_channels=32, num_channels=32,time_length=self.time_length),
            ResBlock(input_channels=32, num_channels=32,time_length=self.time_length),

            nn.Flatten(),
            nn.Linear(self.time_length*32,512),
            nn.ReLU(inplace=True),
            nn.Linear(512,32),
#             nn.ReLU(inplace=True),
#             nn.Linear(256,32),
            nn.ReLU(inplace=True),
            nn.Linear(32,4)
        )

        # self.act = nn.Sigmoid()
        
        for layer in self.net:
            if isinstance(layer, nn.Linear):
                nn.init.xavier_normal_(layer.weight.data)
        
    def forward(self, sup_inp, que_inp):
        sup_inp = sup_inp.permute(0, 2, 1)
        que_inp = que_inp.permute(0, 2, 1)
#         def lcm(a, b):
#             return abs(a * b) // math.gcd(a, b)
        # sup_inp que_inp  [batch_size, in_channels, time_length]
        bz_sup = sup_inp.shape[0]
        bz_que = que_inp.shape[0]

        y_sup = self.net(sup_inp) #  [bz_sup,5]
        y_que = self.net(que_inp) #  [bz_que,5]

        mx_len = bz_sup * bz_que

        y_sup = y_sup.repeat_interleave(int(mx_len / bz_sup),0)
        y_que = y_que.repeat(int(mx_len / bz_que),1)

        y_p = F.pairwise_distance(y_sup,y_que,p=2)
        # mean = torch.mean(y_dist)
        # std = torch.std(y_dist)
        # y_dist = (y_dist - mean) / (std + 1e-10)
        # y_p = self.act(y_dist)

        return y_p


class Loss(torch.nn.Module):
    """
    loss function.
    """

    def __init__(self, margin=2, gamma = 1, eps = 1e-10, training = True):
        super(Loss, self).__init__()
        self.margin = margin
        self.gamma = gamma
        self.eps = eps
        self.training = training

    def forward(self, y_p, label, training=None):
        if training is not None:
            self.training = training
        # y_p [lcm(bz_sup, bz_que)] from 0 ~ 1 靠近1表示越不相似
        # label ([bz_sup], [bz_que]) from [0, 1] 1 表示异常 0表示正常
        # print(y_p)
        label_sup = label[0]
        label_que = label[1]
        mx_len = y_p.shape[0]
        # print(label_sup.repeat_interleave(int(mx_len / label_sup.shape[0])))
        # print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        # print(label_que.repeat(int(mx_len / label_que.shape[0])))
        # print("++++++++++++++++++++++++++++++")
        con_label = label_sup.repeat_interleave(int(mx_len / label_sup.shape[0])) - label_que.repeat(int(mx_len / label_que.shape[0]))
        # print(con_label)
        # print("???????????????????????????")
        # con_label = torch.abs(con_label) # 1 表示不相似， 0 表示相似
        con_label = torch.where(con_label == 0, 0, 1)
        # loss = - (1 - con_label) * torch.log(1 - y_p + self.eps) - con_label * torch.log(y_p + self.eps)
        # loss = con_label * torch.clamp(self.margin - y_p, min=0.0) + (1 - con_label) * y_p
        loss = torch.pow(torch.log(self.margin) - torch.log(y_p)) * con_label * torch.clamp(self.margin - y_p, min=0.0) + (1 - con_label) * y_p
        loss = torch.mean(loss)
        pred = torch.where(y_p > self.margin,0.0,1.0)
        # print(pred)
        # print('---------------------------------------------')
        # print(con_label)
        pred = torch.mean(torch.abs(pred - con_label))
        if self.training:
            return loss, pred, None, None
        


        # 计算混淆矩阵 label_sup label_que y_p
        que_predict = np.zeros((20,4))
        for i, dist in enumerate(y_p):
            x = int(i / 20)
            y = i % 20

            que_predict[y][label_sup[x]] += dist
        # print(que_predict)
        # print("??????????")
        que_predict[:, 0] /= 8
        que_predict[:, 1:] /= 4

        que_pred = que_predict.argmin(1)
        # print(label_que)
        # print("----------")
        # print(que_pred)
        return loss, pred, label_que, que_pred
    
