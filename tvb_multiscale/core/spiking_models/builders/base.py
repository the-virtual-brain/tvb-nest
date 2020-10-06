# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
from six import string_types
from collections import OrderedDict
import numpy as np
from pandas import Series

from tvb_multiscale.core.config import CONFIGURED, initialize_logger
from tvb_multiscale.core.spiking_models.region_node import SpikingRegionNode
from tvb_multiscale.core.spiking_models.brain import SpikingBrain
from tvb.contrib.scripts.utils.log_error_utils import raise_value_error
from tvb.contrib.scripts.utils.data_structures_utils import ensure_list, flatten_tuple, property_to_fun


LOG = initialize_logger(__name__)


class SpikingModelBuilder(object):
    __metaclass__ = ABCMeta

    # Default configuratons modifiable by the user:
    config = CONFIGURED

    tvb_to_spiking_dt_ratio = 4
    default_min_spiking_dt = 0.001
    default_min_delay_ratio = 2
    default_min_delay = 0.001
    default_population = {}
    default_populations_connection = {}
    default_nodes_connection = {}
    default_devices_connection = {}

    population_order = 100

    # User inputs:
    tvb_simulator = None
    spiking_nodes_ids = []
    populations = []
    populations_connections = []
    nodes_connections = []
    output_devices = [] # Use these to observe Spiking Simulator behavior
    input_devices = []  # use these for possible external stimulation devices

    # Internal configurations and outputs:
    monitor_period = 1.0
    spiking_dt = 0.1 / tvb_to_spiking_dt_ratio
    _spiking_nodes_labels = []
    _populations = []
    _populations_connections = []
    _nodes_connections = []
    _output_devices = []
    _input_devices = []
    _spiking_brain = SpikingBrain()
    _models = []

    def __init__(self, tvb_simulator, spiking_nodes_ids, config=CONFIGURED, logger=LOG):
        self.config = config
        self.logger = logger
        self.spiking_nodes_ids = np.unique(spiking_nodes_ids)
        self.tvb_simulator = tvb_simulator
        self._update_spiking_dt()
        self._update_default_min_delay()
        # We assume that there at least the Raw monitor which is also used for communication to/from Spiking Simulator
        # If there is only the Raw monitor, then self.monitor_period = self.tvb_dt
        self.monitor_period = tvb_simulator.monitors[-1].period
        self.population_order = 100
        self._models = []
        self._spiking_brain = SpikingBrain()

    @abstractmethod
    def build_spiking_population(self, label, model, size, params):
        pass

    @abstractmethod
    def build_spiking_region_node(self, label="", input_node=SpikingRegionNode(), *args, **kwargs):
        pass

    @property
    def min_delay(self):
        return self.default_min_delay

    @abstractmethod
    def set_synapse(self, syn_model, weight, delay, receptor_type):
        pass

    @abstractmethod
    def connect_two_populations(self, source, target, conn_params, synapse_params):
        pass

    @abstractmethod
    def build_and_connect_devices(self, devices):
        pass

    @abstractmethod
    def build(self):
        pass

    @property
    def tvb_model(self):
        return self.tvb_simulator.model

    @property
    def tvb_connectivity(self):
        return self.tvb_simulator.connectivity

    @property
    def tvb_weights(self):
        return self.tvb_simulator.connectivity.weights

    @property
    def tvb_delays(self):
        return self.tvb_simulator.connectivity.delays

    @property
    def tvb_dt(self):
        return self.tvb_simulator.integrator.dt

    @property
    def number_of_nodes(self):
        return self.tvb_connectivity.number_of_regions

    @property
    def number_of_spiking_nodes(self):
        return np.maximum(len(self.spiking_nodes_ids), 1)

    # The methods below are used in order to return the builder's properties
    # per spiking node or spiking nodes' connection

    @property
    def spiking_nodes_labels(self):
        if len(self._spiking_nodes_labels) == self.number_of_spiking_nodes:
            return self._spiking_nodes_labels
        else:
            return self.tvb_connectivity.region_labels[self.spiking_nodes_ids]

    def _population_property_per_node(self, property):
        output = OrderedDict()
        for population in self.populations:
            output[population["label"]] = property_per_node(population[property],
                                                            population.get("nodes", self.spiking_nodes_ids),
                                                            self.tvb_connectivity.region_labels)
        return output

    @property
    def number_of_populations(self):
        return len(self.populations)

    @property
    def populations_models(self):
        return self._population_property_per_node("model")

    @property
    def populations_nodes(self):
        return self._population_property_per_node("nodes")

    @property
    def populations_scales(self):
        return self._population_property_per_node("scale")

    @property
    def populations_sizes(self):
        scales = self._population_property_per_node("scale")
        for pop_name, scale in scales.items():
            if isinstance(scale, dict):
                for node_key, node_scale in scale.items():
                    scales[pop_name][node_key] = int(np.round(scales[pop_name][node_key] * self.population_order))
            else:
                scales[pop_name] *= self.population_order
        return scales

    @property
    def populations_params(self):
        return self._population_property_per_node("params")

    def _connection_label(self, connection):
        return "%s->%s" % (str(connection["source"]), str(connection["target"]))

    def _connection_property_per_node(self, property, connections):
        output = OrderedDict()
        for conn in connections:
            output[self._connection_label(conn)] = \
                property_per_node(conn[property], conn.get("nodes", self.spiking_nodes_ids),
                                  self.tvb_connectivity.region_labels)
        return output

    def _population_connection_property_per_node(self, property):
        return self._connection_property_per_node(property, self.populations_connections)

    @property
    def populations_connections_labels(self):
        return [self._connection_label(conn) for conn in self.populations_connections]

    @property
    def populations_connections_models(self):
        return self._population_connection_property_per_node("synapse_model")

    @property
    def populations_connections_weights(self):
        return self._population_connection_property_per_node("weight")

    @property
    def populations_connections_delays(self):
        return self._population_connection_property_per_node("delay")

    @property
    def populations_connections_receptor_types(self):
        return self._population_connection_property_per_node("receptor_type")

    @property
    def populations_connections_conn_spec(self):
        return self._population_connection_property_per_node("conn_spec")

    @property
    def populations_connections_nodes(self):
        return self._population_connection_property_per_node("nodes")

    def _nodes_connection_property_per_node(self, property):
        output = OrderedDict()
        for conn in self.nodes_connections:
            output[self._connection_label(conn)] = \
                property_per_nodes_connection(conn[property],
                                              conn.get("source_nodes", self.spiking_nodes_ids),
                                              conn.get("target_nodes", self.spiking_nodes_ids),
                                              self.spiking_nodes_ids, self.tvb_connectivity.region_labels)
        return output

    @property
    def nodes_connections_labels(self):
        return [self._connection_label(conn) for conn in self.nodes_connections]

    @property
    def nodes_connections_models(self):
        return self._nodes_connection_property_per_node("synapse_model")

    @property
    def nodes_connections_weights(self):
        return self._nodes_connection_property_per_node("weight")

    @property
    def nodes_connections_delays(self):
        return self._nodes_connection_property_per_node("delay")

    @property
    def nodes_connections_receptor_types(self):
        return self._nodes_connection_property_per_node("receptor_type")

    @property
    def nodes_connections_conn_spec(self):
        return self._nodes_connection_property_per_node("conn_spec")

    @property
    def nodes_connections_source_nodes(self):
        return self._nodes_connection_property_per_node("source_nodes")

    @property
    def nodes_connections_target_nodes(self):
        return self._nodes_connection_property_per_node("target_nodes")

    def _assert_delay(self, delay):
        assert delay >= 0.0
        return delay

    def _assert_within_node_delay(self, delay):
        if delay > self.tvb_dt / 2:
            if delay > self.tvb_dt:
                raise ValueError("Within Spiking nodes delay %f is not smaller "
                                 "than the TVB integration time step %f!"
                                 % (delay, self.tvb_dt))
            else:
                LOG.warning("Within Spiking nodes delay %f is not smaller "
                            "than half the TVB integration time step %f!"
                            % (delay, self.tvb_dt))
        return self._assert_delay(delay)

    def _update_spiking_dt(self):
        # The TVB dt should be an integer multiple of the spiking simulator dt:
        self.spiking_dt = int(np.round(self.tvb_dt / self.tvb_to_spiking_dt_ratio / self.default_min_spiking_dt)) \
                          * self.default_min_spiking_dt

    def _update_default_min_delay(self):
        # The Spiking Network min delay should be smaller than half the TVB dt,
        # and an integer multiple of the spiking simulator dt
        self.default_min_delay = np.minimum(
            np.maximum(self.default_min_delay_ratio * self.spiking_dt, self.min_delay),
            self.tvb_dt / 2)

    def _configure_populations(self):
        # Every population must have its own model model, label.
        # scale of spiking neurons' number, and model specific parameters,
        # and a list of spiking region nodes where it is going to be placed
        # "scale" and "parameters" can be given as functions.
        # This configuration will make confirm user inputs
        # and set the two properties above as functions of node index
        self.populations_labels = []
        _populations = []
        for i_pop, population in enumerate(self.populations):
            _populations.append(dict(self.default_population))
            _populations[-1].update(population)
            if len(_populations[-1].get("label", "")) == 0:
                _populations[-1]["label"] = "Pop%d" % i_pop
            self.populations_labels.append(_populations[-1]["label"])
            if _populations[-1]["nodes"] is None:
                _populations[-1]["nodes"] = self.spiking_nodes_ids
            _model = _populations[-1]["model"]
            if _model not in self._models:
                self._models.append(_model)
            _populations[-1]["scale"] = property_to_fun(_populations[-1]["scale"])
            _populations[-1]["params"] = property_to_fun(_populations[-1]["params"])
        self.populations_labels = np.unique(self.populations_labels).tolist()
        self._populations = _populations
        return self._populations

    def _assert_connection_populations(self, connection):
        # This method will make sure that there source and target user inputs for every population connection
        # and that every source/target population is already among the populations to be generated.
        for pop in ["source", "target"]:
            pops_labels = connection.get(pop, None)
        if pops_labels is None:
            raise_value_error("No %s population in connection!:\n%s" % (pop, str(connection)))
        for pop_lbl in ensure_list(pops_labels):
            assert pop_lbl in self.populations_labels
        return pops_labels

    def _configure_connections(self, connections, default_connection):
        # This method sets "weight", "delay" and "receptor_type" synapse properties
        # as functions of the node where the populations are placed
        _connections = []
        for i_con, connection in enumerate(connections):
            self._assert_connection_populations(connection)
            temp_conn = dict(default_connection)
            temp_conn.update(connection)
            _connections.append(temp_conn)
            for prop in ["weight", "delay", "receptor_type", "params"]:
                _connections[i_con][prop] = property_to_fun(_connections[i_con][prop])
            for prop in ["source_neurons", "target_neurons"]:
                inds_fun = _connections[i_con].get(prop, None)
                if inds_fun is not None:
                    _connections[i_con][prop] = property_to_fun(inds_fun)
                else:
                    _connections[i_con][prop] = None
            _model = _connections[i_con].get("synapse_model", _connections[i_con].get("model", None))
            if _model is not None and _model not in self._models:
                self._models.append(_model)
        return _connections

    def _configure_populations_connections(self):
        _populations_connections = self._configure_connections(self.populations_connections,
                                                               self.default_populations_connection)
        for i_conn, connections in enumerate(self.populations_connections):
            if connections["nodes"] is None:
                _populations_connections[i_conn]["nodes"] = self.spiking_nodes_ids
        self._populations_connections = _populations_connections
        return self._populations_connections

    def _configure_nodes_connections(self):
        _nodes_connections = self._configure_connections(self.nodes_connections,
                                                         self.default_nodes_connection)
        for i_conn, connections in enumerate(self.nodes_connections):
            for pop in ["source", "target"]:
                this_pop = "%s_nodes" % pop
                if connections[this_pop] is None:
                    _nodes_connections[i_conn][this_pop] = self.spiking_nodes_ids
        self.tvb_connectivity.configure()
        self._nodes_connections = _nodes_connections
        return self._nodes_connections

    def _configure_devices(self, devices):
        # Configure devices by the variable model they measure or stimulate (Series),
        # population (Series),
        # and target node (Series) for faster reading
        # "weight", "delay" and "receptor_type" are set as functions, following user input
        _devices = list()
        for device in devices:
            _devices.append(dict(device))
            spiking_nodes = device.get("nodes", self.spiking_nodes_ids)
            if spiking_nodes is None:
                spiking_nodes = self.spiking_nodes_ids
            # User inputs
            # ..set/converted to functions
            weights_fun = property_to_fun(device.get("weights", 1.0))
            delays_fun = property_to_fun(device.get("delays", 0.0))
            receptor_type_fun = property_to_fun(device.get("receptor_type",
                                                           self.default_devices_connection["receptor_type"]))
            # Default behavior for any region node and any combination of populations
            # is to target all of their neurons:
            neurons_fun = device.get("neurons_fun", None)
            if neurons_fun is not None:
                neurons_fun = property_to_fun(neurons_fun)
            # Defaults in arrays:
            shape = (len(spiking_nodes),)
            receptor_type = np.tile(self.default_devices_connection["receptor_type"])
            # weights and delays might be dictionaries for distributions:
            weights = np.ones(shape).astype("O")
            delays = np.zeros(shape).astype("O")
            neurons = np.tile([None], shape).astype("O")
            # Set now the properties using the above defined functions:
            for i_trg, trg_node in enumerate(spiking_nodes):
                weights[i_trg] = weights_fun(trg_node)  # a function also of self.tvb_weights
                delays[i_trg] = delays_fun(trg_node)    # a function also of self.tvb_delays
                receptor_type[i_trg] = receptor_type_fun(trg_node)
                if neurons_fun is not None:
                    neurons[i_trg] = lambda neurons: neurons_fun(trg_node, neurons)
            _devices[-1]["params"] = device.get("params", {})
            _devices[-1]["weights"] = weights
            _devices[-1]["delays"] = delays
            _devices[-1]["receptor_type"] = receptor_type
            _devices[-1]["neurons_fun"] = neurons
            _devices[-1]["nodes"] = [np.where(self.spiking_nodes_ids == trg_node)[0][0] for trg_node in spiking_nodes]
        return _devices

    def _configure_output_devices(self):
        self._output_devices = self._configure_devices(self.output_devices)
        return self._output_devices

    def _configure_input_devices(self):
        self._input_devices = self._configure_devices(self.input_devices)
        return self._input_devices

    def configure(self):
        self._configure_populations()
        self._configure_populations_connections()
        self._configure_nodes_connections()
        self._configure_output_devices()
        self._configure_input_devices()

    def build_spiking_region_nodes(self, *args, **kwargs):
        # For every Spiking node
        for node_id, node_label in zip(self.spiking_nodes_ids, self.spiking_nodes_labels):
            self._spiking_brain[node_label] = self.build_spiking_region_node(node_label)
            # ...and every population in it...
            for iP, population in enumerate(self._populations):
                # ...if this population exists in this node...
                if node_id in population["nodes"]:
                    # ...generate this population in this node...
                    size = int(np.round(population["scale"](node_id) * self.population_order))
                    self._spiking_brain[node_label][population["label"]] = \
                        self.build_spiking_population(population["label"], population["model"], size,
                                                      params=population["params"](node_id),
                                                      *args, **kwargs)

    def connect_within_node_spiking_populations(self):
        # For every different type of connections between distinct Spiking nodes' populations
        for i_conn, conn in enumerate(ensure_list(self._populations_connections)):
            # ...and form the connection within each Spiking node
            for node_index in conn["nodes"]:
                i_node = np.where(self.spiking_nodes_ids == node_index)[0][0]
                syn_spec = self.set_synapse(conn["synapse_model"],
                                            conn['weight'](node_index),
                                            self._assert_delay(conn['delay'](node_index)),
                                            conn['receptor_type'](node_index),
                                            conn["params"]
                                            )
                syn_spec.update()
                for pop_src in ensure_list(conn["source"]):
                    for pop_trg in ensure_list(conn["target"]):
                        self.connect_two_populations(
                            self._spiking_brain[i_node][pop_src], conn["source_inds"],
                            self._spiking_brain[i_node][pop_trg], conn["target_inds"],
                            conn['conn_spec'], syn_spec
                        )

    def connect_spiking_region_nodes(self):
        # For every different type of connections between distinct Spiking nodes' populations
        for i_conn, conn in enumerate(ensure_list(self._nodes_connections)):
            # ...form the connection for every distinct pair of Spiking nodes
            for source_index in conn["source_nodes"]:
                i_source_node = np.where(self.spiking_nodes_ids == source_index)[0][0]
                for target_index in conn["target_nodes"]:
                    i_target_node = np.where(self.spiking_nodes_ids == target_index)[0][0]
                    syn_spec = self.set_synapse(conn["synapse_model"],
                                                conn["weight"](source_index, target_index),
                                                conn["delay"](source_index, target_index),
                                                conn["receptor_type"](source_index, target_index)
                                                )
                    if source_index != target_index:
                        for conn_src in ensure_list(conn["source"]):
                            src_pop = self._spiking_brain[i_source_node][conn_src]
                            for conn_trg in ensure_list(conn["target"]):
                                trg_pop = self._spiking_brain[i_target_node][conn_trg]
                                self.connect_two_populations(src_pop, conn["source_inds"],
                                                             trg_pop, conn["target_inds"],
                                                             conn['conn_spec'], syn_spec)

    def build_spiking_brain(self):
        # Build and connect internally all Spiking nodes
        self.build_spiking_region_nodes()
        self.connect_within_node_spiking_populations()
        # Connect Spiking nodes among each other
        self.connect_spiking_region_nodes()

    def _build_and_connect_devices(self, devices):
        # Build devices by the variable model they measure or stimulate (Series),
        # population (Series),
        # and target node (Series) for faster reading
        _devices = Series()
        for device in devices:
            _devices = _devices.append(
                            self.build_and_connect_devices(device))
        return _devices

    def build_and_connect_output_devices(self):
        # Build devices by the variable model they measure (Series),
        # population (Series),
        # and target node (Series) for faster
        return self._build_and_connect_devices(self._output_devices)

    def build_and_connect_input_devices(self):
        # Build devices by the variable model they stimulate (Series),
        # population (Series),
        # and target node (Series) for faster reading
        return self._build_and_connect_devices(self._input_devices)

    def build_spiking_network(self):
        # Configure all inputs to set them to the correct formats and sizes
        self.configure()
        # Build and connect the brain network
        self.build_spiking_brain()
        # Build and connect possible Spiking output devices
        # !!Use it only for extra Spiking quantities
        # that do not correspond to TVB state variables or parameters
        # you wish to transmit from Spiking to TVB!!
        self._output_devices = self.build_and_connect_output_devices()
        # Build and connect possible Spiking input devices
        # !!Use it only for stimuli, if any!!
        self._input_devices = self.build_and_connect_input_devices()
        return self.build()


