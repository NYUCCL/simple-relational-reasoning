import os
import torch
from torch import nn
import torchvision
import torchvision.models as models


CHECKPOINT_FOLDER = r'/home/gd1279/scratch/SAYcam-models'

RESNET = 'resnet'
VGG = 'vgg'
MOBILENET = 'mobilenet'
RESNEXT = 'resnext'
MODELS = (RESNET, VGG, MOBILENET, RESNEXT)

SAYCAM_models = (MOBILENET, RESNEXT)
SAYCAM_n_out = {'S': 2765, 'SAY':6269}


def build_model(name, device, pretrained=True, saycam=None):
    name = name.lower()
    assert(name in MODELS)
    model = None
    
    if saycam:
        if saycam is True:
            saycam = 'SAY'
        saycam = saycam.upper()
        
        assert(saycam in SAYCAM_n_out)
        assert(name in SAYCAM_models)
        
        checkpoint = torch.load(os.path.join(CHECKPOINT_FOLDER, f'TC-{saycam}-{name}.tar'))
        
        if name == MOBILENET:
            model = models.mobilenet_v2(pretrained=False)
            model = nn.DataParallel(model)
            model = model.to(device)
            model.module.classifier = nn.Linear(1280, SAYCAM_n_out[saycam])
            model.load_state_dict(checkpoint['model_state_dict'])
            model.module.classifier = nn.Sequential()
        
        elif name == RESNEXT:
            model = models.resnext50_32x4d(pretrained=False)
            model = nn.DataParallel(model)
            model = model.to(device)
            model.module.fc = nn.Linear(2048, SAYCAM_n_out[saycam])
            model.load_state_dict(checkpoint['model_state_dict'])
            model.module.fc = nn.Sequential()
    
    else:
        if name == RESNET:
            model = models.resnet18(pretrained=pretrained)
            model.fc_backup = model.fc
            model.fc = nn.Sequential()
            model = model.to(device)

        elif name == VGG:
            model = models.vgg16(pretrained=pretrained)
            model.fc_backup = model.classifier[6]
            model.classifier[6] = nn.Sequential()
            model = model.to(device)

        elif name == MOBILENET:
            model = models.mobilenet_v2(pretrained=pretrained)
            model.fc_backup = model.classifier[1]
            model.classifier[1] = nn.Sequential()
            model = model.to(device)

        elif name == RESNEXT:
            model = models.resnext50_32x4d(pretrained=pretrained)
            model.fc_backup = model.fc
            model.fc = nn.Sequential()
            model = model.to(device)
        
    if model is None:
        raise ValueError(f'Failed to build model for name={name}, pretrained={pretrained}, saycam={saycam}')
        
    return model
    