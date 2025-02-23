# -*- coding: utf-8 -*-
"""ProgRock Diffusion

Command line version of Disco Diffusion (v5 Alpha)

Original file is located at
    https://colab.research.google.com/drive/1QGCyDlYneIvv1zFXngfOCCoSUKC6j1ZP

Original notebook by Katherine Crowson (https://github.com/crowsonkb, https://twitter.com/RiversHaveWings). It uses either OpenAI's 256x256 unconditional ImageNet or Katherine Crowson's fine-tuned 512x512 diffusion model (https://github.com/openai/guided-diffusion), together with CLIP (https://github.com/openai/CLIP) to connect text prompts with images.

Modified by Daniel Russell (https://github.com/russelldc, https://twitter.com/danielrussruss) to include (hopefully) optimal params for quick generations in 15-100 timesteps rather than 1000, as well as more robust augmentations.

Further improvements from Dango233 and nsheppard helped improve the quality of diffusion in general, and especially so for shorter runs like this notebook aims to achieve.

Vark added code to load in multiple Clip models at once, which all prompts are evaluated against, which may greatly improve accuracy.

The latest zoom, pan, rotation, and keyframes features were taken from Chigozie Nri's VQGAN Zoom Notebook (https://github.com/chigozienri, https://twitter.com/chigozienri)

Advanced DangoCutn Cutout method is also from Dango223.

Somnai (https://twitter.com/Somnai_dreams) added Diffusion Animation techniques, QoL improvements and various implementations of tech and techniques, mostly listed in the changelog below.
--
Stripped down for basic Python use by Jason Hough
--
"""

# @title Licensed under the MIT License

# Copyright (c) 2021 Katherine Crowson

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

#@title <- View Changelog

import os
from os import path
import shutil
root_path = os.getcwd()


#Simple create paths taken with modifications from Datamosh's Batch VQGAN+CLIP notebook
def createPath(filepath):
    if path.exists(filepath) == False:
        os.makedirs(filepath)
        print(f'Made {filepath}')
    else:
        pass


initDirPath = f'{root_path}/init_images'
createPath(initDirPath)
outDirPath = f'{root_path}/images_out'
createPath(outDirPath)

model_path = f'{root_path}/models'
createPath(model_path)

model_256_downloaded = False
model_512_downloaded = False
model_secondary_downloaded = False

python_example = "python3"

import sys
if sys.platform == 'win32':
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    python_example = "python"

#Uncomment the below line if you're getting an error about OMP: Error #15.
#os.environ['KMP_DUPLICATE_LIB_OK']='TRUE'

from dataclasses import dataclass
from functools import partial
import cv2
import pandas as pd
import re
import gc
import io
import math
import timm
from IPython import display
import lpips
from PIL import Image, ImageOps, ImageStat, ImageEnhance
from PIL.PngImagePlugin import PngInfo
import requests
from glob import glob
import json5 as json
from types import SimpleNamespace
import torch
from torch import nn
from torch.nn import functional as F
import torchvision.transforms as T
import torchvision.transforms.functional as TF
from tqdm import tqdm
sys.path.append(f'{root_path}/ResizeRight')
sys.path.append(f'{root_path}/CLIP')
sys.path.append(f'{root_path}/guided-diffusion')
#sys.path.append(f'{root_path}/SLIP')
import clip
from resize_right import resize
#from models import SLIP_VITB16, SLIP, SLIP_VITL16
from guided_diffusion.script_util import create_model_and_diffusion, model_and_diffusion_defaults
from datetime import datetime
import numpy as np
import numexpr
import matplotlib.pyplot as plt
import random
from ipywidgets import Output
import hashlib
import urllib.request
from os.path import exists


# Setting default values for everything, which can then be overridden by settings files.
batch_name = "Default"
text_prompts = "No prompt in the file, by Sir Digby Chicken Caeser"
image_prompts = {}
clip_guidance_scale = "auto"
tv_scale = 0
range_scale = 150
sat_scale = 0
n_batches = 1
display_rate = 20
cutn_batches = 4
max_frames = 10000
interp_spline = "Linear"
init_image = None
init_scale = 1000
skip_steps = 0
frames_scale = 1500
frames_skip_steps = "60%"
perlin_init = False
perlin_mode = "mixed"
skip_augs = False
randomize_class = True
clip_denoised = False
clamp_grad = True
clamp_max = "auto"
set_seed = "random_seed"
fuzzy_prompt = False
rand_mag = 0.05
eta = "auto"
width_height = [832, 512]
width_height_scale = 1
diffusion_model = "512x512_diffusion_uncond_finetune_008100"
use_secondary_model = True
steps = 250
sampling_mode = "ddim"
diffusion_steps = 1000
ViTB32 = True
ViTB16 = True
ViTL14 = False
ViTL14_336 = False
RN101 = False
RN50 = True
RN50x4 = False
RN50x16 = False
RN50x64 = False
#SLIPB16 = False
#SLIPL16 = False
cut_overview = "[12]*400+[4]*600"
cut_innercut = "[4]*400+[12]*600"
cut_ic_pow = 1
cut_ic_pow_final = "None"
cut_icgray_p = "[0.2]*400+[0]*600"
key_frames = True
angle = "0:(0)"
zoom = "0: (1), 10: (1.05)"
translation_x = "0: (0)"
translation_y = "0: (0)"
video_init_path = "/content/training.mp4"
extract_nth_frame = 2
intermediate_saves = 0
add_metadata = True
stop_early = 0
fix_brightness_contrast = True
adjustment_interval = 10
high_contrast_threshold = 80
high_contrast_adjust_amount = 0.85
high_contrast_start = 20
high_contrast_adjust = True
low_contrast_threshold = 20
low_contrast_adjust_amount = 2
low_contrast_start = 20
low_contrast_adjust = True
high_brightness_threshold = 180
high_brightness_adjust_amount = 0.85
high_brightness_start = 0
high_brightness_adjust = True
low_brightness_threshold = 40
low_brightness_adjust_amount = 1.15
low_brightness_start = 0
low_brightness_adjust = True
sharpen_preset = 'Off'  #@param ['Off', 'Faster', 'Fast', 'Slow', 'Very Slow']
keep_unsharp = False  #@param{type: 'boolean'}
animation_mode = "None" # "Video Input", "2D"
gobig_orientation = "vertical"
gobig_scale = 2

# Command Line parse
import argparse
example_text = f'''Usage examples:

To simply use the 'Default' output directory and get settings from settings.json:
 {python_example} prd.py

To use your own settings.json (note that putting it in quotes can help parse errors):
 {python_example} prd.py -s "some_directory/mysettings.json"

Note that multiple settings files are allowed. They're parsed in order. The values present are applied over any previous value:
 {python_example} prd.py -s "some_directory/mysettings.json" -s "highres.json"

To use the 'Default' output directory and settings, but override the output name and prompt:
 {python_example} prd.py -p "A cool image of the author of this program" -o Coolguy

To use multiple prompts with optional weight values:
 {python_example} prd.py -p "A cool image of the author of this program" -p "Pale Blue Sky:.5"

You can ignore the seed coming from a settings file by adding -i, resulting in a new random seed

To force use of the CPU for image generation, add a -c or --cpu with how many threads to use (warning: VERY slow):
 {python_example} prd.py -c 16

To generate a checkpoint image at 20% steps, for use as an init image in future runs, add -g or --geninit:
 {python_example} prd.py -g

To use a checkpoint image at 20% steps add -u or --useinit:
 {python_example} prd.py -u

To specify which CUDA device to use (advanced) by device ID (default is 0):
 {python_example} prd.py --cuda 1

To HIDE the settings that get added to your output PNG's metadata, use:
 {python_example} prd.py --hidemetadata

To increase resolution 2x by splitting the final image and re-rendering detail in the sections, use:
 {python_example} prd.py --gobig

To increase resolution 2x on an existing output, make sure to supply proper settings, then use:
 {python_example} prd.py --gobig --gobiginit "some_directory/image.png"

If you already upscaled your gobiginit image, you can skip the resizing process. Provide the scaling factor used:
 {python_example} prd.py --gobig --gobiginit "some_directory/image.png" --gobiginit_scaled 2
'''

my_parser = argparse.ArgumentParser(
    prog='ProgRockDiffusion',
    description='Generate images from text prompts.',
    epilog=example_text,
    formatter_class=argparse.RawDescriptionHelpFormatter)

my_parser.add_argument('--gui',
                       action='store_true',
                       required=False,
                       help='Use the PyQt5 GUI')

my_parser.add_argument(
    '-s',
    '--settings',
    action='append',
    required=False,
    default=['settings.json'],
    help=
    'A settings JSON file to use, best to put in quotes. Multiples are allowed and layered in order.'
)

my_parser.add_argument('-o',
                       '--output',
                       action='store',
                       required=False,
                       help='What output directory to use within images_out')

my_parser.add_argument('-p',
                       '--prompt',
                       action='append',
                       required=False,
                       help='Override the prompt')

my_parser.add_argument('-i',
                       '--ignoreseed',
                       action='store_true',
                       required=False,
                       help='Ignores the random seed in the settings file')

my_parser.add_argument(
    '-c',
    '--cpu',
    type=int,
    nargs='?',
    action='store',
    required=False,
    default=False,
    const=0,
    help='Force use of CPU instead of GPU, and how many threads to run')

my_parser.add_argument(
    '-g',
    '--geninit',
    type=int,
    nargs='?',
    action='store',
    required=False,
    default=False,
    const=0.2,
    help=
    'Save a partial image at the specified percent of steps (1 to 99), for use as later init image'
)
my_parser.add_argument('-u',
                       '--useinit',
                       action='store_true',
                       required=False,
                       default=False,
                       help='Use the specified init image')

my_parser.add_argument('--cuda',
                       action='store',
                       required=False,
                       default='0',
                       help='Which GPU to use. Default is 0.')

my_parser.add_argument(
    '--hidemetadata',
    action='store_true',
    required=False,
    help='Will prevent settings from being added to the output PNG file')

my_parser.add_argument(
    '--gobig',
    action='store_true',
    required=False,
    help='After generation, the image is split into sections and re-rendered, to double the size.')

my_parser.add_argument(
    '--gobiginit',
    action='store',
    required=False,
    help=
    'An image to use to kick off GO BIG mode, skipping the initial render.'
)

my_parser.add_argument(
    '--gobiginit_scaled',
    type=int,
    nargs='?',
    action='store',
    required=False,
    default=False,
    const=2,
    help=
    'If you already scaled your gobiginit image, add this option along with the multiplier used (default 2)'
)

cl_args = my_parser.parse_args()


# Simple check to see if a key is present in the settings file
def is_json_key_present(json, key):
    try:
        buf = json[key]
    except KeyError:
        return False
    return True


#A simple way to ensure values are in an accceptable range, and also return a random value if desired
def clampval(minval, val, maxval):
    if val == "random":
        try:
            val = random.randint(minval, maxval)
        except:
            val = random.uniform(minval, maxval)
        return val
    #Auto is handled later, so we just return it back as is
    elif val == "auto":
        return val
    elif val < minval:
        val = minval
        return val
    elif val > maxval:
        val = maxval
        return val
    else:
        return val


# Load the JSON config files
for setting_arg in cl_args.settings:
    try:
        with open(setting_arg, 'r', encoding="utf-8") as json_file:
            print(f'Parsing {setting_arg}')
            settings_file = json.load(json_file)
            # If any of these around in this settings file they'll be applied, overwriting any previous value.
            # Some are passed by clampval first to make sure they are within bounds (or randomized if desired)
            if is_json_key_present(settings_file, 'batch_name'):
                batch_name = (settings_file['batch_name'])
            if is_json_key_present(settings_file, 'text_prompts'):
                text_prompts = (settings_file['text_prompts'])
            if is_json_key_present(settings_file, 'image_prompts'):
                image_prompts = (settings_file['image_prompts'])
            if is_json_key_present(settings_file, 'clip_guidance_scale'):
                clip_guidance_scale = clampval(
                    1500, (settings_file['clip_guidance_scale']), 100000)
            if is_json_key_present(settings_file, 'tv_scale'):
                tv_scale = clampval(0, (settings_file['tv_scale']), 1000)
            if is_json_key_present(settings_file, 'range_scale'):
                range_scale = clampval(0, (settings_file['range_scale']), 1000)
            if is_json_key_present(settings_file, 'sat_scale'):
                sat_scale = clampval(0, (settings_file['sat_scale']), 20000)
            if is_json_key_present(settings_file, 'n_batches'):
                n_batches = (settings_file['n_batches'])
            if is_json_key_present(settings_file, 'display_rate'):
                display_rate = (settings_file['display_rate'])
            if is_json_key_present(settings_file, 'cutn_batches'):
                cutn_batches = (settings_file['cutn_batches'])
            if is_json_key_present(settings_file, 'max_frames'):
                max_frames = (settings_file['max_frames'])
            if is_json_key_present(settings_file, 'interp_spline'):
                interp_spline = (settings_file['interp_spline'])
            if is_json_key_present(settings_file, 'init_image'):
                init_image = (settings_file['init_image'])
            if is_json_key_present(settings_file, 'init_scale'):
                init_scale = (settings_file['init_scale'])
            if is_json_key_present(settings_file, 'skip_steps'):
                skip_steps = (settings_file['skip_steps'])
            if is_json_key_present(settings_file, 'stop_early'):
                stop_early = (settings_file['stop_early'])
            if is_json_key_present(settings_file, 'frames_scale'):
                frames_scale = (settings_file['frames_scale'])
            if is_json_key_present(settings_file, 'frames_skip_steps'):
                frames_skip_steps = (settings_file['frames_skip_steps'])
            if is_json_key_present(settings_file, 'perlin_init'):
                perlin_init = (settings_file['perlin_init'])
            if is_json_key_present(settings_file, 'perlin_mode'):
                perlin_mode = (settings_file['perlin_mode'])
            if is_json_key_present(settings_file, 'skip_augs'):
                skip_augs = (settings_file['skip_augs'])
            if is_json_key_present(settings_file, 'randomize_class'):
                randomize_class = (settings_file['randomize_class'])
            if is_json_key_present(settings_file, 'clip_denoised'):
                clip_denoised = (settings_file['clip_denoised'])
            if is_json_key_present(settings_file, 'clamp_grad'):
                clamp_grad = (settings_file['clamp_grad'])
            if is_json_key_present(settings_file, 'clamp_max'):
                clamp_max = clampval(0.001, (settings_file['clamp_max']), 0.1)
            if is_json_key_present(settings_file, 'set_seed'):
                set_seed = (settings_file['set_seed'])
            if is_json_key_present(settings_file, 'fuzzy_prompt'):
                fuzzy_prompt = (settings_file['fuzzy_prompt'])
            if is_json_key_present(settings_file, 'rand_mag'):
                rand_mag = clampval(0.0, (settings_file['rand_mag']), 0.999)
            if is_json_key_present(settings_file, 'eta'):
                eta = clampval(0.0, (settings_file['eta']), 0.999)
            if is_json_key_present(settings_file, 'width'):
                width_height = [(settings_file['width']),
                                (settings_file['height'])]
            if is_json_key_present(settings_file, 'width_height_scale'):
                width_height_scale = (settings_file['width_height_scale'])
            if is_json_key_present(settings_file, 'diffusion_model'):
                diffusion_model = (settings_file['diffusion_model'])
            if is_json_key_present(settings_file, 'use_secondary_model'):
                use_secondary_model = (settings_file['use_secondary_model'])
            if is_json_key_present(settings_file, 'steps'):
                steps = (settings_file['steps'])
            if is_json_key_present(settings_file, 'sampling_mode'):
                sampling_mode = (settings_file['sampling_mode'])
            if is_json_key_present(settings_file, 'diffusion_steps'):
                diffusion_steps = (settings_file['diffusion_steps'])
            if is_json_key_present(settings_file, 'ViTB32'):
                ViTB32 = (settings_file['ViTB32'])
            if is_json_key_present(settings_file, 'ViTB16'):
                ViTB16 = (settings_file['ViTB16'])
            if is_json_key_present(settings_file, 'ViTL14'):
                ViTL14 = (settings_file['ViTL14'])
            if is_json_key_present(settings_file, 'ViTL14_336'):
                ViTL14_336 = (settings_file['ViTL14_336'])
            if is_json_key_present(settings_file, 'RN101'):
                RN101 = (settings_file['RN101'])
            if is_json_key_present(settings_file, 'RN50'):
                RN50 = (settings_file['RN50'])
            if is_json_key_present(settings_file, 'RN50x4'):
                RN50x4 = (settings_file['RN50x4'])
            if is_json_key_present(settings_file, 'RN50x16'):
                RN50x16 = (settings_file['RN50x16'])
            if is_json_key_present(settings_file, 'RN50x64'):
                RN50x64 = (settings_file['RN50x64'])