def node_key_index_and_label(node, labels):
    if isinstance(node, string_types):
        try:
            i_node = labels.index(node)
            label = node
            node_key = "%d-%s" % (i_node, node)
        except:
            raise_value_error("Node %s is not a region node modeled in Spiking Simulator!" % node)
    else:
        try:
            label = labels[node]
            i_node = node
            node_key = "%d-%s" % (node, label)
        except:
            raise_value_error("Node %d is not a region node modeled in Spiking Simulator!" % node)
    return node_key, i_node, label


# The functions below are used in order to return the builder's properties
# per spiking node or spiking nodes' connection


def property_per_node(property, nodes, nodes_labels):
    if hasattr(property, "__call__") and nodes:
        property_per_node = OrderedDict()
        for node in nodes:
            node_key, node_index = node_key_index_and_label(node, nodes_labels)[:2]
            property_per_node[node_key] = property(node_index)
        return property_per_node
    else:
        return property


def property_per_nodes_connection(property, source_nodes, target_nodes, spiking_nodes_ids, nodes_labels):
    if hasattr(property, "__call__"):
        if source_nodes is None:
            source_nodes = spiking_nodes_ids
        else:
            source_nodes = np.unique(source_nodes)
        if target_nodes is None:
            target_nodes = spiking_nodes_ids
        else:
            target_nodes = np.unique(target_nodes)
        property_per_nodes_connection = OrderedDict()
        for source_node in source_nodes:
            source_index, source_label = node_key_index_and_label(source_node, nodes_labels)[1:]
            for target_node in target_nodes:
                target_index, target_label = node_key_index_and_label(target_node, nodes_labels)[1:]
                node_connection_label = "%d.%s->%d.%s" % (source_index, source_label, target_index, target_label)
                property_per_nodes_connection[node_connection_label] = property(source_index, target_index)
        return property_per_nodes_connection
    else:
        return property
