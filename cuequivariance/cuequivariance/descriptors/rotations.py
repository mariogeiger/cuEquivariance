# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from typing import *

import numpy as np

import cuequivariance as cue
from cuequivariance import segmented_tensor_product as stp


def fixed_axis_angle_rotation(
    irreps: cue.Irreps, axis: np.ndarray, angle: float
) -> cue.EquivariantTensorProduct:
    """
    subsrcipts: ``input[u],output[u]``

    Rotation by a known angle around a known axis
    """
    assert irreps.irrep_class in [cue.SO3, cue.O3]

    d = stp.SegmentedTensorProduct.from_subscripts("iu_ju+ij")

    for mul, ir in irreps:
        # Note the transpose
        d.add_path(
            None,
            None,
            c=ir.rotation(axis, angle).T,
            dims={"u": mul},
        )

    d = d.flatten_coefficient_modes()
    return cue.EquivariantTensorProduct(d, [irreps, irreps], layout=cue.ir_mul)


def yxy_rotation(
    irreps: cue.Irreps, lmax: Optional[int] = None
) -> cue.EquivariantTensorProduct:
    """
    subsrcipts: ``gamma[],beta[],alpha[],input[u],output[u]``

    The composition of three rotations:

    - Rotation around the y-axis by angle gamma
    - followed by rotation around the x-axis by angle beta
    - followed by rotation around the y-axis by angle alpha

    The angles are encoded in the following way::

        encoding(x) = [cos(x * l), cos(x * (l - 1)), ..., cos(x), 1, sin(x), sin(2 * x), ..., sin(l * x)]

    where l is the maximum L in the input and output irreps.
    """
    cbio = xy_rotation(irreps, lmax).d  # gamma, beta, input, A
    aio = y_rotation(irreps, lmax).d  # alpha, A, output
    cbiao = stp.dot(cbio, aio, (3, 1))  # gamma, beta, input, alpha, output
    cbaio = cbiao.move_operand(2, 3)  # gamma, beta, alpha, input, output
    return cue.EquivariantTensorProduct(
        cbaio,
        [
            irreps.new_scalars(cbaio.operands[0].size),
            irreps.new_scalars(cbaio.operands[1].size),
            irreps.new_scalars(cbaio.operands[2].size),
            irreps,
            irreps,
        ],
        layout=cue.ir_mul,
    )


def xy_rotation(
    irreps: cue.Irreps, lmax: Optional[int] = None
) -> cue.EquivariantTensorProduct:
    """
    subsrcipts: ``gamma[],beta[],input[u],output[u]``

    Rotation around the y-axis followed by rotation around the x-axis
    """
    cio = y_rotation(irreps, lmax).d  # gamma, input, A
    bio = x_rotation(irreps, lmax).d  # beta, A, output
    cibo = stp.dot(cio, bio, (2, 1))  # gamma, input, beta, output
    cbio = cibo.move_operand(1, 2)  # gamma, beta, input, output
    return cue.EquivariantTensorProduct(
        cbio,
        [
            irreps.new_scalars(cbio.operands[0].size),
            irreps.new_scalars(cbio.operands[1].size),
            irreps,
            irreps,
        ],
        layout=cue.ir_mul,
    )


def yx_rotation(
    irreps: cue.Irreps, lmax: Optional[int] = None
) -> cue.EquivariantTensorProduct:
    """
    subsrcipts: ``phi[],theta[],input[u],output[u]``

    Rotation around the x-axis followed by rotation around the y-axis
    """
    cio = x_rotation(irreps, lmax).d
    bio = y_rotation(irreps, lmax).d
    cibo = stp.dot(cio, bio, (2, 1))
    cbio = cibo.move_operand(1, 2)
    return cue.EquivariantTensorProduct(
        cbio,
        [
            irreps.new_scalars(cbio.operands[0].size),
            irreps.new_scalars(cbio.operands[1].size),
            irreps,
            irreps,
        ],
        layout=cue.ir_mul,
    )


