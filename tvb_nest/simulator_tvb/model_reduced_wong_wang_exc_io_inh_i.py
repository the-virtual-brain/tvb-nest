# -*- coding: utf-8 -*-
#
#
#  TheVirtualBrain-Scientific Package. This package holds all simulators, and
# analysers necessary to run brain-simulations. You can use it stand alone or
# in conjunction with TheVirtualBrain-Framework Package. See content of the
# documentation-folder for more details. See also http://www.thevirtualbrain.org
#
# (c) 2012-2017, Baycrest Centre for Geriatric Care ("Baycrest") and others
#
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.  See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with this
# program.  If not, see <http://www.gnu.org/licenses/>.
#
#
#   CITATION:
# When using The Virtual Brain for scientific publications, please cite it as follows:
#
#   Paula Sanz Leon, Stuart A. Knock, M. Marmaduke Woodman, Lia Domide,
#   Jochen Mersmann, Anthony R. McIntosh, Viktor Jirsa (2013)
#       The Virtual Brain: a simulator of primate brain network dynamics.
#   Frontiers in Neuroinformatics (7:10. doi: 10.3389/fninf.2013.00010)

"""
Models based on Wong-Wang's work.

"""

from numba import guvectorize, float64
from tvb.simulator.models.base import numpy, basic, arrays, ModelNumbaDfun, LOG


@guvectorize([(float64[:],)*23], '(n),(m)' + ',()'*20 + '->(n)', nopython=True)
def _numba_dfun(S, c, ae, be, de, ge, te, wp, we, jn, re, ai, bi, di, gi, ti, wi, ji, ri, g, l, io, dx):
    "Gufunc for reduced Wong-Wang model equations."

    cc = g[0]*jn[0]*c[0]

    if S[0] < 0.0:
        S_e = 0.0
    elif S[0] > 1.0:
        S_e = 1.0
    else:
        S_e = S[0]

    jnSe = jn[0] * S_e

    if S[1] < 0.0:
        S_i = 0.0
    elif S[1] > 1.0:
        S_i = 1.0
    else:
        S_i = S[1]

    if re[0] < 0.0:
        x = wp[0]*jnSe - ji[0]*S_i + we[0]*io[0] + cc
        x = ae[0]*x - be[0]
        h = x / (1 - numpy.exp(-de[0]*x))
    else:
        h = re[0]
    dx[0] = - (S_e / te[0]) + (1.0 - S_e) * h * ge[0]

    if ri[0] < 0.0:
        x = jnSe - S_i + wi[0]*io[0] + l[0]*cc
        x = ai[0]*x - bi[0]
        h = x / (1 - numpy.exp(-di[0]*x))
    else:
        h = ri[0]
    dx[1] = - (S_i / ti[0]) + h * gi[0]


