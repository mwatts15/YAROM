"""
.. class:: Connection

   connection
   =============

   Connection between neurons

"""
from PyOpenWorm import Relationship,Neuron
from string import Template
import rdflib as R

class SynapseType:
    Chemical,GapJunction = range(2)

class Connection(Relationship):
    def __init__(self,
                 pre_cell=None,
                 post_cell=None,
                 number=0,
                 syntype=None,
                 synclass=None,
                 conf=False):
        Relationship.__init__(self,conf=conf)
        self.rdf_type = self.conf['rdf.namespace']['Connection']
        self.namespace = R.Namespace(self.rdf_type + '/')

        if isinstance(pre_cell,Neuron) or pre_cell is None:
            self.pre_cell = pre_cell
        elif pre_cell is not None:
            self.pre_cell = Neuron(name=pre_cell, conf=self.conf)

        if (isinstance(post_cell,Neuron)) or post_cell is None:
            self.post_cell = post_cell
        elif post_cell is not None:
            self.post_cell = Neuron(name=post_cell, conf=self.conf)

        self.number = int(number)
        if isinstance(syntype,basestring):
            syntype=syntype.lower()
            if syntype in ('send', SynapseType.Chemical):
                self.syntype = SynapseType.Chemical
            elif syntype in ('gapjunction', SynapseType.GapJunction):
                self.syntype = SynapseType.GapJunction
        else:
            self.syntype = None

        self.synclass = synclass

    def identifier(self):
        data = (self.pre_cell, self.post_cell, self.number,self.syntype, self.synclass)
        return self.conf['molecule_name'](data)

    def triples(self):
        pre_cell = self.pre_cell.identifier()
        post_cell = self.post_cell.identifier()
        ident = self.identifier()

        yield (pre_cell, self.conf['rdf.namespace']['356'], post_cell)
        yield (ident, R.RDF['type'], self.rdf_type)
        yield (ident, self.namespace['pre'], pre_cell)

        if self.syntype == SynapseType.Chemical:
            yield (ident, self.namespace['syntype'], self.conf['rdf.namespace']['356'])
        elif self.syntype == SynapseType.GapJunction:
            yield (ident, self.namespace['syntype'], self.conf['rdf.namespace']['357'])
        else:
            yield (ident, self.namespace['syntype'], self.namespace['UnknownType'])

        if self.synclass:
            yield (ident, self.namespace['neurotransmitter'], R.Literal(synclass))
        else:
            yield (ident, self.namespace['neurotransmitter'], R.Literal("unknown class"))

        yield (ident, self.namespace['post'], post_cell)

    def load(self):
        t = Template("""
        SELECT ?pre ?post ?syntype ?id ?number
        WHERE
        {
            ?id $pre_pred ?pre_n .
            ?pre_n rdfs:label ?pre  .

            ?id $post_pred ?post_n .
            ?post_n rdfs:label ?post  .

            ?id $syntype_pred ?syntype .
            ?id $synclass_pred ?syntype .
            ?id $number_pred ?number .
            # Additional Bindings
            $binds
        }
        """)
        binds = dict()
        if self.number != 0:
            binds['number'] = R.Literal(self.number,datatype=R.XSD.integer)
        if self.pre_cell is not None:
            binds['pre_n'] = self.pre_cell.identifier().n3()
        if self.post_cell is not None:
            binds['post_n'] = self.post_cell.identifier().n3()
        if self.syntype is not None:
            binds['syntype'] = R.Literal(self.syntype)

        q = t.substitute(pre_pred=self.namespace['pre'].n3(),
                syntype_pred=self.namespace['syntype'].n3(),
                post_pred=self.namespace['post'].n3(),
                number_pred=self.namespace['number'].n3(),
                synclass_pred=self.namespace['neurotransmitter'].n3(),
                binds=_dict_to_sparql_binds(binds))
        res = self['rdf.graph'].query(q)
        for r in res:
            yield Connection(pre_cell=r['pre'], post_cell=r['post'], syntype=r['syntype'], number=r['number'])
    def __str__(self):
        return "Connection from %s to %s (%i times, type: %s, neurotransmitter: %s)"%(self.pre_cell, self.post_cell, self.number, self.syntype, self.synclass)

def _dict_to_sparql_binds(d):
    return "\n".join('filter(' + d[x] + ' = ?' + x + ')' for x in d)
