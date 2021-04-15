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

"""Stacking task."""

import numpy as np
import pybullet as p

from ravens import utils
from ravens.tasks.task import Task


class StackBlockVerticalSquare(Task):
  """Stacking task."""

  def __init__(self):
    super().__init__()
    self.max_steps = 12
    self.pos_eps = 0.01
    self.rot_eps = np.deg2rad(180)

  def reset(self, env):
    super().reset(env)

    # Add base.
    base_size = (0.05 * (5./4.), 0.15 * (5./4.), 0.005 * (5./4.))
    base_urdf = 'assets/stacking/stand.urdf'
    base_pose = self.get_random_pose(env, base_size)
    env.add_object(base_urdf, base_pose, 'fixed')

    # Block colors.
    colors = [
        utils.COLORS['purple'], utils.COLORS['blue'], utils.COLORS['green'],
        utils.COLORS['yellow'], utils.COLORS['orange'], utils.COLORS['red']
    ]

    # Add blocks.
    objs = []
    # sym = np.pi / 2
    goal_height = 4
    block_size = (0.05, 0.05, 0.05)
    block_urdf = 'assets/stacking/block.urdf'
    for i in range(goal_height):
      block_pose = self.get_random_pose(env, block_size)
      block_id = env.add_object(block_urdf, block_pose)
      p.changeVisualShape(block_id, -1, rgbaColor=colors[i] + [1])
      objs.append((block_id, (np.pi / 2, None)))

    # Associate placement locations for goals.
    place_pos = [(0, -0.05, 0.03), (0, 0, 0.03),
                 (0, -0.05, 0.08), (0, 0, 0.08)]
    targs = [(utils.apply(base_pose, i), base_pose[1]) for i in place_pos]

    # Goal: blocks are stacked in a tower (green, blue, purple, yellow, orange, red).
    # self.goals.append((objs[:], np.ones((6, 6)), targs[:],
    #                   False, True, 'pose', None, 1))
    for i in range(goal_height):
      self.goals.append(([objs[i]], np.ones((1, 1)), [targs[i]],
                        False, True, 'pose', None, 1 / goal_height))