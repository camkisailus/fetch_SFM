#! /usr/bin/python3

import rospy
import numpy as np
import math
import random

from visualization_msgs.msg import Marker, MarkerArray

# room number: min_x, max_x, min_y, max_y, min_z, max_z
# REGIONS = {
#     'table1': (0, 1, 0, 1, 0, 1),
#     'table2': (5, 6, 5, 6, 5, 6),
# }
REGIONS = {
    'table1': (-2, -3, -5, -4, 0.5, 1.5),
    # 'table2': (5, 6, 5, 6, 5, 6),
}
class ParticleFilter(object):
    def __init__(self, n, valid_regions, color=None, shape=None):
        self.n = n
        self.particles = np.zeros([n, 3])
        self.weights = 1.0/self.n * np.ones([n])
        self.valid_regions = [region_id for region_id in valid_regions]
        self.region_reinvig_p = np.zeros([len(self.valid_regions)])
        volumes = []
        for region in self.valid_regions:
            x = REGIONS[region][1] - REGIONS[region][0]
            y = REGIONS[region][3] - REGIONS[region][2]
            z = REGIONS[region][5] - REGIONS[region][4]
            volumes.append(x*y*z)
        total_vol = sum(volumes)
        for i in range(len(self.valid_regions)):
            self.region_reinvig_p[i] = volumes[i] / total_vol
        for i in range(self.n):
            self.reinvigorate(self.particles[i])
    
    def reinvigorate(self, particle):
        region_idx = np.random.choice([i for i in range(len(self.region_reinvig_p))], p=self.region_reinvig_p)
        min_x, max_x, min_y, max_y, min_z, max_z = REGIONS[self.valid_regions[region_idx]]
        x = min_x + random.random()*(max_x - min_x)
        y = min_y + random.random()*(max_y - min_y)
        z = min_z + random.random()*(max_z - min_z)
        particle[0] = x
        particle[1] = y
        particle[2] = z
    
    def jitter(self):
        for i in range(self.n):
            self.particles[i][0] += np.random.normal(0, 0.15)
            self.particles[i][1] += np.random.normal(0, 0.15)
            self.particles[i][2] += np.random.normal(0, 0.15)

    def jitter_particle(self, particle):
        particle[0] += np.random.normal(0, 0.15)
        particle[1] += np.random.normal(0, 0.15)
        particle[2] += np.random.normal(0, 0.15)

class ObjectParticleFilter(ParticleFilter):
    def __init__(self, n, label, valid_regions):
        shape = 'sphere'
        if label == 'spoon':
            color = 'green'
        elif label == 'mug':
            color = 'red'
        super().__init__(n, valid_regions, color, shape)
        self.label = label
        self.observations = []
        self.particle_pub = rospy.Publisher('SFM/{}_particles'.format(self.label), MarkerArray, queue_size=10) 
    
    def show(self):
        marker_array = MarkerArray()
        highest_weight = max(self.weights)
        lowest_weight = min(self.weights)
        threshold = lowest_weight + float((highest_weight-lowest_weight)*0.9)
        for i in range(self.n):
            marker = Marker()
            marker.id = i
            marker.header.frame_id = 'map'
            if self.label == 'grasp_spoon':
                marker.color.r = 1
                marker.type = marker.SPHERE
            elif self.label == 'grasp_mug':
                marker.color.b = 1
                marker.type = marker.SPHERE
            elif self.label == 'stir_mug':
                marker.color.r = 0.5
                marker.color.b = 0.5
                marker.type = marker.CUBE
            elif self.label == 'spoon':
                marker.color.r = 1
                marker.type = marker.CUBE
            elif self.label == 'mug':
                marker.color.b = 1
                marker.type = marker.CUBE
            
            marker.action = marker.ADD
            marker.scale.x = 0.2
            marker.scale.y = 0.2
            marker.scale.z = 0.2
            if self.weights[i] < threshold:
                marker.color.a = 0.1
            else:
                marker.color.a = 1.0
            marker.pose.orientation.w = 1.0
            marker.pose.position.x = self.particles[i, 0]
            marker.pose.position.y = self.particles[i, 1]
            marker.pose.position.z = self.particles[i, 2]
            marker_array.markers.append(marker)
        self.particle_pub.publish(marker_array)

    def add_observation(self, x, y, z):
        self.observations.append((x, y, z))
    
    def update_filter(self):
        self.jitter()
        self.weight()
        self.resample()
        self.show()
        # rs_idx = self.systematic_resample()
        # temp_p = np.copy(self.particles)
        # for i in range(self.n):
        #     self.particles[i] = temp_p[rs_idx[i]]
        # print(rs_idx)
        # self.resample()
    
    def weight(self):
        if(len(self.observations) == 0):
            self.weights = np.ones([self.n])
        else:
            for i in range(self.n):
                max_phi = 0
                for j in range(len(self.observations)):
                    dist = math.pow(self.observations[j][0] - self.particles[i][0], 2) + math.pow(self.observations[j][1] - self.particles[i][1], 2) + math.pow(self.observations[j][2] - self.particles[i][2], 2)
                    phi = math.exp(-1 * dist)
                    if(phi > max_phi):
                        max_phi = phi
                self.weights[i] = max_phi
        # normalize
        w_sum = sum(self.weights)
        for i in range(self.n):
            self.weights[i] /= w_sum
        
    def resample(self):
        if(len(self.observations) == 0):
            for i in range(self.n):
                self.reinvigorate(self.particles[i])
        else:
            for i in range(self.n):
                observation = self.observations[i%len(self.observations)]
                self.particles[i][0] = observation[0]
                self.particles[i][1] = observation[1]
                self.particles[i][2] = observation[2]
                self.jitter_particle(self.particles[i])
    
    def systematic_resample(self):
        """ Performs the systemic resampling algorithm used by particle filters.

        This algorithm separates the sample space into N divisions. A single random
        offset is used to to choose where to sample from for all divisions. This
        guarantees that every sample is exactly 1/N apart.

        Parameters
        ----------
        weights : list-like of float
            list of weights as floats

        Returns
        -------

        indexes : ndarray of ints
            array of indexes into the weights defining the resample. i.e. the
            index of the zeroth resample is indexes[0], etc.
        """
        N = len(self.weights)

        # make N subdivisions, and choose positions with a consistent random offset
        positions = (np.random.random() + np.arange(N)) / N

        indexes = np.zeros(N, 'i')
        cumulative_sum = np.cumsum(self.weights)
        i, j = 0, 0
        while i < N:
            if positions[i] < cumulative_sum[j]:
                indexes[i] = j
                i += 1
            else:
                j += 1
        return indexes




if __name__ == '__main__':
    rospy.init_node('SFM')
    foo = ObjectParticleFilter(100, 'mug', ['table1'])
    r = rospy.Rate(1)
    while not rospy.is_shutdown():
        rospy.loginfo("updating")
        foo.update_filter()
        r.sleep()

    # foo.jitter()
    # foo.add_observation(0, 0, 0)
    # foo.add_observation(5, 5, 5)
    # foo.weight()
    # print(foo.particles)
    # # for i in range(100):
    # #     print("{}: ({:.4f}, {:.4f}, {:.4f}, {:.4f}".format(i, foo.particles[i][0], foo.particles[i][2], foo.particles[i][2], foo.weights[i]))
    # for i in range(100):
    #     foo.update_filter()
    # for i in range(100):
    #     print("{}: ({:.4f}, {:.4f}, {:.4f}, {:.4f}".format(i, foo.particles[i][0], foo.particles[i][2], foo.particles[i][2], foo.weights[i]))


