# -*- coding: utf-8 -*-
"""
.. class:: Worm

   This module contains the class that defines the worm as a whole

"""

import PyOpenWorm as P
from PyOpenWorm import DataObject


class Worm(DataObject):
    """
    Attributes
    ----------
    neuron_network : ObjectProperty
        The neuron network of the worm
    muscle : ObjectProperty
        Muscles of the worm

    """

    def __init__(self,scientific_name=False,**kwargs):
        DataObject.__init__(self,**kwargs)
        Worm.DatatypeProperty("scientific_name", owner=self)
        Worm.ObjectProperty("neuron_network", owner=self, value_type=P.Network)
        Worm.ObjectProperty("muscle", owner=self, value_type=P.Muscle)
        Worm.ObjectProperty("cell", owner=self, value_type=P.Cell)

        if scientific_name:
            self.scientific_name(scientific_name)
        else:
            self.scientific_name("C. elegans")

    def get_neuron_network(self):
        """
        Get the network object

        :returns: An object to work with the network of the worm
        :rtype: PyOpenWorm.Network
        """
        for x in self.neuron_network():
            return x

    def muscles(self):
        """
        Get all muscles by name

        :returns: A list of all muscle names
        :rtype: list
         """
        for x in self.muscle():
            yield x

    def get_semantic_net(self):
        """
         Get the underlying semantic network as an RDFLib Graph

        :returns: A semantic network containing information about the worm
        :rtype: rdflib.ConjunctiveGraph
         """

        return self['semantic_net']
