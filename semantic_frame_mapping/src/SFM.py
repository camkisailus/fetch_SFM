#! /usr/bin/python3

import rospy
import numpy as np
import math
import random

from visualization_msgs.msg import Marker, MarkerArray
from particle_filters import *
from utils import *

# room number: min_x, max_x, min_y, max_y, min_z, max_z
# REGIONS = {
#     'table1': (0, 1, 0, 1, 0, 1),
#     'table2': (5, 6, 5, 6, 5, 6),
# }
REGIONS = {
    'table1': (-2, -3, -5, -4, 0.5, 1.5),
    'table2': (5, 6, 5, 6, 5, 6),
}

class Region():
    def __init__(self, name, min_x, max_x, min_y, max_y, min_z, max_z):
        self.name = name
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y
        self.min_z = min_z
        self.max_z = max_z
    
    def get_bounds(self):
        return (self.min_x, self.max_x, self.min_y, self.max_y, self.min_z, self.max_z)
    
class SFMClient():
    def __init__(self):
        self.kb = init_knowledge_base(rospy.get_param('~sf_dir'))
        self.regions = {}
        for name, bounds in REGIONS.items():
            self.regions[name] = Region(name, bounds[0], bounds[1],bounds[2], bounds[3], bounds[4], bounds[5])
        self.spoon_particle_filter = ObjectParticleFilter(50, valid_regions=[self.regions['table1']], label='spoon')
        self.mug_particle_filter = ObjectParticleFilter(50, valid_regions=[self.regions['table2']], label='mug')
        self.object_filters = {'spoon':self.spoon_particle_filter, 'mug':self.mug_particle_filter}
        self.frame_filters = {}
        self.frame_to_label_dict = {}
        for i, frame in enumerate(self.kb):
            self.frame_to_label_dict[i] = frame.name
            valid_regions = [self.regions['table1']]
            filter = FrameParticleFilter(50, frame.name, frame.preconditions, frame.core_frame_elements, valid_regions)
            for cfe in frame.core_frame_elements:
                filter.add_frame_element(self.object_filters[cfe], cfe)
            self.frame_filters[frame.name] = filter
            rospy.loginfo("{} filter initialized".format(frame.name))
        for frame in self.kb:
            for precondition in frame.preconditions:
                print("Adding {} for {}".format(precondition, frame.name))
                self.frame_filters[frame.name].add_precondition(self.frame_filters[precondition], precondition)
        for _, filter in self.frame_filters.items():
            print(filter.label)
            for name, fe_filter in filter.frame_element_filters.items():
                print("\tcfe: {}, filter: {}".format(name, fe_filter.label))
            try:
                for name, p_filter in filter.precondition_filters.items():
                    print("\tpcond: {}, filter: {}".format(name, p_filter.label))
            except AttributeError:
                print("No preconditions!")

if __name__ == '__main__':
    rospy.init_node('sematic_frame_mapping_node')
    foo = SFMClient()
    r = rospy.Rate(1)
    while not rospy.is_shutdown():
        r.sleep()
