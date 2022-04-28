from logging import Logger
from tvb.basic.neotraits._attr import Attr

from tvb_multiscale.core.orchestrators.spikeNet_app import SpikeNetSerialApp, SpikeNetParallelApp
from tvb_multiscale.core.orchestrators.tvb_app import TVBSerialApp as TVBSerialAppBase
from tvb_multiscale.core.orchestrators.serial_orchestrator import SerialOrchestrator

from tvb_multiscale.tvb_netpyne.config import Config, CONFIGURED, initialize_logger
from tvb_multiscale.tvb_netpyne.netpyne_models.builders.netpyne_factory import load_netpyne
from tvb_multiscale.tvb_netpyne.netpyne_models.network import NetpyneNetwork
from tvb_multiscale.tvb_netpyne.netpyne_models.builders.base import NetpyneNetworkBuilder
from tvb_multiscale.tvb_netpyne.netpyne_models.models.default_exc_io_inh_i import DefaultExcIOInhIBuilder
from tvb_multiscale.tvb_netpyne.interfaces.builders import NetpyneProxyNodesBuilder, TVBNetpyneInterfaceBuilder
from tvb_multiscale.tvb_netpyne.interfaces.models.default import DefaultTVBNetpyneInterfaceBuilder
    

class NetpyneSerialApp(SpikeNetSerialApp):

    """NetpyneSerialApp class"""

    config = Attr(
        label="Configuration",
        field_type=Config,
        doc="""Config class instance.""",
        required=True,
        default=CONFIGURED
    )

    logger = Attr(
        label="Logger",
        field_type=Logger,
        doc="""logging.Logger instance.""",
        required=True,
        default=initialize_logger(__name__, config=CONFIGURED)
    )

    spikeNet_builder = Attr(
        label="Netpyne Network Builder",
        field_type=NetpyneNetworkBuilder,
        doc="""Instance of Netpyne Network Builder.""",
        required=True,
        default=DefaultExcIOInhIBuilder()
    )

    spiking_network = Attr(
        label="NetPyNE Network",
        field_type=NetpyneNetwork,
        doc="""Instance of NetpyneNetwork class.""",
        required=False
    )

    @property
    def netpyne_instance(self):
        return self.spiking_cosimulator

    @property
    def netpyne_synaptic_weight_scale(self):
        # TODO: this is not specific to serial app. Once Parallel app is ready, move to some common ancestor, to use in both cases (see also: TVBNetpyneSerialOrchestrator.build_interfaces())
        return 1.0

    # @property
    # def netpyne_network(self):
    #     return self.spiking_network

    # @property
    # def netpyne_model_builder(self):
    #     return self.spikeNet_builder

    def start(self):
        self.spiking_cosimulator = load_netpyne(self.spikeNet_builder.spiking_dt, self.config)

    def configure(self):
        super(NetpyneSerialApp, self).configure()
        # self.spiking_cosimulator = configure_nest_kernel(self._spiking_cosimulator, self.config)
        self.spikeNet_builder.netpyne_synaptic_weight_scale = self.netpyne_synaptic_weight_scale
        self.spikeNet_builder.netpyne_instance = self.spiking_cosimulator

    def configure_simulation(self):
        super(NetpyneSerialApp, self).configure_simulation()
        self.netpyne_instance.createAndPrepareNetwork(self.simulation_length)

    def simulate(self, simulation_length=None):
        if simulation_length is None:
            simulation_length = self.simulation_length
        self.spiking_cosimulator.run(simulation_length)

    def run(self, *args, **kwargs):
        self.configure()
        self.build()

    def clean_up(self):
        self.spiking_cosimulator.finalize()

    def stop(self):
        pass

class TVBSerialApp(TVBSerialAppBase):

    """TVBSerialApp class"""

    config = Attr(
        label="Configuration",
        field_type=Config,
        doc="""Configuration class instance.""",
        required=True,
        default=CONFIGURED
    )

    logger = Attr(
        label="Logger",
        field_type=Logger,
        doc="""logging.Logger instance.""",
        required=True,
        default=initialize_logger(__name__, config=CONFIGURED)
    )

    interfaces_builder = Attr(
        label="TVBNESTInterfaces builder",
        field_type=TVBNetpyneInterfaceBuilder,
        doc="""Instance of TVBNESTInterfaces' builder class.""",
        required=True,
        default=DefaultTVBNetpyneInterfaceBuilder()
    )

    spiking_network = Attr(
        label="NEST Network",
        field_type=NetpyneNetwork,
        doc="""Instance of NESTNetwork class.""",
        required=False
    )

    _default_interface_builder = TVBNetpyneInterfaceBuilder

class TVBNetpyneSerialOrchestrator(SerialOrchestrator):

    config = Attr(
        label="Configuration",
        field_type=Config,
        doc="""Configuration class instance.""",
        required=True,
        default=CONFIGURED
    )

    logger = Attr(
        label="Logger",
        field_type=Logger,
        doc="""logging.Logger instance.""",
        required=True,
        default=initialize_logger(__name__, config=CONFIGURED)
    )

    tvb_app = Attr(
        label="TVBSerial app",
        field_type=TVBSerialApp,
        doc="""Application for running TVB serially.""",
        required=True,
        default=TVBSerialApp()
    )

    spikeNet_app = Attr(
        label="NetPyNE Network app",
        field_type=NetpyneSerialApp,
        doc="""Application for running a Spiking Network (co)simulator serially.""",
        required=False,
        default=NetpyneSerialApp()
    )

    def build_interfaces(self):
        self.tvb_app.interfaces_builder.netpyne_synaptic_weight_scale = self.spikeNet_app.netpyne_synaptic_weight_scale
        SerialOrchestrator.build_interfaces(self)