#            if is_json_key_present(settings_file, 'SLIPB16'):
#                SLIPB16 = (settings_file['SLIPB16'])
#            if is_json_key_present(settings_file, 'SLIPL16'):
#                SLIPL16 = (settings_file['SLIPL16'])
            if is_json_key_present(settings_file, 'cut_overview'):
                cut_overview = (settings_file['cut_overview'])
            if is_json_key_present(settings_file, 'cut_innercut'):
                cut_innercut = (settings_file['cut_innercut'])
            if is_json_key_present(settings_file, 'cut_ic_pow'):
                cut_ic_pow = clampval(0.5, (settings_file['cut_ic_pow']), 100)
            if is_json_key_present(settings_file, 'cut_ic_pow_final'):
                cut_ic_pow_final = (settings_file['cut_ic_pow_final'])
                if type(cut_ic_pow_final) is not str:
                    cut_ic_pow_final = clampval(0.5, (settings_file['cut_ic_pow_final']), 100)
            if is_json_key_present(settings_file, 'cut_icgray_p'):
                cut_icgray_p = (settings_file['cut_icgray_p'])
            if is_json_key_present(settings_file, 'key_frames'):
                key_frames = (settings_file['key_frames'])
            if is_json_key_present(settings_file, 'angle'):
                angle = (settings_file['angle'])
            if is_json_key_present(settings_file, 'zoom'):
                zoom = (settings_file['zoom'])
            if is_json_key_present(settings_file, 'translation_x'):
                translation_x = (settings_file['translation_x'])
            if is_json_key_present(settings_file, 'translation_y'):
                translation_y = (settings_file['translation_y'])
            if is_json_key_present(settings_file, 'video_init_path'):
                video_init_path = (settings_file['video_init_path'])
            if is_json_key_present(settings_file, 'extract_nth_frame'):
                extract_nth_frame = (settings_file['extract_nth_frame'])
            if is_json_key_present(settings_file, 'intermediate_saves'):
                intermediate_saves = (settings_file['intermediate_saves'])
            if is_json_key_present(settings_file, 'fix_brightness_contrast'):
                fix_brightness_contrast = (settings_file['fix_brightness_contrast'])
            if is_json_key_present(settings_file, 'adjustment_interval'):
                adjustment_interval = (settings_file['adjustment_interval'])
            if is_json_key_present(settings_file, 'high_contrast_threshold'):
                high_contrast_threshold = (
                    settings_file['high_contrast_threshold'])
            if is_json_key_present(settings_file,
                                   'high_contrast_adjust_amount'):
                high_contrast_adjust_amount = (
                    settings_file['high_contrast_adjust_amount'])
            if is_json_key_present(settings_file, 'high_contrast_start'):
                high_contrast_start = (settings_file['high_contrast_start'])
            if is_json_key_present(settings_file, 'high_contrast_adjust'):
                high_contrast_adjust = (settings_file['high_contrast_adjust'])
            if is_json_key_present(settings_file, 'low_contrast_threshold'):
                low_contrast_threshold = (
                    settings_file['low_contrast_threshold'])
            if is_json_key_present(settings_file,
                                   'low_contrast_adjust_amount'):
                low_contrast_adjust_amount = (
                    settings_file['low_contrast_adjust_amount'])
            if is_json_key_present(settings_file, 'low_contrast_start'):
                low_contrast_start = (settings_file['low_contrast_start'])
            if is_json_key_present(settings_file, 'low_contrast_adjust'):
                low_contrast_adjust = (settings_file['low_contrast_adjust'])
            if is_json_key_present(settings_file, 'high_brightness_threshold'):
                high_brightness_threshold = (
                    settings_file['high_brightness_threshold'])
            if is_json_key_present(settings_file,
                                   'high_brightness_adjust_amount'):
                high_brightness_adjust_amount = (
                    settings_file['high_brightness_adjust_amount'])
            if is_json_key_present(settings_file, 'high_brightness_start'):
                high_brightness_start = (
                    settings_file['high_brightness_start'])
            if is_json_key_present(settings_file, 'high_brightness_adjust'):
                high_brightness_adjust = (
                    settings_file['high_brightness_adjust'])
            if is_json_key_present(settings_file, 'low_brightness_threshold'):
                low_brightness_threshold = (
                    settings_file['low_brightness_threshold'])
            if is_json_key_present(settings_file,
                                   'low_brightness_adjust_amount'):
                low_brightness_adjust_amount = (
                    settings_file['low_brightness_adjust_amount'])
            if is_json_key_present(settings_file, 'low_brightness_start'):
                low_brightness_start = (settings_file['low_brightness_start'])
            if is_json_key_present(settings_file, 'low_brightness_adjust'):
                low_brightness_adjust = (
                    settings_file['low_brightness_adjust'])
            if is_json_key_present(settings_file, 'sharpen_preset'):
                sharpen_preset = (settings_file['sharpen_preset'])
            if is_json_key_present(settings_file, 'keep_unsharp'):
                keep_unsharp = (settings_file['keep_unsharp'])
            if is_json_key_present(settings_file, 'animation_mode'):
                animation_mode = (settings_file['animation_mode'])
            if is_json_key_present(settings_file, 'gobig_orientation'):
                gobig_orientation = (settings_file['gobig_orientation'])
            if is_json_key_present(settings_file, 'gobig_scale'):
                gobig_scale = int(settings_file['gobig_scale'])

    except Exception as e:
        print('Failed to open or parse ' + setting_arg +
              ' - Check formatting.')
        print(e)
        quit()

width_height = [
    width_height[0] * width_height_scale, width_height[1] * width_height_scale
]

#Now override some depending on command line and maybe a special case
if cl_args.output:
    batch_name = cl_args.output
    print(f'Setting Output dir to {batch_name}')

if cl_args.ignoreseed:
    set_seed = 'random_seed'
    print(f'Using a random seed instead of the one provided by the JSON file.')

if cl_args.hidemetadata:
    add_metadata = False
    print(
        f'Hide metadata flag is ON, settings will not be stored in the PNG output.'
    )

gui = False
if cl_args.gui:
    gui = True
    import prdgui

