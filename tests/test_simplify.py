#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

import unittest
import os
import ogr
import shapely.wkb
from afcsimplifier.geotool import distance, qdistance
from afcsimplifier.simplifier import ChainDB
from afcsimplifier.douglaspeucker import douglaspeucker
from utils import TestCaseGeometry, load_wkt, load_shapefile

data_dir = os.path.join(os.path.dirname(__file__), 'data')


def data_path(name):
    return os.path.join(data_dir, name)


# constraints:
# expandcontract=None,
# repair_intersections=False,
# repair_intersections_precision=0.01,
# prevent_shape_removal=None,
# prevent_shape_removal_min_points=3,
# use_topology=False,
# use_topology_snap_precision=0.0001,
# simplify_shared_edges=False,
# simplify_non_shared_edges=False,


class TestSimplifier(TestCaseGeometry):
    def setUp(self):
        print "-------------------------"

    def _test_geometry_simplification(self, geometries, simplifier, simplifier_params, constraints,
                                      check_valid=True, check_simple=True):
        if not isinstance(geometries, dict):
            geometries = {'A': geometries}
        geometries_removed = 0
        simp_geometries = {}
        for gid, simp_wkb in self.simplify_geometries(geometries, simplifier, simplifier_params, constraints):
            if simp_wkb is None:
                geometries_removed += 1
                continue
            try:
                simp_geometries[gid] = simp_wkb
                if check_valid:
                    self.assertValidGeometry(simp_wkb)
                if check_simple:
                    self.assertSimpleGeometry(simp_wkb)
            except AssertionError:
                print "Failed on geometry id={}".format(gid)
                raise
        if constraints.get('prevent_shape_removal') is True:
            self.assertEquals(geometries_removed, 0)
        return simp_geometries

    def test_preserve_topology(self):
        geometries = load_shapefile(data_path('naturalearth_nations/ne_10m_admin_0_countries.shp'),
                                    geom_key='ISO_A2')
        simplifier = douglaspeucker
        simplifier_params = dict(epsilon=0.01)
        constraints = dict(use_topology=True,
                           use_topology_snap_precision=0.0001,
                           simplify_shared_edges=True,
                           simplify_non_shared_edges=True)
        self._test_geometry_simplification(geometries, simplifier, simplifier_params, constraints,
                                           check_valid=False, check_simple=True)

    def test_expandcontract(self):
        geometries = load_shapefile(data_path('naturalearth_nations/ne_10m_admin_0_countries.shp'),
                                    geom_key='ISO_A2')
        geometries = {k: v for k, v in geometries.iteritems() if k.split(":")[1] == 'VN'}
        #poly = load_wkt(data_path('poly2.wkt'))
        #geometries = {'A': poly.wkb}

        simplifier = douglaspeucker
        simplifier_params = dict(epsilon=0.1)
        self.save_shapefile(data_path('test'), 'orig', geometries)
        for mode in ["Expand", "Contract"]:
            constraints = dict(expandcontract=mode,
                               # until I find a way to validate the constraint when receiving non-valid or non-simple
                               # polygons, I set these constraints so that I can use
                               # shapely.union and shapely.intersection to test expand/contract
                               prevent_shape_removal=True,
                               repair_intersections=True,
                               # to speedup repair intersections
                               use_topology=False,  # TODO: Fails with TRUE because multiple chains in linearring
                               simplify_shared_edges=True,
                               simplify_non_shared_edges=True,
                               )
            simp_geometries = self._test_geometry_simplification(geometries, simplifier, simplifier_params, constraints,
                                                                 check_valid=False, check_simple=False)
            self.save_shapefile(data_path('test'), 'simp', simp_geometries)
            for key, simp_wkb in simp_geometries.iteritems():
                geom = shapely.wkb.loads(geometries[key])
                simp_geom = shapely.wkb.loads(simp_wkb)

                intersection = geom.intersection(simp_geom)
                union = geom.union(simp_geom)
                if mode == "Expand":
                    # Nothing from the original geometry is lost
                    self.assertTrue(geom.equals(intersection))
                    self.assertTrue(simp_geom.equals(union))
                if mode == "Contract":
                    self.assertTrue(simp_geom.equals(intersection))
                    self.assertTrue(geom.equals(union))

    def test_repair_intersections(self):
        geometries = load_shapefile(data_path('naturalearth_nations/ne_10m_admin_0_countries.shp'),
                                    geom_key='ISO_A2')
        simplifier = douglaspeucker
        simplifier_params = dict(epsilon=0.01)
        constraints = dict(repair_intersections=True,
                           repair_intersections_precision=0.001)
        self._test_geometry_simplification(geometries, simplifier, simplifier_params, constraints,
                                           check_valid=True, check_simple=True)

    def test_line_first_and_last_segment_intersects_after_simplify(self):
        line_geom = load_wkt(data_path('line1.wkt'))
        simplifier = douglaspeucker
        simplifier_params = dict(epsilon=150)
        constraints = dict(repair_intersections=True,
                           repair_intersections_precision=0.001)
        self._test_geometry_simplification(line_geom.wkb, simplifier, simplifier_params, constraints,
                                           check_valid=True, check_simple=True)

    def test_build_geometry(self):
        """ Test that build_geometry correctly merge chains
        """
        for num_points in range(3, 7):
            cdb = ChainDB()

            # generate a geometry
            points = [(x, x**2) for x in xrange(num_points*2)]
            gpoly = ogr.Geometry(ogr.wkbPolygon)
            gring = ogr.Geometry(ogr.wkbLinearRing)
            for p in points:
                gring.AddPoint_2D(*p)
            gring.AddPoint_2D(*points[0])  # close ring
            gpoly.AddGeometry(gring)
            wkb = gpoly.ExportToWkb(1)

            cdb.add_geometry('A', wkb)

            cdb.print_geoms()
            cdb.print_chains()
            print cdb.chains
            print "-"*30

            wkb2 = cdb.to_wkb('A')

            import shapely.wkb
            p1 = shapely.wkb.loads(wkb).exterior.coords
            p2 = shapely.wkb.loads(wkb2).exterior.coords
            print list(p1)
            print list(p2)
            self.assertEquals(wkb, wkb2)

if __name__ == "__main__":
    unittest.main()
