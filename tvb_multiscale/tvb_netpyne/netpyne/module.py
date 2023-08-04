import numpy as np

from netpyne import specs, sim
from netpyne.sim import *
from copy import deepcopy


class NetpyneModule(object):

    spikeGenerators = []
    _readyToRun = False
    
    def __init__(self):
        self._autoCreatedPops = []
        self._spikeGeneratorPops = []
        self._spikeGeneratorsToRecord = []
        self._tracesToRecord = {}
        self._popsToRecordTraces = []

        self._compileOrLoadMod()

    def _compileOrLoadMod(self):
        # Make sure that all required mod-files are compiled (is there a better way to check?)
        try:
            h.DynamicVecStim()
        except:
            import sys, os
            currDir = os.getcwd()

            python_path = sys.executable.split("python")[0]
            tvb_multiscale_path = os.path.abspath(__file__).split("tvb_multiscale")[0]
            # before compiling, need to cd to where those specific mod files live, to avoid erasing any other dll's that might contain other previously compiled model
            os.chdir(f'{tvb_multiscale_path}/tvb_multiscale/tvb_netpyne/netpyne/mod')
            if not os.path.exists('x86_64'):
                print("NetPyNE couldn't find necessary mod-files. Trying to compile..")
                os.system(f'{python_path}nrnivmodl .')
            else:
                print(f"NetPyNE will load mod-files from {os.getcwd()}.")
            import neuron
            neuron.load_mechanisms('.')

            os.chdir(currDir)

    def importModel(self, netParams, simConfig, dt, config):

        simConfig.dt = dt

        simConfig.simLabel = 'spiking'
        simConfig.saveFolder = config.out._out_base # TODO: better use some public method

        # using DynamicVecStim model for artificial cells serving as stimuli
        netParams.cellParams['art_NetStim'] = {'cellModel': 'DynamicVecStim'}

        self._netParams = netParams
        self._simConfig = simConfig

    @property
    def netParams(self):
        if self._netParams:
            return self._netParams
        return sim.net.params

    @property
    def simConfig(self):
        if self._simConfig:
            return self._simConfig
        return sim.cfg

    @property
    def dt(self):
        return self.simConfig.dt

    @property
    def minDelay(self):
        return self.dt

    @property
    def time(self):
        return h.t

    def createNetwork(self):
        sim.initialize(self.netParams, self.simConfig)
        self._netParams = None
        self._simConfig = None

        sim.net.createPops()
        sim.net.createCells()
        sim.net.connectCells()
        sim.net.addStims()
        sim.net.addRxD()

    def prepareSimulation(self, duration):

        simConfig = self.simConfig
        simConfig.duration = duration

        simConfig.recordTraces.update(self._tracesToRecord)
        simConfig.recordCells.extend(self._popsToRecordTraces)

        # choose N random cells from each population to plot traces for
        if len(self._autoCreatedPops):
            n = 1
            rnd = np.random.RandomState(0)
            def includeFor(pop):
                popSize = len(sim.net.pops[pop].cellGids)
                chosen = (pop, rnd.choice(popSize, size=min(n, popSize), replace=False).tolist())
                return chosen
            include = list(map(includeFor, self._autoCreatedPops))
            simConfig.analysis['plotTraces'] = {'include': include, 'saveFig': True}

        # exclude spike generators from spike recording.. (unless explicitly configured in device's params) 
        exclude = [pop for pop in self._spikeGeneratorPops if pop not in self._spikeGeneratorsToRecord]
        record = [pop for pop in self.netParams.popParams.keys() if pop not in exclude]
        if simConfig.recordCellsSpikes == -1: # only if no specific configuration
            simConfig.recordCellsSpikes = record
        # .. and from plotting
        simConfig.analysis['plotRaster'] = {'saveFig': True, 'include': record, 'popRates': 'minimal'}

        sim.setSimCfg(simConfig)
        sim.setupRecording()
        sim.run.prepareSimWithIntervalFunc()

        # interval run is used internally to support communication with TVB. However, users may also need to have feedbacks
        # at some interval, distinct from those used internally. User-defined interval and intervalFunc are read here, and the logic is handled in `run()`
        if hasattr(self.simConfig, 'interval'):
            self.interval = self.simConfig.interval
            self.intervalFunc = self.simConfig.intervalFunc
            self.nextIntervalFuncCall = self.interval
        else:
            self.nextIntervalFuncCall = None

        self._readyToRun = True


    def connectStimuli(self, sourcePop, targetPop, weight, delay, receptorType, prob=None):
        # TODO: randomize weight and delay, if values do not already contain sting func
        # (e.g. use random_normal_weight() and random_uniform_delay() from netpyne_templates)
        sourceCells = self.netParams.popParams[sourcePop]['numCells']
        targetCells = self.netParams.popParams[targetPop]['numCells']

        if prob:
            rule = 'probability'
            val = prob

        # connect cells roughly one-to-one ('lamda' for E -> I connections is already taken into account, as it baked into source population size)
        elif sourceCells <= targetCells:
            rule = 'divergence'
            val = 1.0
        else:
            rule = 'convergence'
            val = 1.0

        connLabel = sourcePop + '->' + targetPop
        self.netParams.connParams[connLabel] = {
            'preConds': {'pop': sourcePop},
            'postConds': {'pop': targetPop},
            rule: val,
            'weight': weight,
            'delay': delay,
            'synMech': receptorType
        }

    def interconnectSpikingPopulations(self, sourcePopulation, targetPopulation, synapticMechanism, weight, delay, probabilityOfConn):

        label = sourcePopulation + "->" + targetPopulation
        self.netParams.connParams[label] = {
            'preConds': {'pop': sourcePopulation},
            'postConds': {'pop': targetPopulation},
            'probability': probabilityOfConn,
            'weight': weight,
            'delay': delay,
            'synMech': synapticMechanism }

    def registerPopulation(self, label, cellModel, size):
        self._autoCreatedPops.append(label)
        self.netParams.popParams[label] = {'cellType': cellModel, 'numCells': size}

    def createArtificialCells(self, label, number, record=False):
        print(f"Netpyne:: Creating artif cells for node '{label}' of {number} neurons")
        self.netParams.popParams[label] = {
            'cellType': 'art_NetStim',
            'numCells': number,
        }
        self._spikeGeneratorPops.append(label)
        if record:
            self._spikeGeneratorsToRecord.append(label)

    def recordTracesFromPop(self, traces, pop):
        if pop not in self._popsToRecordTraces:
            self._popsToRecordTraces.append(pop)

        for traceId, traceVal in traces.items():
            if traceId not in self._tracesToRecord:
                self._tracesToRecord[traceId] = deepcopy(traceVal)
            trace = self._tracesToRecord[traceId]
            existingPops = trace.get('conds', {}).get('pop')
            if existingPops and (pop not in existingPops):
                existingPops.append(pop)
            else:
                existingPops = [pop]
                trace['conds'] = {'pop': existingPops}

    def getSpikes(self, generatedBy=None, startingFrom=None):

        if not 'spkid' in sim.simData:
            return [], []

        spktimes = np.array(sim.simData['spkt'])
        spkgids = np.array(sim.simData['spkid'])

        if startingFrom is not None:
            inds = np.nonzero(spktimes > startingFrom) # filtered by time # (self.time - timeWind)

            spktimes = spktimes[inds]
            spkgids = spkgids[inds]

        if generatedBy is not None:
            inds = np.isin(spkgids, generatedBy)

            spktimes = spktimes[inds]
            spkgids = spkgids[inds]
        return spktimes, spkgids

    def getRecordedTime(self):
        return np.array(sim.simData['t'])

    def getTraces(self, key, neuronIds, timeSlice=slice(None)):
        time = self.getRecordedTime()[timeSlice]
        tracesPerNeuron = sim.allSimData.get(key)
        data = np.zeros((len(neuronIds), len(time)))
        for neurInd, neurId in enumerate(neuronIds):
            trace = tracesPerNeuron[f'cell_{neurId}']
            data[neurInd] = trace[timeSlice]
        return data

    def cellGidsForPop(self, popLabel):
        return sim.net.pops[popLabel].cellGids

    def neuronsConnectedWith(self, targetPop):
        gids = []
        for connection in self.netParams.connParams.keys():
            if connection.find(targetPop) >= 0:
                pop = self.netParams.connParams[connection]['postConds']['pop']
                gids.append(self.cellGidsForPop(pop))
        gids = np.array(gids).flatten()
        return gids

    def run(self, length):

        assert self._readyToRun, "The `NetpyneModule.prepareSimulation()` method has to be called prior to start of simulation."

        self.stimulate(length)

        # handling (potentially) two distinct intervals (see comment in `createAndPrepareNetwork()`)
        tvbIterationEnd = self.time + length
        def _(simTime): pass
        if self.nextIntervalFuncCall:
            while (self.nextIntervalFuncCall < min(tvbIterationEnd, sim.cfg.duration)):
                sim.run.runForInterval(self.nextIntervalFuncCall - self.time, _)
                self.intervalFunc(self.time)
                self.nextIntervalFuncCall = self.time + self.interval
        if tvbIterationEnd > self.time:
            if self.time < sim.cfg.duration:
                sim.run.runForInterval(tvbIterationEnd - self.time, _)

                if self.nextIntervalFuncCall:
                    # add correction to avoid accumulation of arithmetic error due to that h.t advances slightly more than the requested interval
                    correction = self.time - tvbIterationEnd
                    self.nextIntervalFuncCall += correction

    def stimulate(self, length):
        allNeuronsSpikes = {}
        allNeurons = []
        for device in self.spikeGenerators:
            allNeurons.extend(device.own_neurons)
            allNeuronsSpikes.update(device.spikesPerNeuron)

            device.spikesPerNeuron = {} # clear to prepare for next interval run

        intervalEnd = h.t + length
        for gid in allNeurons:
            spikes = allNeuronsSpikes.get(gid, [])
            spikes = h.Vector(spikes)
            sim.net.cells[gid].hPointp.play(spikes, intervalEnd)

    def finalize(self):
        if self.time < sim.cfg.duration:
            stopTime = None
        else:
            stopTime = sim.cfg.duration
        sim.run.postRun(stopTime)
        sim.gatherData()
        sim.analyze()
