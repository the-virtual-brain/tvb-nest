# -*- coding: utf-8 -*-

from tvb_multiscale.tvb_annarchy.interfaces.tvb_to_annarchy_parameters_interface import TVBtoANNarchyParameterInterface

from tvb_multiscale.core.tvb.interfaces.builders import \
    TVBtoSpikeNetParameterInterfaceBuilder


class TVBtoANNarchyParameterInterfaceBuilder(TVBtoSpikeNetParameterInterfaceBuilder):
    _build_target_class = TVBtoANNarchyParameterInterface

    @property
    def annarchy_instance(self):
        return self.spiking_network.annarchy_instance
