# This file is part of the pyMOR project (http://www.pymor.org).
# Copyright 2013-2017 pyMOR developers and contributors. All rights reserved.
# License: BSD 2-Clause License (http://opensource.org/licenses/BSD-2-Clause)

import numpy as np

from pymor.algorithms.pod import pod
from pymor.algorithms.timestepping import ExplicitEulerTimeStepper
from pymor.discretizations.basic import InstationaryDiscretization
from pymor.grids.oned import OnedGrid
from pymor.gui.visualizers import OnedVisualizer
from pymor.operators.constructions import VectorFunctional, LincombOperator
from pymor.parameters.functionals import ProjectionParameterFunctional
from pymor.parameters.spaces import CubicParameterSpace
from pymor.reductors.basic import GenericRBReductor

# import wrapped classes
from wrapper import WrappedDiffusionOperator


def discretize(n, nt, blocks):
    h = 1. / blocks
    ops = [WrappedDiffusionOperator.create(n, h * i, h * (i + 1)) for i in range(blocks)]
    pfs = [ProjectionParameterFunctional('diffusion_coefficients', (blocks,), (i,)) for i in range(blocks)]
    operator = LincombOperator(ops, pfs)

    initial_data = operator.source.zeros()

    # use data property of WrappedVector to setup rhs
    # note that we cannot use the data property of ListVectorArray,
    # since ListVectorArray will always return a copy
    rhs_vec = operator.range.zeros()
    rhs_data = rhs_vec._list[0].to_numpy()
    rhs_data[:] = np.ones(len(rhs_data))
    rhs_data[0] = 0
    rhs_data[len(rhs_data) - 1] = 0
    rhs = VectorFunctional(rhs_vec)

    # hack together a visualizer ...
    grid = OnedGrid(domain=(0, 1), num_intervals=n)
    visualizer = OnedVisualizer(grid)

    time_stepper = ExplicitEulerTimeStepper(nt)
    parameter_space = CubicParameterSpace(operator.parameter_type, 0.1, 1)

    d = InstationaryDiscretization(T=1e-0, operator=operator, rhs=rhs, initial_data=initial_data,
                                   time_stepper=time_stepper, num_values=20, parameter_space=parameter_space,
                                   visualizer=visualizer, name='C++-Discretization', cache_region=None)
    return d


# discretize
d = discretize(50, 10000, 4)

# generate solution snapshots
snapshots = d.solution_space.empty()
for mu in d.parameter_space.sample_uniformly(2):
    snapshots.append(d.solve(mu))

# apply POD
reduced_basis = pod(snapshots, 4)[0]

# reduce the model
reductor = GenericRBReductor(d, reduced_basis)
rd = reductor.reduce()

# stochastic error estimation
mu_max = None
err_max = -1.
for mu in d.parameter_space.sample_randomly(10):
    U_RB = (reductor.reconstruct(rd.solve(mu)))
    U = d.solve(mu)
    err = np.max((U_RB-U).l2_norm())
    if err > err_max:
        err_max = err
        mu_max = mu

# visualize maximum error solution
U_RB = (reductor.reconstruct(rd.solve(mu_max)))
U = d.solve(mu_max)
d.visualize((U_RB, U), title='mu = {}'.format(mu), legend=('reduced', 'detailed'))
d.visualize((U-U_RB), title='mu = {}'.format(mu), legend=('error'))