letsgobig = False
gobig_horizontal = False
gobig_vertical = False
if cl_args.gobig:
    letsgobig = True
    if gobig_orientation == "horizontal": # default is vertical, if the settings file says otherwise, change it
        gobig_horizontal = True
    else:
        gobig_vertical = True
    n_batches = 1
    print('Going BIG! N-batches automatically set to 1, as only 1 output is supported.')
    if cl_args.gobiginit:
        init_image = cl_args.gobiginit
        print(f'Using {init_image} to kickstart GO BIG. Initial render will be skipped.')
        # check to make sure it is a multiple of 64, otherwise resize it and let the user know.
        temp_image = Image.open(init_image)
        s_width, s_height = temp_image.size
        reside_x = (s_width // 64) * 64
        reside_y = (s_height// 64) * 64
        if reside_x != s_width or reside_y != s_height:
            print('ERROR: Your go big init resolution was NOT a multiple of 64.')
            print('ERROR: Please resize your image.')
            raise Exception("Exiting due to improperly sized go big init.")
        side_x, side_y = temp_image.size
        width_height[0] = side_x
        width_height[1] = side_y
        temp_image.close
    else:
        cl_args.gobiginit = None
    if cl_args.gobiginit_scaled != False:
        gobig_scale = cl_args.gobiginit_scaled

if cl_args.geninit:
    geninit = True
    if cl_args.geninit > 0 and cl_args.geninit <= 100:
        geninitamount = float(cl_args.geninit /
                              100)  # turn it into a float percent
        print(
            f'GenInit mode enabled. A checkpoint image will be saved at {cl_args.geninit}% of steps.'
        )
    else:
        geninitamount = 0.2
        print(
            f'GenInit mode enabled. Provided number was out of bounds, so using {geninitamount} of steps instead.'
        )
else:
    geninit = False

if cl_args.useinit:
    if skip_steps == 0:
        skip_steps = (
            int(steps * 0.33)
        )  # don't change skip_steps if the settings file specified one
    if path.exists(f'{cl_args.useinit}'):
        useinit = True
        init_image = cl_args.useinit
        print(
            f'UseInit mode is using {cl_args.useinit} and starting at {skip_steps}.'
        )
    else:
        init_image = 'geninit.png'
        if path.exists(init_image):
            print(
                f'UseInit mode is using {init_image} and starting at {skip_steps}.'
            )
            useinit = True
        else:
            print('No init image found. Uneinit mode canceled.')
            useinit = False
else:
    useinit = False

#Automatic Eta based on steps
if eta == 'auto':
    maxetasteps = 315
    minetasteps = 50
    maxeta = 1.0
    mineta = 0.0
    if steps > maxetasteps: eta = maxeta
    elif steps < minetasteps: eta = mineta
    else:
        stepsrange = (maxetasteps - minetasteps)
        newrange = (maxeta - mineta)
        eta = (((steps - minetasteps) * newrange) / stepsrange) + mineta
        eta = round(eta, 2)
        print(f'Eta set automatically to: {eta}')

#Automatic clamp_max based on steps
if clamp_max == 'auto':
    if steps <= 35: clamp_max = 0.001
    elif steps <= 75: clamp_max = 0.0125
    elif steps <= 150: clamp_max = 0.02
    elif steps <= 225: clamp_max = 0.035
    elif steps <= 300: clamp_max = 0.05
    elif steps <= 500: clamp_max = 0.075
    else: clamp_max = 0.1
    print(f'Clamp_max automatically set to {clamp_max}')

#Automatic clip_guidance_scale based on overall resolution
if clip_guidance_scale == 'auto':
    res = width_height[0] * width_height[1]  # total pixels
    maxcgsres = 2000000
    mincgsres = 250000
    maxcgs = 50000
    mincgs = 2500
    if res > maxcgsres: clip_guidance_scale = maxcgs
    elif res < mincgsres: clip_guidance_scale = mincgs
    else:
        resrange = (maxcgsres - mincgsres)
        newrange = (maxcgs - mincgs)
        clip_guidance_scale = ((
            (res - mincgsres) * newrange) / resrange) + mincgs
        clip_guidance_scale = round(clip_guidance_scale)
    print(f'clip_guidance_scale set automatically to: {clip_guidance_scale}')

if cl_args.prompt:
    text_prompts["0"] = cl_args.prompt
    print(f'Setting prompt to {text_prompts}')

# PROMPT RANDOMIZERS
# If any word in the prompt starts and ends with _, replace it with a random line from the corresponding text file
# For example, _artist_ will replace with a line from artist.txt

# Build a list of randomizers to draw from:
def randomizer(category):
    randomizers = []
    with open(f'settings/{category}.txt', encoding="utf-8") as f:
        for line in f:
            randomizers.append(line.strip())
    random_item = random.choice(randomizers)
    return(random_item)

# Search through the prompt for any _randomizer_ words and replace them accordingly
prompt_change = False
for k, v in text_prompts.items():
    if type(v) == list:
        newprompts = []
        for prompt in v:
            if "_" in prompt:
                while "_" in prompt:
                    start = prompt.index('_')
                    end = prompt.index('_',start+1)
                    swap = prompt[(start + 1):end]
                    swapped = randomizer(swap)
                    prompt = prompt.replace(f'_{swap}_', swapped, 1)
                newprompt = prompt
                prompt_change = True
            else:
                newprompt = prompt
            newprompts.append(newprompt)
        if prompt_change == True:
            v = newprompts
    else:  # to handle if the prompt is actually a multi-prompt.
        for kk, vv in v.items():
            newprompts = []
            for prompt in vv:
                if "_" in prompt:
                    while "_" in prompt:
                        start = prompt.index('_')
                        end = prompt.index('_',start+1)
                        swap = prompt[(start + 1):end]
                        swapped = randomizer(swap)
                        prompt = prompt.replace(f'_{swap}_', swapped, 1)
                    newprompt = prompt
                    prompt_change = True
                else:
                    newprompt = prompt
                newprompts.append(newprompt)
            if prompt_change == True:
                vv = newprompts
        if prompt_change == True:
            v = {**v, kk: vv}
    if prompt_change == True:
        text_prompts = {**text_prompts, k: v}
        print(f'Prompt with randomizers: {text_prompts}')

# INIT IMAGE RANDOMIZER
# If the setting for init_image is a word between two underscores, we'll pull a random image from that directory,
# and set our size accordingly.

# randomly pick a file name from a directory:
def random_file(directory):
    files = []
    files = os.listdir(f'{initDirPath}/{directory}')
    file = random.choice(files)
    return(file)

# Check for init randomizer in settings, and configure a random init if found
init_image_OriginalPath  = init_image
if init_image != None:
    if init_image.startswith("_") and init_image.endswith("_"):
        randominit_dir = (init_image[1:])
        randominit_dir = (randominit_dir[:-1]) # parse out the directory name
        print(f"Randomly picking an init image from {initDirPath}/{randominit_dir}")
        init_image_OriginalPath = init_image = (f'{initDirPath}/{randominit_dir}/{random_file(randominit_dir)}')
        print(f"New init image is {init_image}")
        # check to see if the image matches the configured size, if not we'll resize it
        temp = Image.open(init_image).convert('RGB')
        temp_width, temp_height = temp.size
        if (temp_width != width_height[0]) or (temp_height != width_height[1]):
            print('Randomly chosen init image does not match width and height from settings.')
            print('It will be resized as temp_init.png and used as your init.')
            temp = temp.resize(width_height, Image.LANCZOS)
            temp.save('temp_init.png')
            init_image = 'temp_init.png'
import torch

# Decide if we're using CPU or GPU, with appropriate settings depending...
if cl_args.cpu or not torch.cuda.is_available():
    DEVICE = torch.device('cpu')
    device = DEVICE
    fp16_mode = False
    cores = os.cpu_count()
    if cl_args.cpu == 0:
        print(
            f'No thread count specified. Using detected {cores} cores for CPU mode.'
        )
    elif cl_args.cpu > cores:
        print(
            f'Too many threads specified. Using detected {cores} cores for CPU mode.'
        )
    else:
        cores = int(cl_args.cpu)
        print(f'Using {cores} cores for CPU mode.')
    torch.set_num_threads(cores)
else:
    DEVICE = torch.device(f'cuda:{cl_args.cuda}')
    device = DEVICE
    fp16_mode = True
    if torch.cuda.get_device_capability(device) == (
            8, 0):  ## A100 fix thanks to Emad
        print('Disabling CUDNN for A100 gpu', file=sys.stderr)
        torch.backends.cudnn.enabled = False

print('Using device:', device)

#@title 2.2 Define necessary functions

# https://gist.github.com/adefossez/0646dbe9ed4005480a2407c62aac8869


def ease(num, t):
    start = num[0]
    end = num[1]
    power = num[2]
    return start + pow(t, power) * (end - start)


def interp(t):
    return 3 * t**2 - 2 * t**3

# return a number between two numbers in a given range
def val_interpolate(x1: float, x2: float, y1: float, y2: float, x: float):
    """Perform linear interpolation for x between (x1,y1) and (x2,y2) """

    return ((y2 - y1) * x + x2 * y1 - x1 * y2) / (x2 - x1)

def perlin(width, height, scale=10, device=None):
    gx, gy = torch.randn(2, width + 1, height + 1, 1, 1, device=device)
    xs = torch.linspace(0, 1, scale + 1)[:-1, None].to(device)
    ys = torch.linspace(0, 1, scale + 1)[None, :-1].to(device)
    wx = 1 - interp(xs)
    wy = 1 - interp(ys)
    dots = 0
    dots += wx * wy * (gx[:-1, :-1] * xs + gy[:-1, :-1] * ys)
    dots += (1 - wx) * wy * (-gx[1:, :-1] * (1 - xs) + gy[1:, :-1] * ys)
    dots += wx * (1 - wy) * (gx[:-1, 1:] * xs - gy[:-1, 1:] * (1 - ys))
    dots += (1 - wx) * (1 - wy) * (-gx[1:, 1:] * (1 - xs) - gy[1:, 1:] *
                                   (1 - ys))
    return dots.permute(0, 2, 1, 3).contiguous().view(width * scale,
                                                      height * scale)


def perlin_ms(octaves, width, height, grayscale, device=device):
    out_array = [0.5] if grayscale else [0.5, 0.5, 0.5]
    # out_array = [0.0] if grayscale else [0.0, 0.0, 0.0]
    for i in range(1 if grayscale else 3):
        scale = 2**len(octaves)
        oct_width = width
        oct_height = height
        for oct in octaves:
            p = perlin(oct_width, oct_height, scale, device)
            out_array[i] += p * oct
            scale //= 2
            oct_width *= 2
            oct_height *= 2
    return torch.cat(out_array)


def create_perlin_noise(octaves=[1, 1, 1, 1],
                        width=2,
                        height=2,
                        grayscale=True):
    out = perlin_ms(octaves, width, height, grayscale)
    if grayscale:
        out = TF.resize(size=(side_y, side_x), img=out.unsqueeze(0))
        out = TF.to_pil_image(out.clamp(0, 1)).convert('RGB')
    else:
        out = out.reshape(-1, 3, out.shape[0] // 3, out.shape[1])
        out = TF.resize(size=(side_y, side_x), img=out)
        out = TF.to_pil_image(out.clamp(0, 1).squeeze())

    out = ImageOps.autocontrast(out)
    return out


def regen_perlin():
    if perlin_mode == 'color':
        init = create_perlin_noise([1.5**-i * 0.5 for i in range(12)], 1, 1,
                                   False)
        init2 = create_perlin_noise([1.5**-i * 0.5 for i in range(8)], 4, 4,
                                    False)
    elif perlin_mode == 'gray':
        init = create_perlin_noise([1.5**-i * 0.5 for i in range(12)], 1, 1,
                                   True)
        init2 = create_perlin_noise([1.5**-i * 0.5 for i in range(8)], 4, 4,
                                    True)
    else:
        init = create_perlin_noise([1.5**-i * 0.5 for i in range(12)], 1, 1,
                                   False)
        init2 = create_perlin_noise([1.5**-i * 0.5 for i in range(8)], 4, 4,
                                    True)

    init = TF.to_tensor(init).add(
        TF.to_tensor(init2)).div(2).to(device).unsqueeze(0).mul(2).sub(1)
    del init2
    return init.expand(batch_size, -1, -1, -1)


def fetch(url_or_path):
    print(f'Fetching {str(url_or_path)}')
    print(f'This might take a while... please wait.')
    if str(url_or_path).startswith('http://') or str(url_or_path).startswith(
            'https://'):
        r = requests.get(url_or_path)
        r.raise_for_status()
        fd = io.BytesIO()
        fd.write(r.content)
        fd.seek(0)
        return fd
    return open(url_or_path, 'rb')


def read_image_workaround(path):
    """OpenCV reads images as BGR, Pillow saves them as RGB. Work around
    this incompatibility to avoid colour inversions."""
    im_tmp = cv2.imread(path)
    return cv2.cvtColor(im_tmp, cv2.COLOR_BGR2RGB)


def parse_prompt(prompt, vars={}):
    if prompt.startswith('http://') or prompt.startswith('https://'):
        vals = prompt.rsplit(':', 2)
        vals = [vals[0] + ':' + vals[1], *vals[2:]]
    else:
        vals = prompt.rsplit(':', 1)
    vals = vals + ['', '1'][len(vals):]
    return vals[0], float(numexpr.evaluate(vals[1], local_dict=vars))



def sinc(x):
    return torch.where(x != 0,
                       torch.sin(math.pi * x) / (math.pi * x), x.new_ones([]))


def lanczos(x, a):
    cond = torch.logical_and(-a < x, x < a)
    out = torch.where(cond, sinc(x) * sinc(x / a), x.new_zeros([]))
    return out / out.sum()


def ramp(ratio, width):
    n = math.ceil(width / ratio + 1)
    out = torch.empty([n])
    cur = 0
    for i in range(out.shape[0]):
        out[i] = cur
        cur += ratio
    return torch.cat([-out[1:].flip([0]), out])[1:-1]


def resample(input, size, align_corners=True):
    n, c, h, w = input.shape
    dh, dw = size

    input = input.reshape([n * c, 1, h, w])

    if dh < h:
        kernel_h = lanczos(ramp(dh / h, 2), 2).to(input.device, input.dtype)
        pad_h = (kernel_h.shape[0] - 1) // 2
        input = F.pad(input, (0, 0, pad_h, pad_h), 'reflect')
        input = F.conv2d(input, kernel_h[None, None, :, None])

    if dw < w:
        kernel_w = lanczos(ramp(dw / w, 2), 2).to(input.device, input.dtype)
        pad_w = (kernel_w.shape[0] - 1) // 2
        input = F.pad(input, (pad_w, pad_w, 0, 0), 'reflect')
        input = F.conv2d(input, kernel_w[None, None, None, :])

    input = input.reshape([n, c, h, w])
    return F.interpolate(input,
                         size,
                         mode='bicubic',
                         align_corners=align_corners)


class MakeCutouts(nn.Module):
    def __init__(self, cut_size, cutn, skip_augs=False):
        super().__init__()
        self.cut_size = cut_size
        self.cutn = cutn
        self.skip_augs = skip_augs
        self.augs = T.Compose([
            T.RandomHorizontalFlip(p=0.5),
            T.Lambda(lambda x: x + torch.randn_like(x) * 0.01),
            T.RandomAffine(degrees=15, translate=(0.1, 0.1)),
            T.Lambda(lambda x: x + torch.randn_like(x) * 0.01),
            T.RandomPerspective(distortion_scale=0.4, p=0.7),
            T.Lambda(lambda x: x + torch.randn_like(x) * 0.01),
            T.RandomGrayscale(p=0.15),
            T.Lambda(lambda x: x + torch.randn_like(x) * 0.01),
            # T.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1, hue=0.1),
        ])

    def forward(self, input):
        input = T.Pad(input.shape[2] // 4, fill=0)(input)
        sideY, sideX = input.shape[2:4]
        max_size = min(sideX, sideY)

        cutouts = []
        for ch in range(self.cutn):
            if ch > self.cutn - self.cutn // 4:
                cutout = input.clone()
            else:
                size = int(max_size * torch.zeros(1, ).normal_(
                    mean=.8, std=.3).clip(float(self.cut_size / max_size), 1.))
                offsetx = torch.randint(0, abs(sideX - size + 1), ())
                offsety = torch.randint(0, abs(sideY - size + 1), ())
                cutout = input[:, :, offsety:offsety + size,
                               offsetx:offsetx + size]

            if not self.skip_augs:
                cutout = self.augs(cutout)
            cutouts.append(resample(cutout, (self.cut_size, self.cut_size)))
            del cutout

        cutouts = torch.cat(cutouts, dim=0)
        return cutouts


cutout_debug = False
padargs = {}


class MakeCutoutsDango(nn.Module):
    def __init__(self,
                 cut_size,
                 Overview=4,
                 InnerCrop=0,
                 IC_Size_Pow=0.5,
                 IC_Grey_P=0.2):
        super().__init__()
        self.cut_size = cut_size
        self.Overview = Overview
        self.InnerCrop = InnerCrop
        self.IC_Size_Pow = IC_Size_Pow
        self.IC_Grey_P = IC_Grey_P
        if args.animation_mode == 'None':
            self.augs = T.Compose([
                T.RandomHorizontalFlip(p=0.5),
                T.Lambda(lambda x: x + torch.randn_like(x) * 0.01),
                T.RandomAffine(degrees=10,
                               translate=(0.05, 0.05),
                               interpolation=T.InterpolationMode.BILINEAR),
                T.Lambda(lambda x: x + torch.randn_like(x) * 0.01),
                T.RandomGrayscale(p=0.1),
                T.Lambda(lambda x: x + torch.randn_like(x) * 0.01),
                T.ColorJitter(brightness=0.1,
                              contrast=0.1,
                              saturation=0.1,
                              hue=0.1),
            ])
        elif args.animation_mode == 'Video Input':
            self.augs = T.Compose([
                T.RandomHorizontalFlip(p=0.5),
                T.Lambda(lambda x: x + torch.randn_like(x) * 0.01),
                T.RandomAffine(degrees=15, translate=(0.1, 0.1)),
                T.Lambda(lambda x: x + torch.randn_like(x) * 0.01),
                T.RandomPerspective(distortion_scale=0.4, p=0.7),
                T.Lambda(lambda x: x + torch.randn_like(x) * 0.01),
                T.RandomGrayscale(p=0.15),
                T.Lambda(lambda x: x + torch.randn_like(x) * 0.01),
                # T.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1, hue=0.1),
            ])
        elif args.animation_mode == '2D' or args.animation_mode == '3D':
            self.augs = T.Compose([
                T.RandomHorizontalFlip(p=0.4),
                T.Lambda(lambda x: x + torch.randn_like(x) * 0.01),
                T.RandomAffine(degrees=10,
                               translate=(0.05, 0.05),
                               interpolation=T.InterpolationMode.BILINEAR),
                T.Lambda(lambda x: x + torch.randn_like(x) * 0.01),
                T.RandomGrayscale(p=0.1),
                T.Lambda(lambda x: x + torch.randn_like(x) * 0.01),
                T.ColorJitter(brightness=0.1,
                              contrast=0.1,
                              saturation=0.1,
                              hue=0.3),
            ])

    def forward(self, input):
        cutouts = []
        gray = T.Grayscale(3)
        sideY, sideX = input.shape[2:4]
        max_size = min(sideX, sideY)
        min_size = min(sideX, sideY, self.cut_size)
        l_size = max(sideX, sideY)
        output_shape = [1, 3, self.cut_size, self.cut_size]
        output_shape_2 = [1, 3, self.cut_size + 2, self.cut_size + 2]
        pad_input = F.pad(input,
                          ((sideY - max_size) // 2, (sideY - max_size) // 2,
                           (sideX - max_size) // 2, (sideX - max_size) // 2),
                          **padargs)
        cutout = resize(pad_input, out_shape=output_shape)

        if self.Overview > 0:
            if self.Overview <= 4:
                if self.Overview >= 1:
                    cutouts.append(cutout)
                if self.Overview >= 2:
                    cutouts.append(gray(cutout))
                if self.Overview >= 3:
                    cutouts.append(TF.hflip(cutout))
                if self.Overview == 4:
                    cutouts.append(gray(TF.hflip(cutout)))
            else:
                cutout = resize(pad_input, out_shape=output_shape)
                for _ in range(self.Overview):
                    cutouts.append(cutout)

            if cutout_debug:
                TF.to_pil_image(cutouts[0].clamp(0, 1).squeeze(0)).save(
                    "/content/cutout_overview0.jpg", quality=99)

        if self.InnerCrop > 0:
            for i in range(self.InnerCrop):
                size = int(
                    torch.rand([])**self.IC_Size_Pow * (max_size - min_size) +
                    min_size)
                offsetx = torch.randint(0, sideX - size + 1, ())
                offsety = torch.randint(0, sideY - size + 1, ())
                cutout = input[:, :, offsety:offsety + size,
                               offsetx:offsetx + size]
                if i <= int(self.IC_Grey_P * self.InnerCrop):
                    cutout = gray(cutout)
                cutout = resize(cutout, out_shape=output_shape)
                cutouts.append(cutout)
            if cutout_debug:
                TF.to_pil_image(cutouts[-1].clamp(0, 1).squeeze(0)).save(
                    "/content/cutout_InnerCrop.jpg", quality=99)
        cutouts = torch.cat(cutouts)
        if skip_augs is not True: cutouts = self.augs(cutouts)
        return cutouts


def spherical_dist_loss(x, y):
    x = F.normalize(x, dim=-1)
    y = F.normalize(y, dim=-1)
    return (x - y).norm(dim=-1).div(2).arcsin().pow(2).mul(2)


def tv_loss(input):
    """L2 total variation loss, as in Mahendran et al."""
    input = F.pad(input, (0, 1, 0, 1), 'replicate')
    x_diff = input[..., :-1, 1:] - input[..., :-1, :-1]
    y_diff = input[..., 1:, :-1] - input[..., :-1, :-1]
    return (x_diff**2 + y_diff**2).mean([1, 2, 3])


def range_loss(input):
    return (input - input.clamp(-1, 1)).pow(2).mean([1, 2, 3])


stop_on_next_loop = False  # Make sure GPU memory doesn't get corrupted from cancelling the run mid-way through, allow a full frame to complete

def do_run():
    seed = args.seed
    #print(range(args.start_frame, args.max_frames))
    for frame_num in range(args.start_frame, args.max_frames):
        if stop_on_next_loop:
            break

        display.clear_output(wait=True)

        # Print Frame progress if animation mode is on
        #print(f'Animation mode is {animation_mode}') #debug
        if args.animation_mode != "None":
            batchBar = tqdm(range(args.max_frames), desc="Frames")
            batchBar.n = frame_num
            batchBar.refresh()

        # Inits if not video frames
        if args.animation_mode != "Video Input":
            if args.init_image == '':
                init_image = None
            else:
                init_image = args.init_image
            init_scale = args.init_scale
            skip_steps = args.skip_steps

        if args.animation_mode == "2D":
            if args.key_frames:
                angle = args.angle_series[frame_num]
                zoom = args.zoom_series[frame_num]
                translation_x = args.translation_x_series[frame_num]
                translation_y = args.translation_y_series[frame_num]
                print(
                    f'angle: {angle}',
                    f'zoom: {zoom}',
                    f'translation_x: {translation_x}',
                    f'translation_y: {translation_y}',
                )

            if frame_num > 0:
                seed = seed + 1
                if resume_run and frame_num == start_frame:
                    img_0 = cv2.imread(
                        batchFolder +
                        f"/{batch_name}({batchNum})_{start_frame-1:04}.png")
                else:
                    img_0 = cv2.imread('prevFrame.png')
                center = (1 * img_0.shape[1] // 2, 1 * img_0.shape[0] // 2)
                trans_mat = np.float32([[1, 0, translation_x],
                                        [0, 1, translation_y]])
                rot_mat = cv2.getRotationMatrix2D(center, angle, zoom)
                trans_mat = np.vstack([trans_mat, [0, 0, 1]])
                rot_mat = np.vstack([rot_mat, [0, 0, 1]])
                transformation_matrix = np.matmul(rot_mat, trans_mat)
                img_0 = cv2.warpPerspective(img_0,
                                            transformation_matrix,
                                            (img_0.shape[1], img_0.shape[0]),
                                            borderMode=cv2.BORDER_WRAP)
                cv2.imwrite('prevFrameScaled.png', img_0)
                init_image = 'prevFrameScaled.png'
                init_scale = args.frames_scale
                skip_steps = args.calc_frames_skip_steps

        if args.animation_mode == "Video Input":
            seed = seed + 1
            init_image = f'{videoFramesFolder}/{frame_num+1:04}.jpg'
            init_scale = args.frames_scale
            skip_steps = args.calc_frames_skip_steps

        loss_values = []

        if seed is not None:
            np.random.seed(seed)
            random.seed(seed)
            torch.manual_seed(seed)
            #torch.cuda.manual_seed_all(seed) # jason -- commented this out because the above handles it and is device agnostic
            torch.backends.cudnn.deterministic = True

        target_embeds, weights = [], []

        if args.prompts_series is not None and frame_num >= len(
                args.prompts_series):
            frame_prompt = args.prompts_series[-1]
        elif args.prompts_series is not None:
            frame_prompt = args.prompts_series[frame_num]
        else:
            frame_prompt = []

        #print(args.image_prompts_series)
        if args.image_prompts_series is not None and frame_num >= len(
                args.image_prompts_series):
            image_prompt = args.image_prompts_series[-1]
        elif args.image_prompts_series is not None:
            image_prompt = args.image_prompts_series[frame_num]
        else:
            image_prompt = []

        if (type(frame_prompt) is list):
            frame_prompt = {"0": frame_prompt}

        print(f'Frame Prompt: {frame_prompt}')

        prev_sample_prompt = []
        model_stats = []

        def do_weights(s):
            nonlocal model_stats, prev_sample_prompt
            sample_prompt = []

            print_sample_prompt = False
            if (str(s) not in frame_prompt.keys()):
                sample_prompt = prev_sample_prompt.copy()
            else:
                print_sample_prompt = True
                sample_prompt = frame_prompt[str(s)].copy()
                prev_sample_prompt = sample_prompt.copy()

            #sample_prompt += additional_prompts

            if (print_sample_prompt):
                print(f' Prompt for step {s}: {sample_prompt}')

            model_stats = []
            for clip_model in clip_models:
                cutn = 16
                model_stat = {
                    "clip_model": None,
                    "target_embeds": [],
                    "make_cutouts": None,
                    "weights": []
                }
                model_stat["clip_model"] = clip_model

                for prompt in sample_prompt:
                    txt, weight = parse_prompt(prompt, {'s': s})
                    txt = clip_model.encode_text(
                        clip.tokenize(prompt).to(device)).float()

                    if args.fuzzy_prompt:
                        for i in range(25):
                            model_stat["target_embeds"].append(
                                (txt + torch.randn(txt.shape).to(device) *
                                 args.rand_mag).clamp(0, 1))
                            model_stat["weights"].append(weight)
                    else:
                        model_stat["target_embeds"].append(txt)
                        model_stat["weights"].append(weight)

                if image_prompt:
                    model_stat["make_cutouts"] = MakeCutouts(
                        clip_model.visual.input_resolution,
                        cutn,
                        skip_augs=skip_augs)
                    for prompt in image_prompt:
                        path, weight = parse_prompt(prompt, {'s': s})
                        weight *= magnitude_multiplier
                        img = Image.open(fetch(path)).convert('RGB')
                        img = TF.resize(img, min(side_x, side_y, *img.size),
                                        T.InterpolationMode.LANCZOS)
                        batch = model_stat["make_cutouts"](TF.to_tensor(
                            img).to(device).unsqueeze(0).mul(2).sub(1))
                        embed = clip_model.encode_image(
                            normalize(batch)).float()
                        if fuzzy_prompt:
                            for i in range(25):
                                model_stat["target_embeds"].append(
                                    (embed +
                                     torch.randn(embed.shape).to(device) *
                                     rand_mag).clamp(0, 1))
                                weights.extend([weight / cutn] * cutn)
                        else:
                            model_stat["target_embeds"].append(embed)
                            model_stat["weights"].extend([weight / cutn] *
                                                         cutn)

                model_stat["target_embeds"] = torch.cat(
                    model_stat["target_embeds"])
                model_stat["weights"] = torch.tensor(model_stat["weights"],
                                                     device=device)
                if model_stat["weights"].sum().abs() < 1e-3:
                    raise RuntimeError('The weights must not sum to 0.')
                model_stat["weights"] /= model_stat["weights"].sum().abs()
                model_stats.append(model_stat)

        initial_weights = False

        print(f'skip steps: {skip_steps}')

        if (skip_steps > 0):
            for i in range(skip_steps, 0, -1):
                if (str(i) in frame_prompt.keys()):
                    do_weights(i)
                    initial_weights = True
                    break

        if (not initial_weights):
            do_weights(0)

        init = None
        if init_image is not None:
            init = Image.open(fetch(init_image)).convert('RGB')
            init = init.resize((args.side_x, args.side_y), Image.LANCZOS)
            init = TF.to_tensor(init).to(device).unsqueeze(0).mul(2).sub(1)

        if args.perlin_init:
            if args.perlin_mode == 'color':
                init = create_perlin_noise([1.5**-i * 0.5 for i in range(12)],
                                           1, 1, False)
                init2 = create_perlin_noise([1.5**-i * 0.5 for i in range(8)],
                                            4, 4, False)
            elif args.perlin_mode == 'gray':
                init = create_perlin_noise([1.5**-i * 0.5 for i in range(12)],
                                           1, 1, True)
                init2 = create_perlin_noise([1.5**-i * 0.5 for i in range(8)],
                                            4, 4, True)
            else:
                init = create_perlin_noise([1.5**-i * 0.5 for i in range(12)],
                                           1, 1, False)
                init2 = create_perlin_noise([1.5**-i * 0.5 for i in range(8)],
                                            4, 4, True)
            # init = TF.to_tensor(init).add(TF.to_tensor(init2)).div(2).to(device)
            init = TF.to_tensor(init).add(TF.to_tensor(init2)).div(2).to(
                device).unsqueeze(0).mul(2).sub(1)
            del init2

        cur_t = None

        def cond_fn(x, t, y=None):
            with torch.enable_grad():
                x_is_NaN = False
                x = x.detach().requires_grad_()
                n = x.shape[0]
                if use_secondary_model is True:
                    alpha = torch.tensor(diffusion.sqrt_alphas_cumprod[cur_t],
                                         device=device,
                                         dtype=torch.float32)
                    sigma = torch.tensor(
                        diffusion.sqrt_one_minus_alphas_cumprod[cur_t],
                        device=device,
                        dtype=torch.float32)
                    cosine_t = alpha_sigma_to_t(alpha, sigma)
                    out = secondary_model(x, cosine_t[None].repeat([n])).pred
                    fac = diffusion.sqrt_one_minus_alphas_cumprod[cur_t]
                    x_in = out * fac + x * (1 - fac)
                    x_in_grad = torch.zeros_like(x_in)
                else:
                    my_t = torch.ones([n], device=device,
                                      dtype=torch.long) * cur_t
                    out = diffusion.p_mean_variance(model,
                                                    x,
                                                    my_t,
                                                    clip_denoised=False,
                                                    model_kwargs={'y': y})
                    fac = diffusion.sqrt_one_minus_alphas_cumprod[cur_t]
                    x_in = out['pred_xstart'] * fac + x * (1 - fac)
                    x_in_grad = torch.zeros_like(x_in)
                for model_stat in model_stats:
                    for i in range(args.cutn_batches):
                        t_int = int(
                            t.item()
                        ) + 1  #errors on last step without +1, need to find source
                        #when using SLIP Base model the dimensions need to be hard coded to avoid AttributeError: 'VisionTransformer' object has no attribute 'input_resolution'
                        try:
                            input_resolution = model_stat[
                                "clip_model"].visual.input_resolution
                        except:
                            input_resolution = 224

                        temp_ic_pow = 0.0
                        if type(args.cut_ic_pow_final) is int:
                            # interpolate value if we have a range of cut_ic_pow to do
                            percent_done = (steps - cur_t) / steps
                            temp_ic_pow = val_interpolate(float(args.cut_ic_pow), 0.0, float(args.cut_ic_pow_final), 1.0, float(percent_done))
                        else:
                            temp_ic_pow = args.cut_ic_pow
                        cuts = MakeCutoutsDango(
                            input_resolution,
                            Overview=args.cut_overview[1000 - t_int],
                            InnerCrop=args.cut_innercut[1000 - t_int],
                            IC_Size_Pow=temp_ic_pow,
                            IC_Grey_P=args.cut_icgray_p[1000 - t_int])
                        clip_in = normalize(cuts(x_in.add(1).div(2)))
                        image_embeds = model_stat["clip_model"].encode_image(
                            clip_in).float()
                        dists = spherical_dist_loss(
                            image_embeds.unsqueeze(1),
                            model_stat["target_embeds"].unsqueeze(0))
                        dists = dists.view([
                            args.cut_overview[1000 - t_int] +
                            args.cut_innercut[1000 - t_int], n, -1
                        ])
                        losses = dists.mul(
                            model_stat["weights"]).sum(2).mean(0)
                        loss_values.append(losses.sum().item(
                        ))  # log loss, probably shouldn't do per cutn_batch
                        x_in_grad += torch.autograd.grad(
                            losses.sum() * clip_guidance_scale,
                            x_in)[0] / cutn_batches
                tv_losses = tv_loss(x_in)
                if use_secondary_model is True:
                    range_losses = range_loss(out)
                else:
                    range_losses = range_loss(out['pred_xstart'])
                sat_losses = torch.abs(x_in - x_in.clamp(min=-1, max=1)).mean()
                loss = tv_losses.sum() * tv_scale + range_losses.sum(
                ) * range_scale + sat_losses.sum() * sat_scale
                if init is not None and args.init_scale:
                    init_losses = lpips_model(x_in, init)
                    loss = loss + init_losses.sum() * args.init_scale
                x_in_grad += torch.autograd.grad(loss, x_in)[0]
                if torch.isnan(x_in_grad).any() == False:
                    grad = -torch.autograd.grad(x_in, x, x_in_grad)[0]
                else:
                    # print("NaN'd")
                    x_is_NaN = True
                    grad = torch.zeros_like(x)
            if args.clamp_grad and x_is_NaN == False:
                magnitude = grad.square().mean().sqrt()
                timestep = (1000 - t.item()) / 1000
                clamp_max = 0

                #save_tensor_as_image(grad, "grad.png")

                if isinstance(args.clamp_max, list):
                    clamp_max = ease(args.clamp_max, timestep)
                elif isinstance(args.clamp_max, str):
                    clamp_max = float(numexpr.evaluate(args.clamp_max))
                else:
                    clamp_max = args.clamp_max

                return grad * magnitude.clamp(
                    max=args.clamp_max
                ) / magnitude  #min=-0.02, min=-clamp_max,
            return grad

        if args.sampling_mode == 'ddim':
            sample_fn = diffusion.ddim_sample_loop_progressive
        else:
            sample_fn = diffusion.plms_sample_loop_progressive

        image_display = Output()
        for i in range(args.n_batches):
            if args.animation_mode == 'None':
                #display.clear_output(wait=True)
                batchBar = tqdm(range(args.n_batches), desc="Batches")
                batchBar.n = i
                batchBar.refresh()
            print('')
            #display.display(image_display)
            gc.collect()
            torch.cuda.empty_cache()
            cur_t = diffusion.num_timesteps - skip_steps - 1
            total_steps = cur_t

            if perlin_init:
                init = regen_perlin()

            def do_sample_fn(_init_image, _skip):
                if args.sampling_mode == 'ddim':
                    samples = sample_fn(
                        model,
                        (batch_size, 3, args.side_y, args.side_x),
                        clip_denoised=clip_denoised,
                        model_kwargs={},
                        cond_fn=cond_fn,
                        progress=True,
                        skip_timesteps=_skip,
                        init_image=init,
                        randomize_class=randomize_class,
                        eta=eta,
                    )
                else:
                    samples = sample_fn(
                        model,
                        (batch_size, 3, args.side_y, args.side_x),
                        clip_denoised=clip_denoised,
                        model_kwargs={},
                        cond_fn=cond_fn,
                        progress=True,
                        skip_timesteps=_skip,
                        init_image=init,
                        randomize_class=randomize_class,
                        order=2,
                    )

                return samples

            # with run_display:
            # display.clear_output(wait=True)
            imgToSharpen = None
            adjustment_prompt = []
            while cur_t >= stop_early:
                samples = do_sample_fn(init, steps - cur_t - 1)
                for j, sample in enumerate(samples):
                    cur_t -= 1
                    if (cur_t < stop_early):
                        cur_t = -1

                    intermediateStep = False
                    if args.steps_per_checkpoint is not None:
                        if j % steps_per_checkpoint == 0 and j > 0:
                            intermediateStep = True
                    elif j in args.intermediate_saves:
                        intermediateStep = True
                    with image_display:
                        if j % args.display_rate == 0 or cur_t == -1 or intermediateStep == True:
                            for k, image in enumerate(sample['pred_xstart']):
                                # tqdm.write(f'Batch {i}, step {j}, output {k}:')
                                current_time = datetime.now().strftime(
                                    '%y%m%d-%H%M%S_%f')
                                percent = math.ceil(j / total_steps * 100)
                                if args.n_batches > 0:
                                    #if intermediates are saved to the subfolder, don't append a step or percentage to the name
                                    if cur_t == -1 and args.intermediates_in_subfolder is True:
                                        save_num = f'{frame_num:04}' if animation_mode != "None" else i
                                        filename = f'{args.batch_name}_{args.batchNum}_{save_num}.png'
                                    else:
                                        #If we're working with percentages, append it
                                        if args.steps_per_checkpoint is not None:
                                            filename = f'{args.batch_name}({args.batchNum})_{i:04}-{percent:02}%.png'
                                        # Or else, iIf we're working with specific steps, append those
                                        else:
                                            filename = f'{args.batch_name}({args.batchNum})_{i:04}-{j:03}.png'
                                image = TF.to_pil_image(
                                    image.add(1).div(2).clamp(0, 1))
                                #add some key metadata to the PNG if the commandline allows it
                                metadata = PngInfo()
                                if add_metadata == True:
                                    metadata.add_text("prompt",
                                                      str(text_prompts))
                                    metadata.add_text("seed", str(seed))
                                    metadata.add_text("steps", str(steps))
                                    metadata.add_text("init_image",
                                                      str(init_image_OriginalPath))
                                    metadata.add_text("skip_steps",
                                                      str(skip_steps))
                                    metadata.add_text("clip_guidance_scale",
                                                      str(clip_guidance_scale))
                                    metadata.add_text("tv_scale",
                                                      str(tv_scale))
                                    metadata.add_text("range_scale",
                                                      str(range_scale))
                                    metadata.add_text("sat_scale",
                                                      str(sat_scale))
                                    metadata.add_text("eta", str(eta))
                                    metadata.add_text("clamp_max",
                                                      str(clamp_max))
                                    metadata.add_text("cut_overview",
                                                      str(cut_overview))
                                    metadata.add_text("cut_innercut",
                                                      str(cut_innercut))
                                    metadata.add_text("cut_ic_pow",
                                                      str(cut_ic_pow))

                                if j % args.display_rate == 0 or cur_t == -1:
                                    if cl_args.cuda != '0':
                                        image.save(f"progress{cl_args.cuda}.png") # note the GPU being used if it's not 0, so it won't overwrite other GPU's work
                                    else:
                                        image.save('progress.png')
                                    display.clear_output(wait=True)
                                    #display.display(display.Image('progress.png'))
                                if args.steps_per_checkpoint is not None:
                                    if j % args.steps_per_checkpoint == 0 and j > 0:
                                        if args.intermediates_in_subfolder is True:
                                            image.save(
                                                f'{partialFolder}/{filename}')
                                        else:
                                            image.save(
                                                f'{batchFolder}/{filename}')
                                else:
                                    if j in args.intermediate_saves:
                                        if args.intermediates_in_subfolder is True:
                                            image.save(
                                                f'{partialFolder}/{filename}')
                                        else:
                                            image.save(
                                                f'{batchFolder}/{filename}')
                                    if geninit is True:
                                        image.save('geninit.png')
                                        raise KeyboardInterrupt

                                if cur_t == -1:
                                    if frame_num == 0:
                                        save_settings()
                                    if args.animation_mode != "None":
                                        image.save('prevFrame.png')
                                    if args.sharpen_preset != "Off" and animation_mode == "None":
                                        imgToSharpen = image
                                        if args.keep_unsharp is True:
                                            image.save(
                                                f'{unsharpenFolder}/{filename}'
                                            )
                                    else:
                                        image.save(f'{batchFolder}/{filename}',
                                                   pnginfo=metadata)
                                    if args.animation_mode == "None" and letsgobig == False:
                                        print('Incrementing seed by one.')
                                        seed = seed + 1
                                        np.random.seed(seed)
                                        random.seed(seed)
                                        torch.manual_seed(seed)
                                    # if frame_num != args.max_frames-1:
                                    #   display.clear_output()

                    dynamic_adjustment = False
                    adjustment_prompt = []
                    magnitude_multiplier = 1
                    image = sample['pred_xstart'][0]
                    image = TF.to_pil_image(image.add(1).div(2).clamp(0, 1))

                    if (gui):
                        prdgui.update_image(image)
                        #prdgui.update_text(str(cur_t))

                    if (dynamic_adjustment):
                        stat = ImageStat.Stat(image)

                        print(f" stddev: {stat.stddev}")
                        print(f"var:    {stat.var}")
                        print(f"mean:   {stat.mean}")
                        # Inaccurate way of calculating brightness.  Adjust later.
                        brightness = (stat.mean[0] + stat.mean[1] +
                                      stat.mean[2]) / 3

                        #print(f' brightness: {brightness}')
                        overexposure_threshold = 140
                        overexposure_adjustment_magnitude = 10
                        overexposure_adjustment_max = 4

                        underexposure_threshold = 80
                        underexposure_adjustment_magnitude = 10
                        underexposure_adjustment_max = 4

                        #Track the total magnitude of the adjustments so it can be added to the main prompt
                        total_adjustment_magnitude = 0
                        adjustment_prompt = []

                        if (brightness > overexposure_threshold):
                            overexposure = brightness - overexposure_threshold
                            magnitude = overexposure / (
                                (255 - overexposure_threshold) /
                                overexposure_adjustment_magnitude)
                            if (magnitude > overexposure_adjustment_max):
                                magnitude = overexposure_adjustment_max
                            adjustment_prompt += [
                                #f'overexposed:-{magnitude}',
                                #f'grainy:-{magnitude}', f'low contrast:{magnitude}'
                                f'overexposed, grainy, high contrast, brightness:-{magnitude}',
                                f'dark color scheme:{magnitude}',
                                #f'low contrast:{magnitude}',
                                #f'white, yellow, pink, magenta:-{magnitude}'
                            ]
                            total_adjustment_magnitude += abs(magnitude)

                        if (brightness < underexposure_threshold):
                            underexposure = underexposure_threshold - brightness
                            magnitude = underexposure / underexposure_threshold * underexposure_adjustment_magnitude
                            if (magnitude > underexposure_adjustment_max):
                                magnitude = underexposure_adjustment_max
                            adjustment_prompt += [
                                f'bright color scheme, midday, blinding light:{magnitude}'
                            ]
                            total_adjustment_magnitude += abs(magnitude)

                        if (len(adjustment_prompt) > 0):
                            print(
                                f" {j}: {stat.mean}/{brightness}: {adjustment_prompt}"
                            )
                        magnitude_multiplier += total_adjustment_magnitude

                        #if (j < 40 and len(adjustment_prompt) > 0):
                        #    magnitude_multiplier *= (j + 1) / 40

                    do_weights(steps - cur_t - 1)

                    image = sample['pred_xstart'][0]
                    image = TF.to_pil_image(image.add(1).div(2).clamp(0, 1))
                    stat = ImageStat.Stat(image)

                    brightness = sum(stat.mean) / len(stat.mean)
                    contrast = sum(stat.stddev) / len(stat.stddev)

                    s = steps - cur_t

                    #print(f" Contrast at {s}: {contrast}")
                    #print(f" Brightness at {s}: {brightness}")

                    if (s % adjustment_interval == 0) and (fix_brightness_contrast == True):
                        if (high_brightness_adjust
                                and s > high_brightness_start
                                and brightness > high_brightness_threshold):
                            print(
                                " Brightness over threshold. Compensating! Total steps counter might change, it's okay..."
                            )
                            filter = ImageEnhance.Brightness(image)
                            image = filter.enhance(
                                high_brightness_adjust_amount)
                            init = TF.to_tensor(image).to(device).unsqueeze(
                                0).mul(2).sub(1)
                            break

                        if (low_brightness_adjust and s > low_brightness_start
                                and brightness < low_brightness_threshold):
                            print(
                                " Brightness below threshold. Compensating! Total steps counter might change, it's okay..."
                            )
                            filter = ImageEnhance.Brightness(image)
                            image = filter.enhance(
                                low_brightness_adjust_amount)
                            init = TF.to_tensor(image).to(device).unsqueeze(
                                0).mul(2).sub(1)
                            break

                        if (high_contrast_adjust and s > high_contrast_start
                                and contrast > high_contrast_threshold):
                            print(
                                " Contrast over threshold. Compensating! Total steps counter might change, it's okay..."
                            )
                            filter = ImageEnhance.Contrast(image)
                            image = filter.enhance(high_contrast_adjust_amount)
                            init = TF.to_tensor(image).to(device).unsqueeze(
                                0).mul(2).sub(1)
                            break

                        if (low_contrast_adjust and s > low_contrast_start
                                and contrast < low_contrast_threshold):
                            print(
                                " Contrast below threshold. Compensating! Total steps counter might change, it's okay..."
                            )
                            filter = ImageEnhance.Contrast(image)
                            image = filter.enhance(low_contrast_adjust_amount)
                            init = TF.to_tensor(image).to(device).unsqueeze(
                                0).mul(2).sub(1)
                            break

                    if (cur_t == -1):
                        break


            with image_display:
                if args.sharpen_preset != "Off" and animation_mode == "None":
                    print('Skipping Diffusion Sharpening (not currently supported)...')
                    #do_superres(imgToSharpen, f'{batchFolder}/{filename}')
                    display.clear_output()

            plt.plot(np.array(loss_values), 'r')


def save_settings():
    setting_list = {
        'batch_name': batch_name,
        'text_prompts': text_prompts,
        'n_batches': n_batches,
        'steps': steps,
        'display_rate': display_rate,
        'width_height_scale': width_height_scale,
        'width': int(width_height[0] / width_height_scale),
        'height': int(width_height[1] / width_height_scale),
        'set_seed': seed,
        'image_prompts': image_prompts,
        'clip_guidance_scale': clip_guidance_scale,
        'tv_scale': tv_scale,
        'range_scale': range_scale,
        'sat_scale': sat_scale,
        # 'cutn': cutn,
        'cutn_batches': cutn_batches,
        'max_frames': max_frames,
        'interp_spline': interp_spline,
        # 'rotation_per_frame': rotation_per_frame,
        'init_image': init_image,
        'init_scale': init_scale,
        'skip_steps': skip_steps,
        # 'zoom_per_frame': zoom_per_frame,
        'frames_scale': frames_scale,
        'frames_skip_steps': frames_skip_steps,
        'perlin_init': perlin_init,
        'perlin_mode': perlin_mode,
        'skip_augs': skip_augs,
        'randomize_class': randomize_class,
        'clip_denoised': clip_denoised,
        'clamp_grad': clamp_grad,
        'clamp_max': clamp_max,
        'fuzzy_prompt': fuzzy_prompt,
        'rand_mag': rand_mag,
        'eta': eta,
        'diffusion_model': diffusion_model,
        'use_secondary_model': use_secondary_model,
        'diffusion_steps': diffusion_steps,
        'sampling_mode': sampling_mode,
        'ViTB32': ViTB32,
        'ViTB16': ViTB16,
        'ViTL14': ViTL14,
        'ViTL14_336': ViTL14_336,
        'RN101': RN101,
        'RN50': RN50,
        'RN50x4': RN50x4,
        'RN50x16': RN50x16,
        'RN50x64': RN50x64,
#        'SLIPB16': SLIPB16,
#        'SLIPL16': SLIPL16,
        'cut_overview': str(cut_overview),
        'cut_innercut': str(cut_innercut),
        'cut_ic_pow': cut_ic_pow,
        'cut_ic_pow': cut_ic_pow_final,
        'cut_icgray_p': str(cut_icgray_p),
        'animation_mode': animation_mode,
        'key_frames': key_frames,
        'angle': angle,
        'zoom': zoom,
        'translation_x': translation_x,
        'translation_y': translation_y,
        'video_init_path': video_init_path,
        'extract_nth_frame': extract_nth_frame,
        'stop_early': stop_early,
        'fix_brightness_contrast': fix_brightness_contrast,
        'adjustment_interval': adjustment_interval,
        'high_contrast_threshold': high_contrast_threshold,
        'high_contrast_adjust_amount': high_contrast_adjust_amount,
        'high_contrast_start': high_contrast_start,
        'high_contrast_adjust': high_contrast_adjust,
        'low_contrast_threshold': low_contrast_threshold,
        'low_contrast_adjust_amount': low_contrast_adjust_amount,
        'low_contrast_start': low_contrast_start,
        'low_contrast_adjust': low_contrast_adjust,
        'high_brightness_threshold': high_brightness_threshold,
        'high_brightness_adjust_amount': high_brightness_adjust_amount,
        'high_brightness_start': high_brightness_start,
        'high_brightness_adjust': high_brightness_adjust,
        'low_brightness_threshold': low_brightness_threshold,
        'low_brightness_adjust_amount': low_brightness_adjust_amount,
        'low_brightness_start': low_brightness_start,
        'low_brightness_adjust': low_brightness_adjust,
        'sharpen_preset': sharpen_preset,
        'keep_unsharp': keep_unsharp,
        'gobig_orientation': gobig_orientation,
        'gobig_scale': gobig_scale,
    }
    with open(f"{batchFolder}/{batch_name}_{batchNum}_settings.json",
              "w+",
              encoding="utf-8") as f:  #save settings
        json.dump(setting_list, f, ensure_ascii=False, indent=4)


#@title 2.3 Define the secondary diffusion model


def append_dims(x, n):
    return x[(Ellipsis, *(None, ) * (n - x.ndim))]


def expand_to_planes(x, shape):
    return append_dims(x, len(shape)).repeat([1, 1, *shape[2:]])


def alpha_sigma_to_t(alpha, sigma):
    return torch.atan2(sigma, alpha) * 2 / math.pi


def t_to_alpha_sigma(t):
    return torch.cos(t * math.pi / 2), torch.sin(t * math.pi / 2)


@dataclass
class DiffusionOutput:
    v: torch.Tensor
    pred: torch.Tensor
    eps: torch.Tensor


class ConvBlock(nn.Sequential):
    def __init__(self, c_in, c_out):
        super().__init__(
            nn.Conv2d(c_in, c_out, 3, padding=1),
            nn.ReLU(inplace=True),
        )


class SkipBlock(nn.Module):
    def __init__(self, main, skip=None):
        super().__init__()
        self.main = nn.Sequential(*main)
        self.skip = skip if skip else nn.Identity()

    def forward(self, input):
        return torch.cat([self.main(input), self.skip(input)], dim=1)


class FourierFeatures(nn.Module):
    def __init__(self, in_features, out_features, std=1.):
        super().__init__()
        assert out_features % 2 == 0
        self.weight = nn.Parameter(
            torch.randn([out_features // 2, in_features]) * std)

    def forward(self, input):
        f = 2 * math.pi * input @ self.weight.T
        return torch.cat([f.cos(), f.sin()], dim=-1)


class SecondaryDiffusionImageNet(nn.Module):
    def __init__(self):
        super().__init__()
        c = 64  # The base channel count

        self.timestep_embed = FourierFeatures(1, 16)

        self.net = nn.Sequential(
            ConvBlock(3 + 16, c),
            ConvBlock(c, c),
            SkipBlock([
                nn.AvgPool2d(2),
                ConvBlock(c, c * 2),
                ConvBlock(c * 2, c * 2),
                SkipBlock([
                    nn.AvgPool2d(2),
                    ConvBlock(c * 2, c * 4),
                    ConvBlock(c * 4, c * 4),
                    SkipBlock([
                        nn.AvgPool2d(2),
                        ConvBlock(c * 4, c * 8),
                        ConvBlock(c * 8, c * 4),
                        nn.Upsample(scale_factor=2,
                                    mode='bilinear',
                                    align_corners=False),
                    ]),
                    ConvBlock(c * 8, c * 4),
                    ConvBlock(c * 4, c * 2),
                    nn.Upsample(scale_factor=2,
                                mode='bilinear',
                                align_corners=False),
                ]),
                ConvBlock(c * 4, c * 2),
                ConvBlock(c * 2, c),
                nn.Upsample(scale_factor=2,
                            mode='bilinear',
                            align_corners=False),
            ]),
            ConvBlock(c * 2, c),
            nn.Conv2d(c, 3, 3, padding=1),
        )

    def forward(self, input, t):
        timestep_embed = expand_to_planes(self.timestep_embed(t[:, None]),
                                          input.shape)
        v = self.net(torch.cat([input, timestep_embed], dim=1))
        alphas, sigmas = map(partial(append_dims, n=v.ndim),
                             t_to_alpha_sigma(t))
        pred = input * alphas - v * sigmas
        eps = input * sigmas + v * alphas
        return DiffusionOutput(v, pred, eps)


class SecondaryDiffusionImageNet2(nn.Module):
    def __init__(self):
        super().__init__()
        c = 64  # The base channel count
        cs = [c, c * 2, c * 2, c * 4, c * 4, c * 8]

        self.timestep_embed = FourierFeatures(1, 16)
        self.down = nn.AvgPool2d(2)
        self.up = nn.Upsample(scale_factor=2,
                              mode='bilinear',
                              align_corners=False)

        self.net = nn.Sequential(
            ConvBlock(3 + 16, cs[0]),
            ConvBlock(cs[0], cs[0]),
            SkipBlock([
                self.down,
                ConvBlock(cs[0], cs[1]),
                ConvBlock(cs[1], cs[1]),
                SkipBlock([
                    self.down,
                    ConvBlock(cs[1], cs[2]),
                    ConvBlock(cs[2], cs[2]),
                    SkipBlock([
                        self.down,
                        ConvBlock(cs[2], cs[3]),
                        ConvBlock(cs[3], cs[3]),
                        SkipBlock([
                            self.down,
                            ConvBlock(cs[3], cs[4]),
                            ConvBlock(cs[4], cs[4]),
                            SkipBlock([
                                self.down,
                                ConvBlock(cs[4], cs[5]),
                                ConvBlock(cs[5], cs[5]),
                                ConvBlock(cs[5], cs[5]),
                                ConvBlock(cs[5], cs[4]),
                                self.up,
                            ]),
                            ConvBlock(cs[4] * 2, cs[4]),
                            ConvBlock(cs[4], cs[3]),
                            self.up,
                        ]),
                        ConvBlock(cs[3] * 2, cs[3]),
                        ConvBlock(cs[3], cs[2]),
                        self.up,
                    ]),
                    ConvBlock(cs[2] * 2, cs[2]),
                    ConvBlock(cs[2], cs[1]),
                    self.up,
                ]),
                ConvBlock(cs[1] * 2, cs[1]),
                ConvBlock(cs[1], cs[0]),
                self.up,
            ]),
            ConvBlock(cs[0] * 2, cs[0]),
            nn.Conv2d(cs[0], 3, 3, padding=1),
        )

    def forward(self, input, t):
        timestep_embed = expand_to_planes(self.timestep_embed(t[:, None]),
                                          input.shape)
        v = self.net(torch.cat([input, timestep_embed], dim=1))
        alphas, sigmas = map(partial(append_dims, n=v.ndim),
                             t_to_alpha_sigma(t))
        pred = input * alphas - v * sigmas
        eps = input * sigmas + v * alphas
        return DiffusionOutput(v, pred, eps)

"""# 2. Diffusion and CLIP model settings"""

#@markdown ####**Models Settings:**
#diffusion_model = "512x512_diffusion_uncond_finetune_008100" #@param ["256x256_diffusion_uncond", "512x512_diffusion_uncond_finetune_008100"]
#use_secondary_model = True #@param {type: 'boolean'}

timestep_respacing = '50'  # param ['25','50','100','150','250','500','1000','ddim25','ddim50', 'ddim75', 'ddim100','ddim150','ddim250','ddim500','ddim1000']
#diffusion_steps = 1000 # param {type: 'number'}
use_checkpoint = True  #@param {type: 'boolean'}
#ViTB32 = True #@param{type:"boolean"} Low RAM requirement, low accuracy
#ViTB16 = True #@param{type:"boolean"} Low RAM requirement, medium accuracy
#ViTL14 = False #@param{type:"boolean"} High RAM requirement, very high accuracy
#RN101 = True #@param{type:"boolean"} Low RAM requirement, low accuracy
#RN50 = True #@param{type:"boolean"} Low RAM requirement, medium accuracy
#RN50x4 = True #@param{type:"boolean"} Medium RAM requirement, high accuracy
#RN50x16 = False #@param{type:"boolean"} High RAM requirement, high accuracy
#SLIPB16 = False # param{type:"boolean"}
#SLIPL16 = False # param{type:"boolean"}
other_sampling_mode = 'bicubic'
#@markdown If you're having issues with model downloads, check this to compare SHA's:
check_model_SHA = False  #@param{type:"boolean"}

def download_models(diffusion_model,use_secondary_model,fallback=False):
  model_256_downloaded = False
  model_512_downloaded = False
  model_secondary_downloaded = False

  model_256_SHA = '983e3de6f95c88c81b2ca7ebb2c217933be1973b1ff058776b970f901584613a'
  model_512_SHA = '9c111ab89e214862b76e1fa6a1b3f1d329b1a88281885943d2cdbe357ad57648'
  model_secondary_SHA = '983e3de6f95c88c81b2ca7ebb2c217933be1973b1ff058776b970f901584613a'

  model_256_link = 'https://openaipublic.blob.core.windows.net/diffusion/jul-2021/256x256_diffusion_uncond.pt'
  model_512_link = 'http://batbot.tv/ai/models/guided-diffusion/512x512_diffusion_uncond_finetune_008100.pt'
  model_secondary_link = 'https://the-eye.eu/public/AI/models/v-diffusion/secondary_model_imagenet_2.pth'

  model_256_link_fb = 'https://www.dropbox.com/s/9tqnqo930mpnpcn/256x256_diffusion_uncond.pt'
  model_512_link_fb = 'https://huggingface.co/lowlevelware/512x512_diffusion_unconditional_ImageNet/resolve/main/512x512_diffusion_uncond_finetune_008100.pt'
  model_secondary_link_fb = 'https://www.dropbox.com/s/luv4fezod3r8d2n/secondary_model_imagenet_2.pth'

  model_256_path = f'{model_path}/256x256_diffusion_uncond.pt'
  model_512_path = f'{model_path}/512x512_diffusion_uncond_finetune_008100.pt'
  model_secondary_path = f'{model_path}/secondary_model_imagenet_2.pth'

  if fallback:
    model_256_link = model_256_link_fb
    model_512_link = model_512_link_fb
    model_secondary_link = model_secondary_link_fb
  # Download the diffusion model
  if diffusion_model == '256x256_diffusion_uncond':
    if os.path.exists(model_256_path) and check_model_SHA:
      print('Checking 256 Diffusion File')
      with open(model_256_path,"rb") as f:
          bytes = f.read()
          hash = hashlib.sha256(bytes).hexdigest();
      if hash == model_256_SHA:
        print('256 Model SHA matches')
        model_256_downloaded = True
      else:
        print("256 Model SHA doesn't match, redownloading...")
        #wget(model_256_link, model_path)
        print('256 Model downloading. This may take a while...')
        urllib.request.urlretrieve(model_256_link, model_256_path)
        if os.path.exists(model_256_path):
          model_256_downloaded = True
        else:
          print('First URL Failed using FallBack')
          download_models(diffusion_model,use_secondary_model,True)
    elif os.path.exists(model_256_path) and not check_model_SHA or model_256_downloaded == True:
      print('256 Model already downloaded, check check_model_SHA if the file is corrupt')
    else:
      #wget(model_256_link, model_path)
      print('256 Model downloading. This may take a while...')
      urllib.request.urlretrieve(model_256_link, model_256_path)
      if os.path.exists(model_256_path):
        model_256_downloaded = True
      else:
        print('First URL failed, using backup')
        download_models(diffusion_model,True)
  elif diffusion_model == '512x512_diffusion_uncond_finetune_008100':
    if os.path.exists(model_512_path) and check_model_SHA:
      print('Checking 512 Diffusion File')
      with open(model_512_path,"rb") as f:
          bytes = f.read()
          hash = hashlib.sha256(bytes).hexdigest();
      if hash == model_512_SHA:
        print('512 Model SHA matches')
        if os.path.exists(model_512_path):
          model_512_downloaded = True
        else:
          print('First URL failed, using backup')
          download_models(diffusion_model,use_secondary_model,True)
      else:
        print("512 Model SHA doesn't match, redownloading...")
        #wget(model_512_link, model_path)
        print('512 Model downloading. This may take a while...')
        urllib.request.urlretrieve(model_512_link, model_512_path)
        if os.path.exists(model_512_path):
          model_512_downloaded = True
        else:
          print('First URL failed, using backup')
          download_models(diffusion_model,use_secondary_model,True)
    elif os.path.exists(model_512_path) and not check_model_SHA or model_512_downloaded == True:
      print('512 Model already downloaded, check check_model_SHA if the file is corrupt')
    else:
      #wget(model_512_link, model_path)
      print('512 Model downloading. This may take a while...')
      urllib.request.urlretrieve(model_512_link, model_512_path)
      model_512_downloaded = True
  # Download the secondary diffusion model v2
  if use_secondary_model == True:
    if os.path.exists(model_secondary_path) and check_model_SHA:
      print('Checking Secondary Diffusion File')
      with open(model_secondary_path,"rb") as f:
          bytes = f.read()
          hash = hashlib.sha256(bytes).hexdigest();
      if hash == model_secondary_SHA:
        print('Secondary Model SHA matches')
        model_secondary_downloaded = True
      else:
        print("Secondary Model SHA doesn't match, redownloading...")
        #wget(model_secondary_link, model_path)
        print('Secondary Model downloading. This may take a while...')
        urllib.request.urlretrieve(model_secondary_link, model_secondary_path)
        if os.path.exists(model_secondary_path):
          model_secondary_downloaded = True
        else:
          print('First URL failed, using backup')
          download_models(diffusion_model,use_secondary_model,True)
    elif os.path.exists(model_secondary_path) and not check_model_SHA or model_secondary_downloaded == True:
      print('Secondary Model already downloaded, check check_model_SHA if the file is corrupt')
    else:
      #wget(model_secondary_link, model_path)
      print('Secondary Model downloading. This may take a while...')
      urllib.request.urlretrieve(model_secondary_link, model_secondary_path)
      if os.path.exists(model_secondary_path):
          model_secondary_downloaded = True
      else:
        print('First URL Failed using FallBack')
        download_models(diffusion_model,use_secondary_model,True)

download_models(diffusion_model,use_secondary_model)

model_config = model_and_diffusion_defaults()
if diffusion_model == '512x512_diffusion_uncond_finetune_008100':
    model_config.update({
        'attention_resolutions': '32, 16, 8',
        'class_cond': False,
        'diffusion_steps': diffusion_steps,
        'rescale_timesteps': True,
        'timestep_respacing': timestep_respacing,
        'image_size': 512,
        'learn_sigma': True,
        'noise_schedule': 'linear',
        'num_channels': 256,
        'num_head_channels': 64,
        'num_res_blocks': 2,
        'resblock_updown': True,
        'use_checkpoint': use_checkpoint,
        'use_fp16': fp16_mode,
        'use_scale_shift_norm': True,
    })
elif diffusion_model == '256x256_diffusion_uncond':
    model_config.update({
        'attention_resolutions': '32, 16, 8',
        'class_cond': False,
        'diffusion_steps': diffusion_steps,
        'rescale_timesteps': True,
        'timestep_respacing': timestep_respacing,
        'image_size': 256,
        'learn_sigma': True,
        'noise_schedule': 'linear',
        'num_channels': 256,
        'num_head_channels': 64,
        'num_res_blocks': 2,
        'resblock_updown': True,
        'use_checkpoint': use_checkpoint,
        'use_fp16': fp16_mode,
        'use_scale_shift_norm': True,
    })

model_default = model_config['image_size']

if use_secondary_model:
    secondary_model = SecondaryDiffusionImageNet2()
    secondary_model.load_state_dict(
        torch.load(f'{model_path}/secondary_model_imagenet_2.pth',
                   map_location='cpu'))
    secondary_model.eval().requires_grad_(False).to(device)

clip_models = []
if ViTB32 is True:
    clip_models.append(
        clip.load('ViT-B/32',
                  jit=False)[0].eval().requires_grad_(False).to(device))
if ViTB16 is True:
    clip_models.append(
        clip.load('ViT-B/16',
                  jit=False)[0].eval().requires_grad_(False).to(device))
if ViTL14 is True:
    clip_models.append(
        clip.load('ViT-L/14',
                  jit=False)[0].eval().requires_grad_(False).to(device))
if ViTL14_336 is True:
    clip_models.append(
        clip.load('ViT-L/14@336px',
                  jit=False)[0].eval().requires_grad_(False).to(device))
if RN50 is True:
    clip_models.append(
        clip.load('RN50',
                  jit=False)[0].eval().requires_grad_(False).to(device))
if RN50x4 is True:
    clip_models.append(
        clip.load('RN50x4',
                  jit=False)[0].eval().requires_grad_(False).to(device))
if RN50x16 is True:
    clip_models.append(
        clip.load('RN50x16',
                  jit=False)[0].eval().requires_grad_(False).to(device))
if RN50x64 is True:
    clip_models.append(
        clip.load('RN50x64',
                  jit=False)[0].eval().requires_grad_(False).to(device))
if RN101 is True:
    clip_models.append(
        clip.load('RN101',
                  jit=False)[0].eval().requires_grad_(False).to(device))

"""
if SLIPB16:
    SLIPB16model = SLIP_VITB16(ssl_mlp_dim=4096, ssl_emb_dim=256)
    if not os.path.exists(f'{model_path}/slip_base_100ep.pt'):
        #!wget https://dl.fbaipublicfiles.com/slip/slip_base_100ep.pt -P {model_path}
        urllib.request.urlretrieve(
            "https://dl.fbaipublicfiles.com/slip/slip_base_100ep.pt",
            model_path)
    sd = torch.load(f'{model_path}/slip_base_100ep.pt')
    real_sd = {}
    for k, v in sd['state_dict'].items():
        real_sd['.'.join(k.split('.')[1:])] = v
    del sd
    SLIPB16model.load_state_dict(real_sd)
    SLIPB16model.requires_grad_(False).eval().to(device)

    clip_models.append(SLIPB16model)

if SLIPL16:
    SLIPL16model = SLIP_VITL16(ssl_mlp_dim=4096, ssl_emb_dim=256)
    if not os.path.exists(f'{model_path}/slip_large_100ep.pt'):
        #!wget https://dl.fbaipublicfiles.com/slip/slip_large_100ep.pt -P {model_path}
        urllib.request.urlretrieve(
            "https://dl.fbaipublicfiles.com/slip/slip_large_100ep.pt",
            model_path)
    sd = torch.load(f'{model_path}/slip_large_100ep.pt')
    real_sd = {}
    for k, v in sd['state_dict'].items():
        real_sd['.'.join(k.split('.')[1:])] = v
    del sd
    SLIPL16model.load_state_dict(real_sd)
    SLIPL16model.requires_grad_(False).eval().to(device)

    clip_models.append(SLIPL16model)
"""
normalize = T.Normalize(mean=[0.48145466, 0.4578275, 0.40821073],
                        std=[0.26862954, 0.26130258, 0.27577711])
lpips_model = lpips.LPIPS(net='vgg').to(device)

#Get corrected sizes
side_x = (width_height[0] // 64) * 64
side_y = (width_height[1] // 64) * 64
if side_x != width_height[0] or side_y != width_height[1]:
    print(
        f'Changing output size to {side_x}x{side_y}. Dimensions must by multiples of 64.'
    )

#Update Model Settings
timestep_respacing = f'ddim{steps}'
diffusion_steps = (1000 // steps) * steps if steps < 1000 else steps
model_config.update({
    'timestep_respacing': timestep_respacing,
    'diffusion_steps': diffusion_steps,
})

#Make folder for batch
batchFolder = f'{outDirPath}/{batch_name}'
createPath(batchFolder)
"""###Animation Settings"""

#@markdown ####**Animation Mode:**
animation_mode = "None"  #@param['None', '2D', 'Video Input']
#@markdown *For animation, you probably want to turn `cutn_batches` to 1 to make it quicker.*

#@markdown ---

#@markdown ####**Video Input Settings:**
#video_init_path = "/content/training.mp4" #@param {type: 'string'}
#extract_nth_frame = 2 #@param {type:"number"}

if animation_mode == "Video Input":
    videoFramesFolder = f'/content/videoFrames'
    createPath(videoFramesFolder)
    print(f"Exporting Video Frames (1 every {extract_nth_frame})...")
    try:
        #!rm {videoFramesFolder}/*.jpg
        tempfileList = glob.glob(videoFramesFolder + '/*.jpg')
        for tempfilePath in tempfileList:
            os.remove(tempfilePath)
    except:
        print('')
    vf = f'"select=not(mod(n\,{extract_nth_frame}))"'
    subprocess.run([
        'ffmpeg', '-i', f'{video_init_path}', '-vf', f'{vf}', '-vsync', 'vfr',
        '-q:v', '2', '-loglevel', 'error', '-stats',
        f'{videoFramesFolder}/%04d.jpg'
    ],
                   stdout=subprocess.PIPE).stdout.decode('utf-8')

#@markdown ---

#@markdown ####**2D Animation Settings:**
#@markdown `zoom` is a multiplier of dimensions, 1 is no zoom.

#key_frames = True #@param {type:"boolean"}
#max_frames = 10000#@param {type:"number"}

if animation_mode == "Video Input":
    max_frames = len(glob(f'{videoFramesFolder}/*.jpg'))

#interp_spline = 'Linear' #Do not change, currently will not look good. param ['Linear','Quadratic','Cubic']{type:"string"}
#angle = "0:(0)"#@param {type:"string"}
#zoom = "0: (1), 10: (1.05)"#@param {type:"string"}
#translation_x = "0: (0)"#@param {type:"string"}
#translation_y = "0: (0)"#@param {type:"string"}

#@markdown ---

#@markdown ####**Coherency Settings:**
#@markdown `frame_scale` tries to guide the new frame to looking like the old one. A good default is 1500.
#frames_scale = 1500 #@param{type: 'integer'}
#@markdown `frame_skip_steps` will blur the previous frame - higher values will flicker less but struggle to add enough new detail to zoom into.
#frames_skip_steps = '60%' #@param ['40%', '50%', '60%', '70%', '80%'] {type: 'string'}


def parse_key_frames(string, prompt_parser=None):
    """Given a string representing frame numbers paired with parameter values at that frame,
    return a dictionary with the frame numbers as keys and the parameter values as the values.

    Parameters
    ----------
    string: string
        Frame numbers paired with parameter values at that frame number, in the format
        'framenumber1: (parametervalues1), framenumber2: (parametervalues2), ...'
    prompt_parser: function or None, optional
        If provided, prompt_parser will be applied to each string of parameter values.

    Returns
    -------
    dict
        Frame numbers as keys, parameter values at that frame number as values

    Raises
    ------
    RuntimeError
        If the input string does not match the expected format.

    Examples
    --------
    >>> parse_key_frames("10:(Apple: 1| Orange: 0), 20: (Apple: 0| Orange: 1| Peach: 1)")
    {10: 'Apple: 1| Orange: 0', 20: 'Apple: 0| Orange: 1| Peach: 1'}

    >>> parse_key_frames("10:(Apple: 1| Orange: 0), 20: (Apple: 0| Orange: 1| Peach: 1)", prompt_parser=lambda x: x.lower()))
    {10: 'apple: 1| orange: 0', 20: 'apple: 0| orange: 1| peach: 1'}
    """
    pattern = r'((?P<frame>[0-9]+):[\s]*[\(](?P<param>[\S\s]*?)[\)])'
    frames = dict()
    for match_object in re.finditer(pattern, string):
        frame = int(match_object.groupdict()['frame'])
        param = match_object.groupdict()['param']
        if prompt_parser:
            frames[frame] = prompt_parser(param)
        else:
            frames[frame] = param

    if frames == {} and len(string) != 0:
        raise RuntimeError('Key Frame string not correctly formatted')
    return frames


def get_inbetweens(key_frames, integer=False):
    """Given a dict with frame numbers as keys and a parameter value as values,
    return a pandas Series containing the value of the parameter at every frame from 0 to max_frames.
    Any values not provided in the input dict are calculated by linear interpolation between
    the values of the previous and next provided frames. If there is no previous provided frame, then
    the value is equal to the value of the next provided frame, or if there is no next provided frame,
    then the value is equal to the value of the previous provided frame. If no frames are provided,
    all frame values are NaN.

    Parameters
    ----------
    key_frames: dict
        A dict with integer frame numbers as keys and numerical values of a particular parameter as values.
    integer: Bool, optional
        If True, the values of the output series are converted to integers.
        Otherwise, the values are floats.

    Returns
    -------
    pd.Series
        A Series with length max_frames representing the parameter values for each frame.

    Examples
    --------
    >>> max_frames = 5
    >>> get_inbetweens({1: 5, 3: 6})
    0    5.0
    1    5.0
    2    5.5
    3    6.0
    4    6.0
    dtype: float64

    >>> get_inbetweens({1: 5, 3: 6}, integer=True)
    0    5
    1    5
    2    5
    3    6
    4    6
    dtype: int64
    """
    key_frame_series = pd.Series([np.nan for a in range(max_frames)])

    for i, value in key_frames.items():
        key_frame_series[i] = value
    key_frame_series = key_frame_series.astype(float)

    interp_method = interp_spline

    if interp_method == 'Cubic' and len(key_frames.items()) <= 3:
        interp_method = 'Quadratic'

    if interp_method == 'Quadratic' and len(key_frames.items()) <= 2:
        interp_method = 'Linear'

    key_frame_series[0] = key_frame_series[
        key_frame_series.first_valid_index()]
    key_frame_series[max_frames -
                     1] = key_frame_series[key_frame_series.last_valid_index()]
    # key_frame_series = key_frame_series.interpolate(method=intrp_method,order=1, limit_direction='both')
    key_frame_series = key_frame_series.interpolate(
        method=interp_method.lower(), limit_direction='both')
    if integer:
        return key_frame_series.astype(int)
    return key_frame_series


def split_prompts(prompts):
    prompt_series = pd.Series([np.nan for a in range(max_frames)])
    for i, prompt in prompts.items():
        prompt_series[i] = prompt
    # prompt_series = prompt_series.astype(str)
    prompt_series = prompt_series.ffill().bfill()
    return prompt_series


if key_frames:
    try:
        angle_series = get_inbetweens(parse_key_frames(angle))
    except RuntimeError as e:
        print("WARNING: You have selected to use key frames, but you have not "
              "formatted `angle` correctly for key frames.\n"
              "Attempting to interpret `angle` as "
              f'"0: ({angle})"\n'
              "Please read the instructions to find out how to use key frames "
              "correctly.\n")
        angle = f"0: ({angle})"
        angle_series = get_inbetweens(parse_key_frames(angle))

    try:
        zoom_series = get_inbetweens(parse_key_frames(zoom))
    except RuntimeError as e:
        print("WARNING: You have selected to use key frames, but you have not "
              "formatted `zoom` correctly for key frames.\n"
              "Attempting to interpret `zoom` as "
              f'"0: ({zoom})"\n'
              "Please read the instructions to find out how to use key frames "
              "correctly.\n")
        zoom = f"0: ({zoom})"
        zoom_series = get_inbetweens(parse_key_frames(zoom))

    try:
        translation_x_series = get_inbetweens(parse_key_frames(translation_x))
    except RuntimeError as e:
        print("WARNING: You have selected to use key frames, but you have not "
              "formatted `translation_x` correctly for key frames.\n"
              "Attempting to interpret `translation_x` as "
              f'"0: ({translation_x})"\n'
              "Please read the instructions to find out how to use key frames "
              "correctly.\n")
        translation_x = f"0: ({translation_x})"
        translation_x_series = get_inbetweens(parse_key_frames(translation_x))

    try:
        translation_y_series = get_inbetweens(parse_key_frames(translation_y))
    except RuntimeError as e:
        print("WARNING: You have selected to use key frames, but you have not "
              "formatted `translation_y` correctly for key frames.\n"
              "Attempting to interpret `translation_y` as "
              f'"0: ({translation_y})"\n'
              "Please read the instructions to find out how to use key frames "
              "correctly.\n")
        translation_y = f"0: ({translation_y})"
        translation_y_series = get_inbetweens(parse_key_frames(translation_y))

else:
    angle = float(angle)
    zoom = float(zoom)
    translation_x = float(translation_x)
    translation_y = float(translation_y)
"""### Extra Settings
 Partial Saves, Diffusion Sharpening, Advanced Settings, Cutn Scheduling
"""

#@markdown ####**Saving:**
#intermediate_saves = 0#@param{type: 'raw'}
if geninit:
    intermediate_saves = [
        (steps * geninitamount)
    ]  # Save a checkpoint at 20% for use as a later init image
intermediates_in_subfolder = True  #@param{type: 'boolean'}

if type(intermediate_saves) is not list:
    if intermediate_saves:
        steps_per_checkpoint = math.floor(
            (steps - skip_steps - 1) // (intermediate_saves + 1))
        steps_per_checkpoint = steps_per_checkpoint if steps_per_checkpoint > 0 else 1
        print(f'Will save every {steps_per_checkpoint} steps')
    else:
        steps_per_checkpoint = steps + 10
else:
    steps_per_checkpoint = None

if intermediate_saves and intermediates_in_subfolder is True:
    partialFolder = f'{batchFolder}/partials'
    createPath(partialFolder)


batch_size = 1


def move_files(start_num, end_num, old_folder, new_folder):
    for i in range(start_num, end_num):
        old_file = old_folder + f'/{batch_name}({batchNum})_{i:04}.png'
        new_file = new_folder + f'/{batch_name}({batchNum})_{i:04}.png'
        os.rename(old_file, new_file)

resume_run = False  #@param{type: 'boolean'}
run_to_resume = 'latest'  #@param{type: 'string'}
resume_from_frame = 'latest'  #@param{type: 'string'}
retain_overwritten_frames = False  #@param{type: 'boolean'}
if retain_overwritten_frames is True:
    retainFolder = f'{batchFolder}/retained'
    createPath(retainFolder)

skip_step_ratio = int(frames_skip_steps.rstrip("%")) / 100
calc_frames_skip_steps = math.floor(steps * skip_step_ratio)

if steps <= calc_frames_skip_steps:
    sys.exit("ERROR: You can't skip more steps than your total steps")

if resume_run:
    if run_to_resume == 'latest':
        try:
            batchNum
        except:
            batchNum = len(
                glob(f"{batchFolder}/{batch_name}(*)_settings.json")) - 1
    else:
        batchNum = int(run_to_resume)
    if resume_from_frame == 'latest':
        start_frame = len(
            glob(batchFolder + f"/{batch_name}({batchNum})_*.png"))
    else:
        start_frame = int(resume_from_frame) + 1
        if retain_overwritten_frames is True:
            existing_frames = len(
                glob(batchFolder + f"/{batch_name}({batchNum})_*.png"))
            frames_to_save = existing_frames - start_frame
            print(f'Moving {frames_to_save} frames to the Retained folder')
            move_files(start_frame, existing_frames, batchFolder, retainFolder)
else:
    start_frame = 0
    batchNum = len(glob(batchFolder + "/*.json"))
    while path.isfile(
            f"{batchFolder}/{batch_name}({batchNum})_settings.json"
    ) is True or path.isfile(
            f"{batchFolder}/{batch_name}-{batchNum}_settings.json") is True:
        batchNum += 1

print(f'Starting Run: {batch_name}({batchNum}) at frame {start_frame}')

if set_seed == 'random_seed':
    random.seed()
    seed = random.randint(0, 2**32)
    # print(f'Using seed: {seed}')
else:
    seed = int(set_seed)

print(f'Using seed {seed}')

# Leave this section alone, it takes all our settings and puts them in one variable dictionary
args = {
    'batchNum': batchNum,
    'prompts_series': split_prompts(text_prompts) if text_prompts else None,
    'image_prompts_series':
    split_prompts(image_prompts) if image_prompts else None,
    'seed': seed,
    'display_rate': display_rate,
    'n_batches': n_batches if animation_mode == 'None' else 1,
    'batch_size': batch_size,
    'batch_name': batch_name,
    'steps': steps,
    'sampling_mode': sampling_mode,
    'width_height': width_height,
    'clip_guidance_scale': clip_guidance_scale,
    'tv_scale': tv_scale,
    'range_scale': range_scale,
    'sat_scale': sat_scale,
    'cutn_batches': cutn_batches,
    'init_image': init_image,
    'init_scale': init_scale,
    'skip_steps': skip_steps,
    'sharpen_preset': sharpen_preset,
    'keep_unsharp': keep_unsharp,
    'side_x': side_x,
    'side_y': side_y,
    'timestep_respacing': timestep_respacing,
    'diffusion_steps': diffusion_steps,
    'animation_mode': animation_mode,
    'video_init_path': video_init_path,
    'extract_nth_frame': extract_nth_frame,
    'key_frames': key_frames,
    'max_frames': max_frames if animation_mode != "None" else 1,
    'interp_spline': interp_spline,
    'start_frame': start_frame,
    'angle': angle,
    'zoom': zoom,
    'translation_x': translation_x,
    'translation_y': translation_y,
    'angle_series': angle_series,
    'zoom_series': zoom_series,
    'translation_x_series': translation_x_series,
    'translation_y_series': translation_y_series,
    'frames_scale': frames_scale,
    'calc_frames_skip_steps': calc_frames_skip_steps,
    'skip_step_ratio': skip_step_ratio,
    'calc_frames_skip_steps': calc_frames_skip_steps,
    'text_prompts': text_prompts,
    'image_prompts': image_prompts,
    'cut_overview': eval(cut_overview),
    'cut_innercut': eval(cut_innercut),
    'cut_ic_pow': cut_ic_pow,
    'cut_ic_pow_final': cut_ic_pow_final,
    'cut_icgray_p': eval(cut_icgray_p),
    'intermediate_saves': intermediate_saves,
    'intermediates_in_subfolder': intermediates_in_subfolder,
    'steps_per_checkpoint': steps_per_checkpoint,
    'perlin_init': perlin_init,
    'perlin_mode': perlin_mode,
    'set_seed': set_seed,
    'eta': eta,
    'clamp_grad': clamp_grad,
    'clamp_max': clamp_max,
    'skip_augs': skip_augs,
    'randomize_class': randomize_class,
    'clip_denoised': clip_denoised,
    'fuzzy_prompt': fuzzy_prompt,
    'rand_mag': rand_mag,
    'stop_early': stop_early,
}

args = SimpleNamespace(**args)

if cl_args.gobiginit == None:
    model, diffusion = create_model_and_diffusion(**model_config)
    print(f'Prepping model: {model_path}/{diffusion_model}.pt')
    model.load_state_dict(
        torch.load(f'{model_path}/{diffusion_model}.pt', map_location='cpu'))
    model.requires_grad_(False).eval().to(device)
    for name, param in model.named_parameters():
        if 'qkv' in name or 'norm' in name or 'proj' in name:
            param.requires_grad_()
    if model_config['use_fp16']:
        model.convert_to_fp16()
    gc.collect()
    torch.cuda.empty_cache()

# FUNCTIONS FOR GO BIG MODE
#gobig_scale = 2 # how many multiples of the original resolution. Eventually make this configurable
slices_todo = (gobig_scale * gobig_scale) + 1 #we want 5 total slices for a 2x increase, 4 to match the total pixel increase + 1 to cover overlap
#overlap = ((side_x * gobig_scale) / slices_todo) / slices_todo
# Input is an image, return image with mask added as an alpha channel
def addalpha(im, mask):
    imr, img, imb, ima = im.split()
    mmr, mmg, mmb, mma = mask.split()
    im = Image.merge('RGBA', [imr, img, imb, mma]) # we want the RGB from the original, but the transparency from the mask
    return(im)

# take a source image and layer in the slices on top
def mergeimgs(source, slices):
    global slices_todo
    source.convert("RGBA")
    width, height = source.size
    if gobig_horizontal == True:
        slice_height = int(height / slices_todo)
        slice_height = 64 * math.floor(slice_height / 64) #round slice height down to the nearest 64
        paste_y = 0
        for slice in slices:
            source.alpha_composite(slice, (0,paste_y))
            paste_y += slice_height
    if gobig_vertical == True:
        slice_width, slice_height = slices[0].size
        slice_width -= 64 #remove overlap
        print(f'slice_width for merge is {slice_width}')
        #slice_width = int(width / slices_todo)
        #slice_width = 64 * math.floor(slice_width / 64) #round slice width down to the nearest 64
        #remainder = width - (slice_width * slices_todo)
        #while remainder > 0:
        #    slices_todo += 1
        #    remainder = remainder - slice_width
        paste_x = 0
        for slice in slices:
            source.alpha_composite(slice, (paste_x,0))
            paste_x += slice_width
    return source

# Slices an image into the configured number of chunks. Overlap is currently 64px but should become dynamic
def slice(source):
    global slices_todo
    width, height = source.size
    overlap = 64 #int(height / slices_todo / 4)
    if gobig_horizontal == True:
        slice_height = int(height / slices_todo)
        slice_height = 64 * math.floor(slice_height / 64) #round slice height down to the nearest 64
        slice_height += overlap
        i = 0
        slices = []
        x = 0
        y = 0
        bottomy = slice_height
        while i < slices_todo:
            slices.append(source.crop((x, y, width, bottomy)))
            y += slice_height - overlap
            bottomy = y + slice_height
            i += 1
    if gobig_vertical == True:
        slice_width = int(width / slices_todo)
        slice_width = 64 * math.floor(slice_width / 64) #round slice width down to the nearest 64
        remainder = width - (slice_width * slices_todo)
        while remainder > 0:
            slices_todo += 1
            remainder = remainder - slice_width
        slice_width += overlap
        print(f'slice_width is {slice_width}')
        i = 0
        slices = []
        x = 0
        y = 0
        edgex = slice_width
        while i < slices_todo:
            slices.append(source.crop((x, y, edgex, height)))
            x += slice_width - overlap
            edgex = x + slice_width
            i += 1
    return (slices)

# FINALLY DO THE RUN
try:
    if (gui):
        print("running with gui")
        prdgui.run_gui(do_run, side_x, side_y)
    else:
        if cl_args.gobiginit is not None: # skip do_run if a gobig init image was provided
            if cl_args.cuda != '0':
                progress_image = (f'progress{cl_args.cuda}.png')
            else:
                progress_image = 'progress.png'
            shutil.copy(init_image, progress_image)
        else:
            do_run()
        if letsgobig:
            current_time = datetime.now().strftime('%y%m%d-%H%M%S_%f')
            # Resize initial progress.png to new size
            if cl_args.cuda != '0': #handle if a different GPU is in use
                progress_image = (f'progress{cl_args.cuda}.png')
                slice_image = (f'slice{cl_args.cuda}.png')
                original_output_image = (f'{batchFolder}/{batch_name}_original_output_{cl_args.cuda}_{current_time}.png')
                final_output_image = (f'{batchFolder}/{batch_name}_final_output_{cl_args.cuda}_{current_time}.png')
            else:
                progress_image = 'progress.png'
                slice_image = 'slice.png'
                original_output_image = (f'{batchFolder}/{batch_name}_original_output_{current_time}.png')
                final_output_image = (f'{batchFolder}/{batch_name}_final_output_{current_time}.png')
            input_image = Image.open(progress_image).convert('RGBA')
            input_image.save(original_output_image)
            print(f'cl_args.gobiginit_scaled is {cl_args.gobiginit_scaled}')
            print(f'size of input_image is {input_image.size}')
            print(f'side_x and side_y are {side_x} and {side_y}')
            if cl_args.gobiginit_scaled == False:
                reside_x = side_x * gobig_scale
                reside_y = side_y * gobig_scale
                source_image = input_image.resize((reside_x, reside_y), Image.LANCZOS)
            else:
                source_image = Image.open(progress_image).convert('RGBA')

            input_image.close()
            # Slice source_image into overlapping slices
            slices = slice(source_image)
            # Run PRD again for each slice, with init image paramaters, etc.
            i = 1 # just to number the slices as they save
            betterslices = []
            for chunk in slices:
                # Reset underlying systems for another run
                print(f'Rendering slice {i} of {slices_todo} ...')
                model, diffusion = create_model_and_diffusion(**model_config)
                model.load_state_dict(
                    torch.load(f'{model_path}/{diffusion_model}.pt', map_location='cpu'))
                model.requires_grad_(False).eval().to(device)
                for name, param in model.named_parameters():
                    if 'qkv' in name or 'norm' in name or 'proj' in name:
                        param.requires_grad_()
                if model_config['use_fp16']:
                    model.convert_to_fp16()
                gc.collect()
                torch.cuda.empty_cache()
                #no do the next run
                chunk.save(slice_image)
                args.init_image = slice_image
                args.skip_steps = int(steps * .6)
                args.side_x, args.side_y = chunk.size
                side_x, side_y = chunk.size
                fix_brightness_contrast = False
                do_run()
                print(f'Finished run, grabbing {progress_image} and adding it to betterslices.')
                resultslice = Image.open(progress_image).convert('RGBA')
                betterslices.append(resultslice.copy())
                resultslice.close()
                i += 1
            # generate an alpha mask
            # starts at full opacity * initial_value
            # decrements opacity by gradient * x / width
            if gobig_vertical:
                alpha_gradient = Image.new('L', (args.side_x, 1), color=0xFF)
                a = 0
                for x in range(args.side_x):
                    a +=4 # add 4 to alpha at each pixel, to give us a 64 pixel overlap gradient
                    if a < 255:
                        alpha_gradient.putpixel((x, 0), a)
                    else:
                        alpha_gradient.putpixel((x, 0), 255)
                alpha = alpha_gradient.resize(betterslices[0].size, Image.BICUBIC)
            # For each slice, use addalpha to add an alpha mask
            if gobig_horizontal:
                alpha_gradient = Image.new('L', (1, args.side_y), color=0xFF)
                a = 0
                for x in range(args.side_y):
                    a +=4 # add 4 to alpha at each pixel, to give us a 64 pixel overlap gradient
                    if a < 255:
                        alpha_gradient.putpixel((0, x), a)
                    else:
                        alpha_gradient.putpixel((0, x), 255)
                alpha = alpha_gradient.resize(betterslices[0].size, Image.BICUBIC)
            #add the generated alpha channel to a mask image
            mask = Image.new('RGBA', (args.side_x, args.side_y), color=0)
            mask.putalpha(alpha)
            i = 1 # start at 1 in the list instead of 0, because we don't need/want a mask on the first (0) image
            while i < slices_todo:
                betterslices[i] = addalpha(betterslices[i], mask)
                i += 1
            # Once we have all our images, mergeimgs back onto source.png, then save
            final_output = mergeimgs(source_image, betterslices)
            final_output.save(final_output_image)
            print(f'\n\nGO BIG is complete!\n\n ***** NOTE *****\nYour output is saved as {final_output_image}!')

except KeyboardInterrupt:
    pass
finally:
    print('Seed used:', seed)
    gc.collect()
    torch.cuda.empty_cache()
"""# 5. Create the video"""

# @title ### **Create video**
#@markdown Video file will save in the same folder as your images.

skip_video_for_run_all = True  #@param {type: 'boolean'}

if skip_video_for_run_all == False:
    # import subprocess in case this cell is run without the above cells
    import subprocess
    from base64 import b64encode

    latest_run = batchNum

    folder = batch_name  #@param
    run = latest_run  #@param
    final_frame = 'final_frame'

    init_frame = 1  #@param {type:"number"} This is the frame where the video will start
    last_frame = final_frame  #@param {type:"number"} You can change i to the number of the last frame you want to generate. It will raise an error if that number of frames does not exist.
    fps = 12  #@param {type:"number"}
    view_video_in_cell = False  #@param {type: 'boolean'}

    frames = []
    # tqdm.write('Generating video...')

    if last_frame == 'final_frame':
        last_frame = len(glob(batchFolder + f"/{folder}({run})_*.png"))
        print(f'Total frames: {last_frame}')

    image_path = f"{outDirPath}/{folder}/{folder}({run})_%04d.png"
    filepath = f"{outDirPath}/{folder}/{folder}({run}).mp4"

    cmd = [
        'ffmpeg', '-y', '-vcodec', 'png', '-r',
        str(fps), '-start_number',
        str(init_frame), '-i', image_path, '-frames:v',
        str(last_frame + 1), '-c:v', 'libx264', '-vf', f'fps={fps}',
        '-pix_fmt', 'yuv420p', '-crf', '17', '-preset', 'very ', filepath
    ]

    process = subprocess.Popen(cmd,
                               cwd=f'{batchFolder}',
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        print(stderr)
        raise RuntimeError(stderr)
    else:
        print("The video is ready")

    if view_video_in_cell:
        mp4 = open(filepath, 'rb').read()
        data_url = "data:video/mp4;base64," + b64encode(mp4).decode()
        display.HTML("""
      <video width=400 controls>
            <source src="%s" type="video/mp4">
      </video>
      """ % data_url)