class ReducedWongWangExcIOInhI(ModelNumbaDfun):
    r"""
    .. [WW_2006] Kong-Fatt Wong and Xiao-Jing Wang,  *A Recurrent Network
                Mechanism of Time Integration in Perceptual Decisions*.
                Journal of Neuroscience 26(4), 1314-1328, 2006.

    .. [DPA_2014] Deco Gustavo, Ponce Alvarez Adrian, Patric Hagmann,
                  Gian Luca Romani, Dante Mantini, and Maurizio Corbetta. *How Local
                  Excitation–Inhibition Ratio Impacts the Whole Brain Dynamics*.
                  The Journal of Neuroscience 34(23), 7886 –7898, 2014.



    .. automethod:: ReducedWongWang.__init__

    Equations taken from [DPA_2013]_ , page 11242

    .. math::
                 x_{ek}       &=   w_p\,J_N \, S_{ek} - J_iS_{ik} + W_eI_o + GJ_N \mathbf\Gamma(S_{ek}, S_{ej}, u_{kj}),\\
                 H(x_{ek})    &=  \dfrac{a_ex_{ek}- b_e}{1 - \exp(-d_e(a_ex_{ek} -b_e))},\\
                 \dot{S}_{ek} &= -\dfrac{S_{ek}}{\tau_e} + (1 - S_{ek}) \, \gammaH(x_{ek}) \,

                 x_{ik}       &=   J_N \, S_{ek} - S_{ik} + W_iI_o + \lambdaGJ_N \mathbf\Gamma(S_{ik}, S_{ej}, u_{kj}),\\
                 H(x_{ik})    &=  \dfrac{a_ix_{ik} - b_i}{1 - \exp(-d_i(a_ix_{ik} -b_i))},\\
                 \dot{S}_{ik} &= -\dfrac{S_{ik}}{\tau_i} + \gamma_iH(x_{ik}) \,

    """
    _ui_name = "Reduced Wong-Wang"
    ui_configurable_parameters = ['a_e', 'b_e', 'd_e', 'gamma_e', 'tau_e', 'W_e', 'w_p', 'J_N',
                                  'a_i', 'b_i', 'd_i', 'gamma_i', 'tau_i', 'W_i', 'J_i',
                                  'I_o', 'G', 'lamda']

    # Define traited attributes for this model, these represent possible kwargs.
    r_e = arrays.FloatArray(
        label=":math:`r_e`",
        default=numpy.array([-1., ]),
        range=basic.Range(lo=-1., hi=10000., step=1.),
        doc="[Hz]. Excitatory population firing rate.",
        order=1)

    a_e = arrays.FloatArray(
        label=":math:`a_e`",
        default=numpy.array([310., ]),
        range=basic.Range(lo=0., hi=500., step=1.),
        doc="[n/C]. Excitatory population input gain parameter, chosen to fit numerical solutions.",
        order=1)

    b_e = arrays.FloatArray(
        label=":math:`b_e`",
        default=numpy.array([125., ]),
        range=basic.Range(lo=0., hi=200., step=1.),
        doc="[Hz]. Excitatory population input shift parameter chosen to fit numerical solutions.",
        order=2)

    d_e = arrays.FloatArray(
        label=":math:`d_e`",
        default=numpy.array([0.160, ]),
        range=basic.Range(lo=0.0, hi=0.2, step=0.001),
        doc="""[s]. Excitatory population input scaling parameter chosen to fit numerical solutions.""",
        order=3)

    gamma_e = arrays.FloatArray(
        label=r":math:`\gamma_e`",
        default=numpy.array([0.641/1000, ]),
        range=basic.Range(lo=0.0, hi=1.0/1000, step=0.01/1000),
        doc="""Excitatory population kinetic parameter""",
        order=4)

    tau_e = arrays.FloatArray(
        label=r":math:`\tau_e`",
        default=numpy.array([100., ]),
        range=basic.Range(lo=50., hi=150., step=1.),
        doc="""[ms]. Excitatory population NMDA decay time constant.""",
        order=5)

    w_p = arrays.FloatArray(
        label=r":math:`w_p`",
        default=numpy.array([1.4, ]),
        range=basic.Range(lo=0.0, hi=2.0, step=0.01),
        doc="""Excitatory population recurrence weight""",
        order=6)

    J_N = arrays.FloatArray(
        label=r":math:`J_{N}`",
        default=numpy.array([0.15, ]),
        range=basic.Range(lo=0.001, hi=0.5, step=0.001),
        doc="""[nA] NMDA current""",
        order=7)

    W_e = arrays.FloatArray(
        label=r":math:`W_e`",
        default=numpy.array([1.0, ]),
        range=basic.Range(lo=0.0, hi=2.0, step=0.01),
        doc="""Excitatory population external input scaling weight""",
        order=8)

    r_i = arrays.FloatArray(
        label=":math:`r_i`",
        default=numpy.array([-1., ]),
        range=basic.Range(lo=-1., hi=10000., step=1.),
        doc="[Hz]. Inhibitory population firing rate.",
        order=1)

    a_i = arrays.FloatArray(
        label=":math:`a_i`",
        default=numpy.array([615., ]),
        range=basic.Range(lo=0., hi=1000., step=1.),
        doc="[n/C]. Inhibitory population input gain parameter, chosen to fit numerical solutions.",
        order=9)

    b_i = arrays.FloatArray(
        label=":math:`b_i`",
        default=numpy.array([177.0, ]),
        range=basic.Range(lo=0.0, hi=200.0, step=1.0),
        doc="[Hz]. Inhibitory population input shift parameter chosen to fit numerical solutions.",
        order=10)

    d_i = arrays.FloatArray(
        label=":math:`d_i`",
        default=numpy.array([0.087, ]),
        range=basic.Range(lo=0.0, hi=0.2, step=0.001),
        doc="""[s]. Inhibitory population input scaling parameter chosen to fit numerical solutions.""",
        order=11)

    gamma_i = arrays.FloatArray(
        label=r":math:`\gamma_i`",
        default=numpy.array([1.0/1000, ]),
        range=basic.Range(lo=0.0, hi=2.0/1000, step=0.01/1000),
        doc="""Inhibitory population kinetic parameter""",
        order=12)

    tau_i = arrays.FloatArray(
        label=r":math:`\tau_i`",
        default=numpy.array([10., ]),
        range=basic.Range(lo=50., hi=150., step=1.0),
        doc="""[ms]. Inhibitory population NMDA decay time constant.""",
        order=13)

    J_i = arrays.FloatArray(
        label=r":math:`J_{i}`",
        default=numpy.array([1.0, ]),
        range=basic.Range(lo=0.001, hi=2.0, step=0.001),
        doc="""[nA] Local inhibitory current""",
        order=14)

    W_i = arrays.FloatArray(
        label=r":math:`W_i`",
        default=numpy.array([0.7, ]),
        range=basic.Range(lo=0.0, hi=1.0, step=0.01),
        doc="""Inhibitory population external input scaling weight""",
        order=15)

    I_o = arrays.FloatArray(
        label=":math:`I_{o}`",
        default=numpy.array([0.382, ]),
        range=basic.Range(lo=0.0, hi=1.0, step=0.001),
        doc="""[nA]. Effective external input""",
        order=16)

    G = arrays.FloatArray(
        label=":math:`G`",
        default=numpy.array([2.0, ]),
        range=basic.Range(lo=0.0, hi=10.0, step=0.01),
        doc="""Global coupling scaling""",
        order=17)

    lamda = arrays.FloatArray(
        label=":math:`\lambda`",
        default=numpy.array([0.0, ]),
        range=basic.Range(lo=0.0, hi=1.0, step=0.01),
        doc="""Inhibitory global coupling scaling""",
        order=18)

    state_variable_range = basic.Dict(
        label="State variable ranges [lo, hi]",
        default={"S_e": numpy.array([0.0, 1.0]), "S_i": numpy.array([0.0, 1.0])},
        doc="Population firing rate",
        order=22
    )

    # Used for phase-plane axis ranges and to bound random initial() conditions.
    state_variable_constraint = basic.Dict(
        label="State Variable constraints [lo, hi]",
        default={"S_e": numpy.array([0.0, 1.0]), "S_i": numpy.array([0.0, 1.0])},
        doc="""The values for each state-variable should be set to encompass
            the boundaries of the dynamic range of that state-variable. Set None for one-sided boundaries""",
        order=23)

    variables_of_interest = basic.Enumerate(
        label="Variables watched by Monitors",
        options=['S_e', 'S_i'],
        default=['S_e', 'S_i'],
        select_multiple=True,
        doc="""default state variables to be monitored""",
        order=24)

    state_variables = ['S_e', 'S_i']
    _nvar = 2
    cvar = numpy.array([0], dtype=numpy.int32)

    def configure(self):
        """  """
        super(ReducedWongWangExcIOInhI, self).configure()
        self.update_derived_parameters()

    def _numpy_dfun(self, state_variables, coupling, local_coupling=0.0):
        r"""
        Equations taken from [DPA_2013]_ , page 11242

        .. math::
                 x_{ek}       &=   w_p\,J_N \, S_{ek} - J_iS_{ik} + W_eI_o + GJ_N \mathbf\Gamma(S_{ek}, S_{ej}, u_{kj}),\\
                 H(x_{ek})    &=  \dfrac{a_ex_{ek}- b_e}{1 - \exp(-d_e(a_ex_{ek} -b_e))},\\
                 \dot{S}_{ek} &= -\dfrac{S_{ek}}{\tau_e} + (1 - S_{ek}) \, \gammaH(x_{ek}) \,

                 x_{ik}       &=   J_N \, S_{ek} - S_{ik} + W_iI_o + \lambdaGJ_N \mathbf\Gamma(S_{ik}, S_{ej}, u_{kj}),\\
                 H(x_{ik})    &=  \dfrac{a_ix_{ik} - b_i}{1 - \exp(-d_i(a_ix_{ik} -b_i))},\\
                 \dot{S}_{ik} &= -\dfrac{S_{ik}}{\tau_i} + \gamma_iH(x_{ik}) \,

        """
        S = state_variables[:, :]

        S[S < 0] = 0.0
        S[S > 1] = 1.0

        c_0 = coupling[0, :]

        # if applicable
        lc_0 = local_coupling * S[0]

        coupling = self.G * self.J_N * (c_0 + lc_0)

        J_N_S_e = self.J_N * S[0]

        # TODO: Confirm that this combutation is correct for this model depending on the r_e and r_i values!
        x_e = self.w_p * J_N_S_e - self.J_i * S[1] + self.W_e * self.I_o + coupling

        x_e = self.a_e * x_e - self.b_e
        H_e = numpy.where(self.r_e >= 0, self.r_e, x_e / (1 - numpy.exp(-self.d_e * x_e)))

        dS_e = - (S[0] / self.tau_e) + (1 - S[0]) * H_e * self.gamma_e

        x_i = J_N_S_e - S[1] + self.W_i * self.I_o + self.lamda * coupling

        x_i = self.a_i * x_i - self.b_i
        H_i = numpy.where(self.r_i >= 0, self.r_i, x_i / (1 - numpy.exp(-self.d_i * x_i)))

        dS_i = - (S[1] / self.tau_i) + H_i * self.gamma_i

        derivative = numpy.array([dS_e, dS_i])

        return derivative

    def dfun(self, x, c, local_coupling=0.0, **kwargs):
        x_ = x.reshape(x.shape[:-1]).T
        c_ = c.reshape(c.shape[:-1]).T + local_coupling * x[0]
        deriv = _numba_dfun(x_, c_,
                            self.a_e, self.b_e, self.d_e, self.gamma_e, self.tau_e,
                            self.w_p, self.W_e, self.J_N, self.r_e,
                            self.a_i, self.b_i, self.d_i, self.gamma_i, self.tau_i,
                            self.W_i, self.J_i, self.r_i,
                            self.G, self.lamda, self.I_o)
        return deriv.T[..., numpy.newaxis]

