# coding=utf-8
# Copyright 2020 The Google Research Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Transport module."""


import numpy as np
from ravens import utils
from ravens.models.resnet import ResNet43_8s

from ravens.models.efficientnet import EfficientNetB0
from ravens.models.efficientnet import EfficientNet
from ravens.models.efficientnet import block
from ravens.models.efficientnet import CONV_KERNEL_INITIALIZER
import supernet_macro

from tensorflow.keras import layers
import tensorflow as tf
import tensorflow_addons as tfa
import transformer as transformer


class Transport:
  """Transport module."""

  def __init__(self, in_shape, n_rotations, crop_size, preprocess, model_name='resnet'):
    """Transport module for placing.

    Args:
      in_shape: shape of input image.
      n_rotations: number of rotations of convolving kernel.
      crop_size: crop size around pick argmax used as convolving kernel.
      preprocess: function to preprocess input images.
    """
    self.iters = 0
    self.n_rotations = n_rotations
    self.crop_size = crop_size  # crop size must be N*16 (e.g. 96)
    self.preprocess = preprocess
    self.model_name = model_name

    self.pad_size = int(self.crop_size / 2)
    self.padding = np.zeros((3, 2), dtype=int)
    self.padding[:2, :] = self.pad_size

    in_shape = np.array(in_shape)
    in_shape[0:2] += self.pad_size * 2
    in_shape = tuple(in_shape)

    # Crop before network (default for Transporters in CoRL submission).
    # kernel_shape = (self.crop_size, self.crop_size, in_shape[2])

    if not hasattr(self, 'output_dim'):
      self.output_dim = 3
    if not hasattr(self, 'kernel_dim'):
      self.kernel_dim = 3

    # 2 fully convolutional ResNets with 57 layers and 16-stride
    if model_name == 'resnet':
      in0, out0 = ResNet43_8s(in_shape, self.output_dim, prefix='s0_')
      in1, out1 = ResNet43_8s(in_shape, self.kernel_dim, prefix='s1_')
      self.model = tf.keras.Model(inputs=[in0, in1], outputs=[out0, out1])
    elif model_name == 'supernet':
      # TODO make the supernet class and call it
      build_supernet()

      

    elif model_name == 'efficientnet':
      print('in_shape: ' + str(in_shape))
      enet = EfficientNetB0(include_top=False, pooling=None, input_shape=in_shape, weights=None)
      in0 = enet.input
      y = tf.keras.layers.UpSampling2D(
          size=(4, 4), interpolation='bilinear', name='upsample_4')(
              enet.output)
      enet1 = EfficientNetB0(include_top=False, pooling=None, input_shape=in_shape, weights=None)
      for layer in enet1.layers:
          # rename all layers in the second model so there are no duplicate layer names
          layer._name = layer.name + str("_1")
      in1 = enet1.input
      z = tf.keras.layers.UpSampling2D(
          size=(4, 4), interpolation='bilinear', name='upsample_4_1')(
              enet1.output)
      bn_axis = 3 if tf.keras.backend.image_data_format() == 'channels_last' else 1
      name = 'out0'
      x = layers.Conv2D(
          1280,
          1,
          padding='same',
          use_bias=False,
          kernel_initializer=CONV_KERNEL_INITIALIZER,
          name=name + 'out_conv')(y)
      x = layers.BatchNormalization(axis=bn_axis, name=name + 'expand_bn')(x)
      x = layers.Activation('swish', name=name + 'expand_activation')(x)
      out0 = layers.Conv2D(
          self.output_dim,
          1,
          padding='same',
          use_bias=False,
          kernel_initializer=CONV_KERNEL_INITIALIZER,
          name='out_conv_1')(x)
      name = 'out1'
      x = layers.Conv2D(
          1280,
          1,
          padding='same',
          use_bias=False,
          kernel_initializer=CONV_KERNEL_INITIALIZER,
          name=name + 'out_conv')(z)
      x = layers.BatchNormalization(axis=bn_axis, name=name + 'expand_bn')(x)
      x = layers.Activation('swish', name=name + 'expand_activation')(x)
      out1 = layers.Conv2D(
          self.kernel_dim,
          1,
          padding='same',
          use_bias=False,
          kernel_initializer=CONV_KERNEL_INITIALIZER,
          name='out_conv')(x)
      # print(out1.layers[0].name)
      # print(out1.layers[-1].name)
      # self.model = tf.keras.Model(inputs=[out0.layers[0], out1.layers[0]], outputs=[out0, out1])
      # self.model = tf.keras.Model(inputs=[, out1.layers[0]], outputs=[out0.layers[-1], out1.layers[-1]])
      # in0, out0 = EfficientNetB0(include_top=False)
      # in1, out1 = EfficientNetB0(include_top=False)
      self.model = tf.keras.Model(inputs=[in0, in1], outputs=[out0, out1])
    elif model_name == 'efficientnet_merged':
      print('in_shape: ' + str(in_shape))
      enet = EfficientNetB0(include_top=False, pooling=None, input_shape=in_shape, weights=None)
      in0 = enet.input
      y = tf.keras.layers.UpSampling2D(
          size=(4, 4), interpolation='bilinear', name='upsample_4')(
              enet.output)
      bn_axis = 3 if tf.keras.backend.image_data_format() == 'channels_last' else 1
      name = 'out0'
      x = layers.Conv2D(
          1280,
          1,
          padding='same',
          use_bias=False,
          kernel_initializer=CONV_KERNEL_INITIALIZER,
          name=name + 'out_conv')(y)
      x = layers.BatchNormalization(axis=bn_axis, name=name + 'expand_bn')(x)
      x = layers.Activation('swish', name=name + 'expand_activation')(x)
      out0 = layers.Conv2D(
          self.output_dim,
          1,
          padding='same',
          use_bias=False,
          kernel_initializer=CONV_KERNEL_INITIALIZER,
          name='out_conv_1')(x)
      name = 'out1'
      x = layers.Conv2D(
          1280,
          1,
          padding='same',
          use_bias=False,
          kernel_initializer=CONV_KERNEL_INITIALIZER,
          name=name + 'out_conv')(y)
      x = layers.BatchNormalization(axis=bn_axis, name=name + 'expand_bn')(x)
      x = layers.Activation('swish', name=name + 'expand_activation')(x)
      out1 = layers.Conv2D(
          self.kernel_dim,
          1,
          padding='same',
          use_bias=False,
          kernel_initializer=CONV_KERNEL_INITIALIZER,
          name='out_conv')(x)
      # print(out1.layers[0].name)
      # print(out1.layers[-1].name)
      # self.model = tf.keras.Model(inputs=[out0.layers[0], out1.layers[0]], outputs=[out0, out1])
      # self.model = tf.keras.Model(inputs=[, out1.layers[0]], outputs=[out0.layers[-1], out1.layers[-1]])
      # in0, out0 = EfficientNetB0(include_top=False)
      # in1, out1 = EfficientNetB0(include_top=False)
      self.model = tf.keras.Model(inputs=[in0], outputs=[out0, out1])
    elif model_name == 'vit':
      # TODO(ahundt) make a compilable model, deal with dimension ordering, bhwc vs bchw
      self.model = ViT(image_size=in_shape, num_classes=1)
    else:
      raise NotImplementedError('model_name not implemented: ' + str(model_name))
      # self.model.compile(run_eagerly=True)
    self.optim = tf.keras.optimizers.Adam(learning_rate=1e-4)
    self.metric = tf.keras.metrics.Mean(name='loss_transport')

    # if not self.six_dof:
    #   in0, out0 = ResNet43_8s(in_shape, output_dim, prefix="s0_")
    #   if self.crop_bef_q:
    #     # Passing in kernels: (64,64,6) --> (64,64,3)
    #     in1, out1 = ResNet43_8s(kernel_shape, kernel_dim, prefix="s1_")
    #   else:
    #     # Passing in original images: (384,224,6) --> (394,224,3)
    #     in1, out1 = ResNet43_8s(in_shape, output_dim, prefix="s1_")
    # else:
    #   in0, out0 = ResNet43_8s(in_shape, output_dim, prefix="s0_")
    #   # early cutoff just so it all fits on GPU.
    #   in1, out1 = ResNet43_8s(
    #       kernel_shape, kernel_dim, prefix="s1_", cutoff_early=True)

  # def set_bounds_pixel_size(self, bounds, pixel_size):
  #   self.bounds = bounds
  #   self.pixel_size = pixel_size

  def correlate(self, in0, in1, softmax):
    """Correlate two input tensors."""
    output = tf.nn.convolution(in0, in1, data_format='NHWC')
    if softmax:
      output_shape = output.shape
      output = tf.reshape(output, (1, np.prod(output.shape)))
      output = tf.nn.softmax(output)
      output = np.float32(output).reshape(output_shape[1:])
    return output

  def forward(self, in_img, p, softmax=True):
    """Forward pass."""
    img_unprocessed = np.pad(in_img, self.padding, mode='constant')
    input_data = self.preprocess(img_unprocessed.copy())
    in_shape = (1,) + input_data.shape
    # print('in_shape: ' + str(in_shape))
    input_data = input_data.reshape(in_shape)
    in_tensor = tf.convert_to_tensor(input_data, dtype=tf.float32)

    # Rotate crop.
    pivot = np.array([p[1], p[0]]) + self.pad_size
    rvecs = self.get_se2(self.n_rotations, pivot)

    # Crop before network (default for Transporters in CoRL submission).
    # crop = tf.convert_to_tensor(input_data.copy(), dtype=tf.float32)
    # crop = tf.repeat(crop, repeats=self.n_rotations, axis=0)
    # crop = tfa.image.transform(crop, rvecs, interpolation="NEAREST")
    # crop = crop[:, p[0]:(p[0] + self.crop_size),
    #             p[1]:(p[1] + self.crop_size), :]
    # logits, kernel_raw = self.model([in_tensor, crop])

    # Crop after network (for receptive field, and more elegant).
    if self.model_name == 'efficientnet_merged':
      logits, crop = self.model([in_tensor])
    else:
      logits, crop = self.model([in_tensor, in_tensor])
    # crop = tf.identity(kernel_bef_crop)
    crop = tf.repeat(crop, repeats=self.n_rotations, axis=0)
    crop = tfa.image.transform(crop, rvecs, interpolation='NEAREST')
    kernel_raw = crop[:, p[0]:(p[0] + self.crop_size),
                      p[1]:(p[1] + self.crop_size), :]

    # Obtain kernels for cross-convolution.
    kernel_paddings = tf.constant([[0, 0], [0, 1], [0, 1], [0, 0]])
    kernel = tf.pad(kernel_raw, kernel_paddings, mode='CONSTANT')
    kernel = tf.transpose(kernel, [1, 2, 3, 0])

    return self.correlate(logits, kernel, softmax)

  def train(self, in_img, p, q, theta, backprop=True):
    """Transport pixel p to pixel q.

    Args:
      in_img: input image.
      p: pixel (y, x)
      q: pixel (y, x)
      theta: rotation label in radians.
      backprop: True if backpropagating gradients.

    Returns:
      loss: training loss.
    """

    self.metric.reset_states()
    with tf.GradientTape() as tape:
      output = self.forward(in_img, p, softmax=False)

      itheta = theta / (2 * np.pi / self.n_rotations)
      itheta = np.int32(np.round(itheta)) % self.n_rotations

      # Get one-hot pixel label map.
      label_size = in_img.shape[:2] + (self.n_rotations,)
      label = np.zeros(label_size)
      label[q[0], q[1], itheta] = 1

      # Get loss.
      label = label.reshape(1, np.prod(label.shape))
      label = tf.convert_to_tensor(label, dtype=tf.float32)
      output = tf.reshape(output, (1, np.prod(output.shape)))
      loss = tf.nn.softmax_cross_entropy_with_logits(label, output)
      loss = tf.reduce_mean(loss)

      if backprop:
        train_vars = self.model.trainable_variables
        grad = tape.gradient(loss, train_vars)
        self.optim.apply_gradients(zip(grad, train_vars))
        self.metric(loss)

    self.iters += 1
    return np.float32(loss)

  def get_se2(self, n_rotations, pivot):
    """Get SE2 rotations discretized into n_rotations angles counter-clockwise."""
    rvecs = []
    for i in range(n_rotations):
      theta = i * 2 * np.pi / n_rotations
      rmat = utils.get_image_transform(theta, (0, 0), pivot)
      rvec = rmat.reshape(-1)[:-1]
      rvecs.append(rvec)
    return np.array(rvecs, dtype=np.float32)

  def save(self, fname):
    self.model.save(fname)

  def load(self, fname):
    self.model.load_weights(fname)
