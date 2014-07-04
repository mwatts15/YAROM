"""
.. class:: Cell

   neuron client
   =============

   This module contains the class that defines the cell

"""

import rdflib as R
import PyOpenWorm
from PyOpenWorm import DataObject, SimpleProperty
from string import Template
import neuroml


# XXX: Should we specify somewhere whether we have NetworkX or something else?
ns =  {'ns1': 'http://www.neuroml.org/schema/neuroml2/'}
segment_query = Template("""
SELECT ?seg_id ?seg_name ?x ?y ?z ?d ?par_id ?x_prox ?y_prox ?z_prox ?d_prox
WHERE {
  ?p ns1:id '$morph_name' .
  ?p ns1:segment ?segment .
  ?segment ns1:distal 	?loop
         ; ns1:id 	    ?seg_id
         ; ns1:name 	?seg_name .

  OPTIONAL {
      ?segment ns1:proximal	?loop_prox .
      ?loop_prox ns1:x ?x_prox
        ; ns1:y ?y_prox
        ; ns1:z ?z_prox
        ; ns1:diameter ?d_prox .
  }
  OPTIONAL {?segment ns1:parent ?par . ?par ns1:segment ?par_id  }.
  ?loop ns1:x ?x
    ; ns1:y ?y
    ; ns1:z ?z
    ; ns1:diameter ?d .
}
            """)
segment_group_query = Template("""
SELECT ?gid ?member ?include
WHERE {
  ?p ns1:id '$morph_name' .
  ?p ns1:segmentGroup ?seg_group .
  ?seg_group ns1:id ?gid .
  OPTIONAL {
    ?seg_group ns1:include ?inc .
    ?inc ns1:segmentGroup ?include .
  }
  OPTIONAL {
    ?seg_group ns1:member ?inc .
    ?inc ns1:segment ?member .
  }
}
            """)
class Cell(DataObject):
    def __init__(self, name, lineageName=False, conf=False):
        DataObject.__init__(self,conf=conf)
        self._name = name
        self.lineageName = SimpleProperty(self, "lineageName")
        self.name = SimpleProperty(self, "name")
        self._lineageName = lineageName

    def lineageName(self, lineageName=False):
        if lineageName:
            self._lineageName = lineageName
        else:
            if not self._lineageName:
                q = """select ?label {
                    # Get the lineage name, a string
                    <%s> <%s> ?label
                }
                """ % (self.identifier(), self.rdf_namespace['lineageName'])

                qres = self['rdf.graph'].query(q, initNs=ns)
                for r in qres:
                    return r['label']
            else:
                return self._lineageName

    def identifier(self):
        """ A cell can be identified by its name or lineage name """
        if not self._id:
            if self._lineageName:
                q = """select ?x {
                    # Get the lineage name, a string
                    ?x <%s> '%s'
                }
                """ % (self.rdf_namespace['lineageName'], self._lineageName)

                qres = self.rdf.query(q, initNs=ns)
                for r in qres:
                    self._id = r['x']
                    break
            elif self._name:
                q = """select ?x {
                    ?x <%s> '%s'
                }
                """ % (self.rdf_namespace['adultName'], self._name)

                qres = self['rdf.graph'].query(q, initNs=ns)
                for r in qres:
                    self._id = r['x']
                    break
            if not self._id:
                # What identifier should we return if there isn't a good one?
                raise PyOpenWorm.IDError(self)
        return self._id

    def morphology(self):
        morph_name = "morphology_" + str(self.name())

        # Query for segments
        query = segment_query.substitute(morph_name=morph_name)
        qres = self['semantic_net'].query(query, initNs=ns)
        morph = neuroml.Morphology(id=morph_name)
        for r in qres:
            par = False

            if r['par_id']:
                par = neuroml.SegmentParent(segments=str(r['par_id']))
                s = neuroml.Segment(name=str(r['seg_name']), id=str(r['seg_id']), parent=par)
            else:
                s = neuroml.Segment(name=str(r['seg_name']), id=str(r['seg_id']))

            if r['x_prox']:
                loop_prox = neuroml.Point3DWithDiam(*(r[x] for x in ['x_prox','y_prox','z_prox','d_prox']))
                s.proximal = loop_prox

            loop = neuroml.Point3DWithDiam(*(r[x] for x in ['x','y','z','d']))
            s.distal = loop
            morph.segments.append(s)
        # Query for segment groups
        query = segment_group_query.substitute(morph_name=morph_name)
        qres = self['semantic_net'].query(query,initNs=ns)
        for r in qres:
            s = neuroml.SegmentGroup(id=r['gid'])
            if r['member']:
                m = neuroml.Member()
                m.segments = str(r['member'])
                s.members.append(m)
            elif r['include']:
                i = neuroml.Include()
                i.segment_groups = str(r['include'])
                s.includes.append(i)
            morph.segment_groups.append(s)
        return morph

    def triples(self):
        ident = self.identifier()
        yield (ident, R.RDF['type'], self.rdf_type)
        if self.lineageName.triples():
            yield (ident, self.rdf_namespace['lineageName'], R.Literal(self._lineageName))
        yield (ident, self.rdf_namespace['name'], R.Literal(self._name))

    def name(self):
        return self._name
    #def rdf(self):

    #def peptides(self):