def y_rotation(
    irreps: cue.Irreps, lmax: Optional[int] = None
) -> cue.EquivariantTensorProduct:
    """
    subsrcipts: ``phi[],input[u],output[u]``

    Rotation around the y-axis by angle gamma

    The angle is encoded in the following way::

        encoding(x) = [cos(x * l), cos(x * (l - 1)), ..., cos(x), 1, sin(x), sin(2 * x), ..., sin(l * x)]

    where l is the maximum L in the input and output irreps.
    """
    assert irreps.irrep_class in [cue.SO3, cue.O3]

    if lmax is None:
        lmax = max(ir.l for _, ir in irreps)

    d = stp.SegmentedTensorProduct.from_subscripts("i_ju_ku+ijk")
    phc = d.add_segment(
        0, (lmax,)
    )  # cos(th * lmax), cos(th * (lmax - 1)), ..., cos(th)
    ph1 = d.add_segment(0, (1,))  # 1
    phs = d.add_segment(0, (lmax,))  # sin(th), sin(2 * th), ..., sin(lmax * th)

    for mul, ir in irreps:
        d.add_segment(1, (ir.l, mul))
        d.add_segment(1, (1, mul))
        d.add_segment(1, (ir.l, mul))
        sup = d.add_segment(2, (ir.l, mul))
        smi = d.add_segment(2, (1, mul))
        slo = d.add_segment(2, (ir.l, mul))

        l = ir.l

        d.add_path(ph1, smi, smi, c=np.ones((1, 1, 1)))

        c = np.zeros((lmax, l, l))
        for i in range(l):
            c[lmax - l + i, i, i] = 1
        d.add_path(phc, sup, sup, c=c)

        c = np.zeros((lmax, l, l))
        for i in range(l):
            c[l - 1 - i, l - 1 - i, i] = 1
        d.add_path(phs, slo, sup, c=c)

        c = np.zeros((lmax, l, l))
        for i in range(l):
            c[l - 1 - i, i, l - 1 - i] = -1
        d.add_path(phs, sup, slo, c=c)

        c = np.zeros((lmax, l, l))
        for i in range(l):
            c[lmax - l + i, l - 1 - i, l - 1 - i] = 1
        d.add_path(phc, slo, slo, c=c)

    d = d.flatten_coefficient_modes()
    return cue.EquivariantTensorProduct(
        d, [irreps.new_scalars(d.operands[0].size), irreps, irreps], layout=cue.ir_mul
    )


def x_rotation(
    irreps: cue.Irreps, lmax: Optional[int] = None
) -> cue.EquivariantTensorProduct:
    """
    subsrcipts: ``phi[],input[u],output[u]``

    Rotation around the x-axis by angle beta

    The angle is encoded in the following way::

        encoding(x) = [cos(x * l), cos(x * (l - 1)), ..., cos(x), 1, sin(x), sin(2 * x), ..., sin(l * x)]

    where l is the maximum L in the input and output irreps.
    """
    assert irreps.irrep_class in [cue.SO3, cue.O3]

    dy = y_rotation(irreps, lmax).d
    dz90 = fixed_axis_angle_rotation(irreps, np.array([0.0, 0.0, 1.0]), np.pi / 2.0).d
    d = stp.dot(stp.dot(dy, dz90, (1, 1)), dz90, (1, 1))

    return cue.EquivariantTensorProduct(
        d, [irreps.new_scalars(d.operands[0].size), irreps, irreps], layout=cue.ir_mul
    )


def inversion(irreps: cue.Irreps) -> cue.EquivariantTensorProduct:
    """
    subsrcipts: ``input[u],output[u]``
    """
    d = stp.SegmentedTensorProduct.from_subscripts("iu_ju+ji")
    for mul, ir in irreps:
        assert len(ir.H) == 1
        H = ir.H[0]
        assert np.allclose(H @ H, np.eye(ir.dim), atol=1e-6)
        d.add_path(None, None, c=H, dims={"u": mul})
    d = d.flatten_coefficient_modes()
    return cue.EquivariantTensorProduct(d, [irreps, irreps], layout=cue.ir_mul)
